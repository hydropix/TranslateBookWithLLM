"""
Translation module for LLM communication
"""
import asyncio
import time
import re
from tqdm.auto import tqdm

from src.config import (
    DEFAULT_MODEL, TRANSLATE_TAG_IN, TRANSLATE_TAG_OUT
)
from prompts.prompts import generate_translation_prompt, generate_subtitle_block_prompt
from .llm_client import default_client, LLMClient, create_llm_client
from .post_processor import clean_translated_text
from .context_optimizer import (
    estimate_tokens_with_margin,
    adjust_parameters_for_context,
    validate_configuration,
    format_estimation_info
)
from typing import List, Dict, Tuple, Optional




async def generate_translation_request(main_content, context_before, context_after, previous_translation_context,
                                       source_language="English", target_language="French", model=DEFAULT_MODEL,
                                       llm_client=None, log_callback=None, fast_mode=False):
    """
    Generate translation request to LLM API

    Args:
        main_content (str): Text to translate
        context_before (str): Context before main content
        context_after (str): Context after main content
        previous_translation_context (str): Previous translation for consistency
        source_language (str): Source language
        target_language (str): Target language
        model (str): LLM model name
        llm_client: LLM client instance
        log_callback (callable): Logging callback function
        fast_mode (bool): If True, uses simplified prompts without placeholder instructions

    Returns:
        str: Translated text or None if failed
    """
    # Skip LLM translation for single character or empty chunks
    if len(main_content.strip()) <= 1:
        if log_callback:
            log_callback("skip_translation", f"Skipping LLM for single/empty character: '{main_content}'")
        return main_content
    
    structured_prompt = generate_translation_prompt(
        main_content,
        context_before,
        context_after,
        previous_translation_context,
        source_language,
        target_language,
        fast_mode=fast_mode
    )
    
    # Log the LLM request with structured data for web interface
    if log_callback:
        log_callback("llm_request", "Sending request to LLM", data={
            'type': 'llm_request',
            'prompt': structured_prompt,
            'model': model
        })

    start_time = time.time()

    # Use provided client or default
    client = llm_client or default_client
    full_raw_response = await client.make_request(structured_prompt, model)
    execution_time = time.time() - start_time

    if not full_raw_response:
        err_msg = "ERROR: LLM API request failed"
        if log_callback: 
            log_callback("llm_api_error", err_msg)
        else: 
            tqdm.write(f"\n{err_msg}")
        return None

    # Log the LLM response with structured data for web interface
    if log_callback:
        log_callback("llm_response", "LLM Response received", data={
            'type': 'llm_response',
            'response': full_raw_response,
            'execution_time': execution_time,
            'model': model
        })

    translated_text = client.extract_translation(full_raw_response)
    
    if translated_text:
        # Apply post-processor cleaning
        return clean_translated_text(translated_text)
    else:
        warn_msg = f"WARNING: Translation tags missing in LLM response."
        if log_callback:
            log_callback("llm_tag_warning", warn_msg)
            log_callback("llm_raw_response_preview", f"LLM raw response: {full_raw_response[:500]}...")
        else:
            tqdm.write(f"\n{warn_msg} Excerpt: {full_raw_response[:100]}...")

        if main_content in full_raw_response:
            discard_msg = "WARNING: LLM response seems to contain input. Discarded."
            if log_callback: 
                log_callback("llm_prompt_in_response_warning", discard_msg)
            else: 
                tqdm.write(discard_msg)
            return None
        # Apply post-processor cleaning even in the fallback case
        return clean_translated_text(full_raw_response.strip())


async def translate_chunks(chunks, source_language, target_language, model_name,
                          api_endpoint, progress_callback=None, log_callback=None,
                          stats_callback=None, check_interruption_callback=None,
                          llm_provider="ollama", gemini_api_key=None, openai_api_key=None,
                          context_window=2048, auto_adjust_context=True, min_chunk_size=5, fast_mode=False,
                          checkpoint_manager=None, translation_id=None, resume_from_index=0):
    """
    Translate a list of text chunks

    Args:
        chunks (list): List of chunk dictionaries
        source_language (str): Source language
        target_language (str): Target language
        model_name (str): LLM model name
        api_endpoint (str): API endpoint
        progress_callback (callable): Progress update callback
        log_callback (callable): Logging callback
        stats_callback (callable): Statistics update callback
        check_interruption_callback (callable): Interruption check callback
        context_window (int): Context window size (num_ctx)
        auto_adjust_context (bool): Enable automatic context adjustment
        min_chunk_size (int): Minimum chunk size when auto-adjusting
        fast_mode (bool): If True, uses simplified prompts without placeholder instructions
        checkpoint_manager: CheckpointManager instance for saving progress
        translation_id: Job ID for checkpoint saving
        resume_from_index: Index to resume from (for resumed jobs)

    Returns:
        list: List of translated chunks
    """
    total_chunks = len(chunks)
    full_translation_parts = []
    last_successful_llm_context = ""
    completed_chunks_count = 0
    failed_chunks_count = 0

    # Get chunk_size from first chunk (assuming consistent chunking)
    chunk_size = 25  # Default fallback
    if chunks and 'main_content' in chunks[0]:
        # Estimate chunk size from first chunk's line count
        chunk_size = len(chunks[0]['main_content'].split('\n'))

    # Handle resume: load previously translated chunks
    if checkpoint_manager and translation_id and resume_from_index > 0:
        checkpoint_data = checkpoint_manager.load_checkpoint(translation_id)
        if checkpoint_data:
            # Restore completed chunks
            saved_chunks = checkpoint_data['chunks']
            for chunk in saved_chunks:
                if chunk['status'] == 'completed' and chunk['translated_text']:
                    full_translation_parts.append(chunk['translated_text'])
                    completed_chunks_count += 1
                else:
                    # Failed chunk - use original
                    full_translation_parts.append(chunk['original_text'])
                    failed_chunks_count += 1

            # Restore translation context for continuity
            if checkpoint_data.get('translation_context'):
                context = checkpoint_data['translation_context']
                last_successful_llm_context = context.get('last_llm_context', '')

            if log_callback:
                log_callback("checkpoint_resumed",
                    f"Resumed from checkpoint: {completed_chunks_count} chunks already completed, "
                    f"resuming from chunk {resume_from_index + 1}/{total_chunks}")

    if log_callback:
        log_callback("txt_translation_loop_start", "Starting segment translation...")

    # PHASE 2: Validation at startup
    if llm_provider == "ollama" and auto_adjust_context:
        validation_warnings = validate_configuration(
            chunk_size=chunk_size,
            num_ctx=context_window,
            model_name=model_name
        )

        for warning in validation_warnings:
            if log_callback:
                log_callback("context_validation_warning", warning)

    # Create LLM client based on provider or custom endpoint
    llm_client = create_llm_client(llm_provider, gemini_api_key, api_endpoint, model_name, openai_api_key)

    try:
        iterator = tqdm(chunks, desc=f"Translating {source_language} to {target_language}", unit="seg") if not log_callback else chunks

        for i, chunk_data in enumerate(iterator):
            # Skip already processed chunks when resuming
            if i < resume_from_index:
                continue

            if check_interruption_callback and check_interruption_callback():
                if log_callback:
                    log_callback("txt_translation_interrupted", f"Translation process for segment {i+1}/{total_chunks} interrupted by user signal.")
                else:
                    tqdm.write(f"\nTranslation interrupted by user at segment {i+1}/{total_chunks}.")
                # Mark as paused when interrupted
                if checkpoint_manager and translation_id:
                    checkpoint_manager.mark_paused(translation_id)
                break

            if progress_callback and total_chunks > 0:
                progress_callback((i / total_chunks) * 100)
            
            # Log progress summary periodically
            if log_callback and i > 0 and i % 5 == 0:
                log_callback("", "info", {
                    'type': 'progress'
                })

            main_content_to_translate = chunk_data["main_content"]
            context_before_text = chunk_data["context_before"]
            context_after_text = chunk_data["context_after"]

            if not main_content_to_translate.strip():
                full_translation_parts.append(main_content_to_translate)
                completed_chunks_count += 1
                if stats_callback and total_chunks > 0:
                    stats_callback({'completed_chunks': completed_chunks_count, 'failed_chunks': failed_chunks_count})
                # Save checkpoint for empty chunks too
                if checkpoint_manager and translation_id:
                    checkpoint_manager.save_checkpoint(
                        translation_id=translation_id,
                        chunk_index=i,
                        original_text=main_content_to_translate,
                        translated_text=main_content_to_translate,
                        chunk_data=chunk_data,
                        total_chunks=total_chunks,
                        completed_chunks=completed_chunks_count,
                        failed_chunks=failed_chunks_count
                    )
                continue

            # PHASE 2: Estimate and adjust context before sending request
            if llm_provider == "ollama" and auto_adjust_context:
                # Generate the prompt (without sending it yet)
                prompt = generate_translation_prompt(
                    main_content_to_translate,
                    context_before_text,
                    context_after_text,
                    last_successful_llm_context,
                    source_language,
                    target_language
                )

                # Estimate number of tokens
                estimation = estimate_tokens_with_margin(
                    text=prompt,
                    language=source_language,
                    apply_margin=True
                )

                if log_callback and (i == 0 or i % 10 == 0):  # Log periodically to avoid spam
                    log_callback("context_estimation",
                        f"Chunk {i+1}: {format_estimation_info(estimation)}")

                # Adjust parameters if necessary
                adjusted_num_ctx, adjusted_chunk_size, warnings = adjust_parameters_for_context(
                    estimated_tokens=estimation.estimated_tokens,
                    current_num_ctx=context_window,
                    current_chunk_size=chunk_size,
                    model_name=model_name,
                    min_chunk_size=min_chunk_size
                )

                # Log adjustments
                for warning in warnings:
                    if log_callback:
                        log_callback("context_adjustment_warning", warning)

                # Apply adjustments if changed
                if adjusted_num_ctx != context_window:
                    context_window = adjusted_num_ctx
                    # Update the LLM client's context window if possible
                    if hasattr(llm_client, 'context_window'):
                        llm_client.context_window = adjusted_num_ctx
                    if log_callback:
                        log_callback("context_adjustment_applied",
                            f"Adjusted context window to {adjusted_num_ctx} tokens for this chunk")

                if adjusted_chunk_size != chunk_size:
                    # Note: We can't re-chunk dynamically here, just log the warning
                    if log_callback:
                        log_callback("chunk_size_warning",
                            f"⚠️  Chunk size should be reduced to {adjusted_chunk_size} lines, "
                            f"but current chunk already prepared. Consider restarting with smaller chunk_size.")

            translated_chunk_text = await generate_translation_request(
                main_content_to_translate, context_before_text, context_after_text,
                last_successful_llm_context, source_language, target_language,
                model_name, llm_client=llm_client, log_callback=log_callback,
                fast_mode=fast_mode
            )

            if translated_chunk_text is not None:
                # Always apply basic cleaning
                translated_chunk_text = clean_translated_text(translated_chunk_text)
                
                full_translation_parts.append(translated_chunk_text)
                completed_chunks_count += 1
                words = translated_chunk_text.split()
                if len(words) > 25:
                    last_successful_llm_context = " ".join(words[-25:])
                else:
                    last_successful_llm_context = translated_chunk_text
            else:
                err_msg_chunk = f"ERROR translating segment {i+1}. Original content preserved."
                if log_callback: 
                    log_callback("txt_chunk_translation_error", err_msg_chunk)
                else: 
                    tqdm.write(f"\n{err_msg_chunk}")
                error_placeholder = f"[TRANSLATION_ERROR SEGMENT {i+1}]\n{main_content_to_translate}\n[/TRANSLATION_ERROR SEGMENT {i+1}]"
                full_translation_parts.append(error_placeholder)
                failed_chunks_count += 1
                last_successful_llm_context = ""

            if stats_callback and total_chunks > 0:
                stats_callback({'completed_chunks': completed_chunks_count, 'failed_chunks': failed_chunks_count})

            # Save checkpoint after each chunk
            if checkpoint_manager and translation_id:
                translation_context = {
                    'last_llm_context': last_successful_llm_context
                }
                checkpoint_manager.save_checkpoint(
                    translation_id=translation_id,
                    chunk_index=i,
                    original_text=main_content_to_translate,
                    translated_text=translated_chunk_text if translated_chunk_text is not None else None,
                    chunk_data=chunk_data,
                    translation_context=translation_context,
                    total_chunks=total_chunks,
                    completed_chunks=completed_chunks_count,
                    failed_chunks=failed_chunks_count
                )
    
    finally:
        # Clean up LLM client resources if created
        if llm_client:
            await llm_client.close()

    return full_translation_parts


# Subtitle translation functions moved to subtitle_translator.py