"""
Translation module for LLM communication
"""
import asyncio
import time
import re
from tqdm.auto import tqdm

from src.config import (
    DEFAULT_MODEL, TRANSLATE_TAG_IN, TRANSLATE_TAG_OUT, SENTENCE_TERMINATORS,
    THINKING_MODELS, ADAPTIVE_CONTEXT_INITIAL_THINKING
)
from prompts.prompts import generate_translation_prompt, generate_subtitle_block_prompt, generate_refinement_prompt
from prompts.examples import ensure_example_ready, has_example_for_pair, PLACEHOLDER_EXAMPLES
from .llm_client import default_client, LLMClient, create_llm_client, LLMResponse
from .llm_providers import ContextOverflowError, RepetitionLoopError
from .post_processor import clean_translated_text
from .context_optimizer import (
    AdaptiveContextManager,
    validate_configuration,
    INITIAL_CONTEXT_SIZE,
    CONTEXT_STEP
)
from typing import List, Dict, Tuple, Optional


# Configuration for context overflow recovery
MAX_CHUNK_REDUCTION_ATTEMPTS = 3
CHUNK_REDUCTION_FACTOR = 0.6  # Reduce to 60% of original size each attempt
MIN_CHUNK_CHARACTERS = 200  # Minimum chunk size to attempt translation


def split_chunk_for_retry(main_content: str, target_ratio: float = 0.5) -> Tuple[str, str]:
    """
    Split a chunk into two parts for retry after context overflow.

    Tries to split at a sentence boundary near the target ratio.

    Args:
        main_content: The text content to split
        target_ratio: Target position for split (0.5 = middle)

    Returns:
        Tuple of (first_half, second_half)
    """
    if not main_content.strip():
        return main_content, ""

    lines = main_content.split('\n')
    if len(lines) <= 1:
        # For single line, split at sentence boundary or middle
        target_pos = int(len(main_content) * target_ratio)

        # Look for sentence terminators near target position
        best_split = target_pos
        for terminator in SENTENCE_TERMINATORS:
            # Search in a window around target position
            search_start = max(0, target_pos - 100)
            search_end = min(len(main_content), target_pos + 100)
            search_area = main_content[search_start:search_end]

            term_pos = search_area.rfind(terminator)
            if term_pos != -1:
                actual_pos = search_start + term_pos + len(terminator)
                if abs(actual_pos - target_pos) < abs(best_split - target_pos):
                    best_split = actual_pos

        return main_content[:best_split].strip(), main_content[best_split:].strip()

    # For multi-line content, split at line boundaries
    target_line = int(len(lines) * target_ratio)

    # Look for a sentence-ending line near target
    best_line = target_line
    for i in range(max(0, target_line - 5), min(len(lines), target_line + 5)):
        line_stripped = lines[i].strip()
        if line_stripped and line_stripped.endswith(SENTENCE_TERMINATORS):
            best_line = i + 1
            break

    first_half = '\n'.join(lines[:best_line])
    second_half = '\n'.join(lines[best_line:])

    return first_half.strip(), second_half.strip()


def reduce_chunk_content(main_content: str, reduction_factor: float = CHUNK_REDUCTION_FACTOR) -> str:
    """
    Reduce chunk content size while preserving sentence boundaries.

    Args:
        main_content: The text content to reduce
        reduction_factor: Target size as fraction of original (e.g., 0.6 = 60%)

    Returns:
        Reduced content string
    """
    if not main_content.strip():
        return main_content

    target_length = int(len(main_content) * reduction_factor)

    if target_length < MIN_CHUNK_CHARACTERS:
        # Content is already small, just return first part
        first_half, _ = split_chunk_for_retry(main_content, reduction_factor)
        return first_half

    lines = main_content.split('\n')
    if len(lines) <= 1:
        # Single line - truncate at sentence boundary
        first_half, _ = split_chunk_for_retry(main_content, reduction_factor)
        return first_half

    # Multi-line content - take first N lines that fit
    target_lines = max(1, int(len(lines) * reduction_factor))

    # Adjust to sentence boundary
    for i in range(target_lines - 1, min(len(lines), target_lines + 3)):
        line_stripped = lines[i].strip()
        if line_stripped and line_stripped.endswith(SENTENCE_TERMINATORS):
            target_lines = i + 1
            break

    return '\n'.join(lines[:target_lines]).strip()




async def _make_llm_request_with_adaptive_context(
    main_content: str,
    context_before: str,
    context_after: str,
    previous_translation_context: str,
    source_language: str,
    target_language: str,
    model: str,
    llm_client,
    log_callback,
    fast_mode: bool,
    has_images: bool = False,
    prompt_options: dict = None,
    context_manager: AdaptiveContextManager = None
) -> Tuple[Optional[str], str, Optional[LLMResponse]]:
    """
    Make LLM request with adaptive context sizing.

    This function uses the AdaptiveContextManager to:
    1. Start with a small context
    2. Retry with larger context if needed
    3. Return token usage info for the manager to learn from

    Args:
        main_content: Text to translate
        context_before: Context before main content
        context_after: Context after main content
        previous_translation_context: Previous translation for consistency
        source_language: Source language
        target_language: Target language
        model: LLM model name
        llm_client: LLM client instance
        log_callback: Logging callback function
        fast_mode: If True, uses simplified prompts
        has_images: If True (with fast_mode), includes image placeholder preservation instructions
        prompt_options: Optional dict with prompt customization options
        context_manager: AdaptiveContextManager for context sizing

    Returns:
        Tuple of (translated_text or None, actual_content_translated, LLMResponse)
    """
    current_content = main_content
    remaining_content = ""
    all_translations = []
    reduction_attempt = 0
    last_response: Optional[LLMResponse] = None

    while current_content.strip():
        try:
            # Generate prompts
            prompt_pair = generate_translation_prompt(
                current_content,
                context_before,
                context_after,
                previous_translation_context,
                source_language,
                target_language,
                fast_mode=fast_mode,
                has_images=has_images,
                prompt_options=prompt_options
            )

            # Log the request
            if log_callback and reduction_attempt == 0:
                log_callback("llm_request", "Sending request to LLM", data={
                    'type': 'llm_request',
                    'system_prompt': prompt_pair.system,
                    'user_prompt': prompt_pair.user,
                    'model': model
                })

            start_time = time.time()
            client = llm_client or default_client

            # Set context from manager if available
            if context_manager and hasattr(client, 'context_window'):
                new_ctx = context_manager.get_context_size()
                if client.context_window != new_ctx:
                    if log_callback:
                        log_callback("context_update",
                            f"📐 Updating context window: {client.context_window} → {new_ctx}")
                    else:
                        tqdm.write(f"\n📐 Context: {client.context_window} → {new_ctx}")
                client.context_window = new_ctx

            llm_response = await client.make_request(
                prompt_pair.user, model, system_prompt=prompt_pair.system
            )
            execution_time = time.time() - start_time

            if not llm_response:
                return None, main_content, None

            last_response = llm_response
            full_raw_response = llm_response.content

            # Check if we should retry with larger context (adaptive strategy)
            if context_manager and llm_response.was_truncated:
                if context_manager.should_retry_with_larger_context(
                    llm_response.was_truncated, llm_response.context_used
                ):
                    context_manager.increase_context()
                    continue  # Retry with larger context

            # Log the response
            if log_callback:
                log_callback("llm_response", "LLM Response received", data={
                    'type': 'llm_response',
                    'response': full_raw_response,
                    'execution_time': execution_time,
                    'model': model,
                    'tokens': {
                        'prompt': llm_response.prompt_tokens,
                        'completion': llm_response.completion_tokens,
                        'total': llm_response.context_used,
                        'limit': llm_response.context_limit
                    }
                })

            # Extract translation
            translated_text = client.extract_translation(full_raw_response)

            if translated_text:
                all_translations.append(translated_text)
            else:
                # Fallback to raw response if no tags found
                if current_content not in full_raw_response:
                    all_translations.append(full_raw_response.strip())
                else:
                    # Response contains input - this is an error
                    if log_callback:
                        log_callback("llm_prompt_in_response_warning",
                            "WARNING: LLM response seems to contain input. Discarded.")
                    return None, main_content, last_response

            # If we had remaining content from a previous split, translate it
            if remaining_content.strip():
                current_content = remaining_content
                remaining_content = ""
                # Update context for continuity
                if all_translations:
                    words = all_translations[-1].split()
                    previous_translation_context = " ".join(words[-25:]) if len(words) > 25 else all_translations[-1]
                reduction_attempt = 0  # Reset for new content
                continue

            # Success - combine all translations
            combined = "\n".join(all_translations) if all_translations else None
            return combined, main_content, last_response

        except RepetitionLoopError as e:
            # Repetition loop detected - this typically happens with thinking models
            # when context window is too small. Try increasing context.
            if context_manager:
                old_context = context_manager.get_context_size()
                # Force a larger context increase for repetition loops
                context_manager.increase_context()
                context_manager.increase_context()  # Double increase for repetition loops
                new_context = context_manager.get_context_size()

                if new_context > old_context:
                    if log_callback:
                        log_callback("repetition_loop_retry",
                            f"🔄 Repetition loop detected! Increasing context from {old_context} to {new_context} tokens")
                    else:
                        tqdm.write(f"\n🔄 Repetition loop - increasing context to {new_context}")
                    continue  # Retry with larger context

            # No context manager or can't increase further
            if log_callback:
                log_callback("repetition_loop_fatal",
                    f"⚠️ Repetition loop detected and cannot recover. "
                    f"Try manually increasing OLLAMA_NUM_CTX. Error: {e}")
            else:
                tqdm.write(f"\n⚠️ Repetition loop detected - increase OLLAMA_NUM_CTX")
            return None, main_content, last_response

        except ContextOverflowError as e:
            # If we have a context manager, try increasing context
            if context_manager and context_manager.should_retry_with_larger_context(True, 0):
                context_manager.increase_context()
                continue  # Retry with larger context

            reduction_attempt += 1

            if reduction_attempt > MAX_CHUNK_REDUCTION_ATTEMPTS:
                if log_callback:
                    log_callback("context_overflow_fatal",
                        f"⚠️ Context overflow: Max reduction attempts ({MAX_CHUNK_REDUCTION_ATTEMPTS}) "
                        f"exceeded. Original error: {e}")
                else:
                    tqdm.write(f"\n⚠️ Context overflow after {MAX_CHUNK_REDUCTION_ATTEMPTS} reduction attempts")
                return None, main_content, last_response

            # Calculate new reduction factor
            reduction_factor = CHUNK_REDUCTION_FACTOR ** reduction_attempt

            if log_callback:
                log_callback("context_overflow_retry",
                    f"⚠️ Context overflow detected! Reducing chunk to {reduction_factor*100:.0f}% "
                    f"(attempt {reduction_attempt}/{MAX_CHUNK_REDUCTION_ATTEMPTS})")
            else:
                tqdm.write(f"\n⚠️ Context overflow - reducing chunk (attempt {reduction_attempt})")

            # Split the content
            first_part, second_part = split_chunk_for_retry(current_content, reduction_factor)

            if len(first_part) < MIN_CHUNK_CHARACTERS and not all_translations:
                # Can't reduce further without losing too much content
                if log_callback:
                    log_callback("context_overflow_fatal",
                        f"⚠️ Cannot reduce chunk further (min size: {MIN_CHUNK_CHARACTERS} chars)")
                return None, main_content, last_response

            current_content = first_part
            # Accumulate remaining content for later
            if second_part.strip():
                remaining_content = second_part + ("\n" + remaining_content if remaining_content else "")

    # Shouldn't reach here normally
    return "\n".join(all_translations) if all_translations else None, main_content, last_response


# Legacy wrapper for backward compatibility
async def _make_llm_request_with_overflow_handling(
    main_content: str,
    context_before: str,
    context_after: str,
    previous_translation_context: str,
    source_language: str,
    target_language: str,
    model: str,
    llm_client,
    log_callback,
    fast_mode: bool,
    has_images: bool = False,
    prompt_options: dict = None
) -> Tuple[Optional[str], str]:
    """Legacy wrapper - calls the new adaptive function without a context manager"""
    result, content, _ = await _make_llm_request_with_adaptive_context(
        main_content, context_before, context_after, previous_translation_context,
        source_language, target_language, model, llm_client, log_callback,
        fast_mode, has_images, prompt_options, context_manager=None
    )
    return result, content


async def generate_translation_request(main_content, context_before, context_after, previous_translation_context,
                                       source_language="English", target_language="Chinese", model=DEFAULT_MODEL,
                                       llm_client=None, log_callback=None, fast_mode=False, has_images=False,
                                       prompt_options=None):
    """
    Generate translation request to LLM API with automatic context overflow handling.

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
        has_images (bool): If True (with fast_mode), includes image placeholder preservation instructions
        prompt_options (dict): Optional dict with prompt customization options

    Returns:
        str: Translated text or None if failed
    """
    # Skip LLM translation for single character or empty chunks
    if len(main_content.strip()) <= 1:
        if log_callback:
            log_callback("skip_translation", f"Skipping LLM for single/empty character: '{main_content}'")
        return main_content

    # Use the overflow-handling wrapper
    translated_text, _ = await _make_llm_request_with_overflow_handling(
        main_content=main_content,
        context_before=context_before,
        context_after=context_after,
        previous_translation_context=previous_translation_context,
        source_language=source_language,
        target_language=target_language,
        model=model,
        llm_client=llm_client,
        log_callback=log_callback,
        fast_mode=fast_mode,
        has_images=has_images,
        prompt_options=prompt_options
    )

    if translated_text:
        return translated_text
    else:
        err_msg = "ERROR: LLM API request failed"
        if log_callback:
            log_callback("llm_api_error", err_msg)
        else:
            tqdm.write(f"\n{err_msg}")
        return None


async def translate_chunks(chunks, source_language, target_language, model_name,
                          api_endpoint, progress_callback=None, log_callback=None,
                          stats_callback=None, check_interruption_callback=None,
                          llm_provider="ollama", gemini_api_key=None, openai_api_key=None,
                          openrouter_api_key=None,
                          context_window=2048, auto_adjust_context=True, min_chunk_size=5, fast_mode=False,
                          checkpoint_manager=None, translation_id=None, resume_from_index=0,
                          has_images=False, prompt_options=None):
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
        context_window (int): Initial context window size (num_ctx) - will be adapted
        auto_adjust_context (bool): Enable adaptive context adjustment
        min_chunk_size (int): Minimum chunk size when auto-adjusting
        fast_mode (bool): If True, uses simplified prompts without placeholder instructions
        checkpoint_manager: CheckpointManager instance for saving progress
        translation_id: Job ID for checkpoint saving
        resume_from_index: Index to resume from (for resumed jobs)
        has_images (bool): If True (with fast_mode), includes image placeholder preservation instructions
        prompt_options (dict): Optional dict with prompt customization options

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

    # Validation at startup
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
    # Determine if model is a known thinking model for initial context sizing
    # Thinking models need more context for their reasoning process
    is_known_thinking_model = any(tm in model_name.lower() for tm in THINKING_MODELS)

    # Start with appropriate initial context size based on model type
    if auto_adjust_context:
        if is_known_thinking_model:
            initial_context = ADAPTIVE_CONTEXT_INITIAL_THINKING
        else:
            initial_context = INITIAL_CONTEXT_SIZE
    else:
        initial_context = context_window

    llm_client = create_llm_client(llm_provider, gemini_api_key, api_endpoint, model_name,
                                    openai_api_key, openrouter_api_key,
                                    context_window=initial_context, log_callback=log_callback)

    # Create adaptive context manager for Ollama provider
    context_manager = None
    if llm_provider == "ollama" and auto_adjust_context:
        # Allow context to grow beyond user's initial setting if needed
        # Most modern models support at least 8K-32K context
        # The user's OLLAMA_NUM_CTX is the starting preference, not a hard limit
        from .context_optimizer import MAX_CONTEXT_SIZE
        context_manager = AdaptiveContextManager(
            initial_context=initial_context,
            context_step=CONTEXT_STEP,
            max_context=MAX_CONTEXT_SIZE,  # Allow full range for auto-adjust
            log_callback=log_callback
        )
        model_type = "thinking" if is_known_thinking_model else "standard"
        if log_callback:
            log_callback("context_adaptive",
                f"🎯 Adaptive context enabled ({model_type} model): starting at {initial_context} tokens, "
                f"max={MAX_CONTEXT_SIZE}, step={CONTEXT_STEP}")

    # Pre-generate examples if missing for this language pair (standard mode only)
    if llm_client and not fast_mode:
        provider = llm_client._get_provider()
        if provider:
            # Standard mode: need placeholder examples
            example_ready = await ensure_example_ready(
                source_language, target_language, provider
            )
            if example_ready and log_callback:
                key = (source_language.lower(), target_language.lower())
                if key not in PLACEHOLDER_EXAMPLES:
                    log_callback("example_generated",
                        f"Generated placeholder example for {source_language}->{target_language}")

    # Detect thinking model status before translation loop
    if llm_client and llm_provider == "ollama":
        await llm_client.detect_thinking_model()

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
                # Add remaining untranslated chunks as original text so partial output is complete
                # This ensures image markers and other content are preserved in partial EPUB
                for remaining_chunk in chunks[i:]:
                    full_translation_parts.append(remaining_chunk["main_content"])
                break

            if progress_callback and total_chunks > 0:
                progress_callback((i / total_chunks) * 100)

            # Log progress summary periodically
            if log_callback and i > 0 and i % 5 == 0:
                log_callback("", "info", {
                    'type': 'progress'
                })
                # Log context manager stats periodically
                if context_manager:
                    stats = context_manager.get_stats()
                    log_callback("context_adaptive",
                        f"📊 Context stats: current={stats['current_context']}, "
                        f"avg_usage={stats['avg_usage']:.0f}, max_usage={stats['max_usage']}")

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

            # Skip LLM translation for single character chunks
            if len(main_content_to_translate.strip()) <= 1:
                if log_callback:
                    log_callback("skip_translation", f"Skipping LLM for single/empty character: '{main_content_to_translate}'")
                full_translation_parts.append(main_content_to_translate)
                completed_chunks_count += 1
                continue

            # Use adaptive context translation
            translated_chunk_text, _, llm_response = await _make_llm_request_with_adaptive_context(
                main_content=main_content_to_translate,
                context_before=context_before_text,
                context_after=context_after_text,
                previous_translation_context=last_successful_llm_context,
                source_language=source_language,
                target_language=target_language,
                model=model_name,
                llm_client=llm_client,
                log_callback=log_callback,
                fast_mode=fast_mode,
                has_images=has_images,
                prompt_options=prompt_options,
                context_manager=context_manager
            )

            # Record success in context manager for adaptive learning
            if translated_chunk_text is not None and llm_response and context_manager:
                context_manager.record_success(
                    prompt_tokens=llm_response.prompt_tokens,
                    completion_tokens=llm_response.completion_tokens,
                    context_limit=llm_response.context_limit
                )

            if translated_chunk_text is not None:
                # Single point of cleaning - applies HTML entity cleanup and whitespace normalization
                # Note: Does NOT remove TAG placeholders - those are handled by EPUB processor
                # (placeholder format defined in src/core/epub/constants.py)
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


async def _make_refinement_request(
    draft_translation: str,
    context_before: str,
    context_after: str,
    previous_refined_context: str,
    target_language: str,
    model: str,
    llm_client,
    log_callback,
    fast_mode: bool,
    has_images: bool = False,
    prompt_options: dict = None,
    context_manager: AdaptiveContextManager = None
) -> Tuple[Optional[str], Optional[LLMResponse]]:
    """
    Make LLM request for refinement pass.

    Similar to translation request but uses the refinement prompt.

    Args:
        draft_translation: First-pass translation to refine
        context_before: Previously refined text for context
        context_after: Text appearing after for context
        previous_refined_context: Last refined text for consistency
        target_language: Target language
        model: LLM model name
        llm_client: LLM client instance
        log_callback: Logging callback function
        fast_mode: If True, uses simplified prompts
        has_images: If True, includes image placeholder preservation
        prompt_options: Optional dict with prompt customization options
        context_manager: AdaptiveContextManager for context sizing

    Returns:
        Tuple of (refined_text or None, LLMResponse)
    """
    try:
        # Generate refinement prompts
        prompt_pair = generate_refinement_prompt(
            draft_translation=draft_translation,
            context_before=context_before,
            context_after=context_after,
            previous_refined_context=previous_refined_context,
            target_language=target_language,
            fast_mode=fast_mode,
            has_images=has_images,
            prompt_options=prompt_options
        )

        # Log the request
        if log_callback:
            log_callback("refinement_request", "Sending refinement request to LLM", data={
                'type': 'refinement_request',
                'system_prompt': prompt_pair.system,
                'user_prompt': prompt_pair.user,
                'model': model
            })

        start_time = time.time()
        client = llm_client or default_client

        # Set context from manager if available
        if context_manager and hasattr(client, 'context_window'):
            new_ctx = context_manager.get_context_size()
            if client.context_window != new_ctx:
                client.context_window = new_ctx

        llm_response = await client.make_request(
            prompt_pair.user, model, system_prompt=prompt_pair.system
        )
        execution_time = time.time() - start_time

        if not llm_response:
            return None, None

        full_raw_response = llm_response.content

        # Log the response
        if log_callback:
            log_callback("refinement_response", "Refinement response received", data={
                'type': 'refinement_response',
                'response': full_raw_response,
                'execution_time': execution_time,
                'model': model,
                'tokens': {
                    'prompt': llm_response.prompt_tokens,
                    'completion': llm_response.completion_tokens,
                    'total': llm_response.context_used,
                    'limit': llm_response.context_limit
                }
            })

        # Extract refined text
        refined_text = client.extract_translation(full_raw_response)

        if refined_text:
            return refined_text, llm_response
        else:
            # Fallback to raw response if no tags found
            if draft_translation not in full_raw_response:
                return full_raw_response.strip(), llm_response
            else:
                if log_callback:
                    log_callback("refinement_warning",
                        "WARNING: Refinement response contains input. Using original.")
                return None, llm_response

    except (ContextOverflowError, RepetitionLoopError) as e:
        if log_callback:
            log_callback("refinement_error", f"Refinement error: {e}")
        return None, None


async def refine_chunks(
    translated_chunks: List[str],
    original_chunks: List[Dict],
    target_language: str,
    model_name: str,
    api_endpoint: str,
    progress_callback=None,
    log_callback=None,
    stats_callback=None,
    check_interruption_callback=None,
    llm_provider="ollama",
    gemini_api_key=None,
    openai_api_key=None,
    openrouter_api_key=None,
    context_window=2048,
    auto_adjust_context=True,
    fast_mode=False,
    has_images=False,
    prompt_options=None
) -> List[str]:
    """
    Refine translated chunks with a second pass for literary quality improvement.

    This function takes already-translated chunks and runs them through a
    refinement prompt that focuses on improving literary quality, natural flow,
    and stylistic excellence.

    Args:
        translated_chunks: List of translated text strings from first pass
        original_chunks: Original chunk dictionaries (for context structure)
        target_language: Target language name
        model_name: LLM model name
        api_endpoint: API endpoint
        progress_callback: Progress update callback
        log_callback: Logging callback
        stats_callback: Statistics update callback
        check_interruption_callback: Interruption check callback
        llm_provider: LLM provider name
        gemini_api_key: Gemini API key
        openai_api_key: OpenAI API key
        openrouter_api_key: OpenRouter API key
        context_window: Initial context window size
        auto_adjust_context: Enable adaptive context adjustment
        fast_mode: If True, uses simplified prompts
        has_images: If True, includes image placeholder preservation
        prompt_options: Optional dict with prompt customization options

    Returns:
        List of refined text strings
    """
    total_chunks = len(translated_chunks)
    refined_parts = []
    last_refined_context = ""
    completed_count = 0
    failed_count = 0

    if log_callback:
        log_callback("refinement_start", f"✨ Starting refinement pass ({total_chunks} chunks)...")

    # Determine if model is a thinking model for initial context sizing
    is_known_thinking_model = any(tm in model_name.lower() for tm in THINKING_MODELS)

    # Refinement needs MORE context than translation because:
    # - The prompt includes the already-translated text (input)
    # - Plus context before/after
    # - Plus instructions
    # So we start with at least 4096 or the user's context_window, whichever is larger
    REFINEMENT_MIN_CONTEXT = 4096

    if auto_adjust_context:
        if is_known_thinking_model:
            initial_context = max(ADAPTIVE_CONTEXT_INITIAL_THINKING, REFINEMENT_MIN_CONTEXT)
        else:
            initial_context = max(INITIAL_CONTEXT_SIZE * 2, REFINEMENT_MIN_CONTEXT)
    else:
        initial_context = max(context_window, REFINEMENT_MIN_CONTEXT)

    # Create LLM client
    llm_client = create_llm_client(
        llm_provider, gemini_api_key, api_endpoint, model_name,
        openai_api_key, openrouter_api_key,
        context_window=initial_context, log_callback=log_callback
    )

    # Create adaptive context manager for Ollama
    context_manager = None
    if llm_provider == "ollama" and auto_adjust_context:
        from .context_optimizer import MAX_CONTEXT_SIZE
        context_manager = AdaptiveContextManager(
            initial_context=initial_context,
            context_step=CONTEXT_STEP,
            max_context=MAX_CONTEXT_SIZE,
            log_callback=log_callback
        )
        if log_callback:
            log_callback("refinement_context", f"📐 Refinement context: starting at {initial_context} tokens (min for refinement: {REFINEMENT_MIN_CONTEXT})")

    # Detect thinking model status
    if llm_client and llm_provider == "ollama":
        await llm_client.detect_thinking_model()

    try:
        iterator = tqdm(
            enumerate(translated_chunks),
            total=total_chunks,
            desc=f"Refining {target_language} translation",
            unit="seg"
        ) if not log_callback else enumerate(translated_chunks)

        for i, draft_text in iterator:
            # Check for interruption
            if check_interruption_callback and check_interruption_callback():
                if log_callback:
                    log_callback("refinement_interrupted",
                        f"Refinement interrupted at chunk {i+1}/{total_chunks}")
                else:
                    tqdm.write(f"\nRefinement interrupted at chunk {i+1}/{total_chunks}")
                # Add remaining unrefined chunks as-is
                for remaining in translated_chunks[i:]:
                    refined_parts.append(remaining)
                break

            # Progress update
            if progress_callback and total_chunks > 0:
                # Refinement is second half of total progress (50-100%)
                progress = 50 + ((i / total_chunks) * 50)
                progress_callback(progress)

            # Skip empty chunks
            if not draft_text.strip():
                refined_parts.append(draft_text)
                completed_count += 1
                if stats_callback:
                    stats_callback({
                        'completed_chunks': completed_count,
                        'failed_chunks': failed_count,
                        'phase': 'refinement'
                    })
                continue

            # Skip very short content
            if len(draft_text.strip()) <= 1:
                refined_parts.append(draft_text)
                completed_count += 1
                continue

            # Get context from original chunks if available
            context_before = ""
            context_after = ""
            if i < len(original_chunks):
                context_before = original_chunks[i].get("context_before", "")
                context_after = original_chunks[i].get("context_after", "")

            # Make refinement request
            refined_text, llm_response = await _make_refinement_request(
                draft_translation=draft_text,
                context_before=context_before,
                context_after=context_after,
                previous_refined_context=last_refined_context,
                target_language=target_language,
                model=model_name,
                llm_client=llm_client,
                log_callback=log_callback,
                fast_mode=fast_mode,
                has_images=has_images,
                prompt_options=prompt_options,
                context_manager=context_manager
            )

            # Record success in context manager
            if refined_text is not None and llm_response and context_manager:
                context_manager.record_success(
                    prompt_tokens=llm_response.prompt_tokens,
                    completion_tokens=llm_response.completion_tokens,
                    context_limit=llm_response.context_limit
                )

            if refined_text is not None:
                # Clean the refined text
                refined_text = clean_translated_text(refined_text)
                refined_parts.append(refined_text)
                completed_count += 1

                # Update context for next chunk
                words = refined_text.split()
                if len(words) > 25:
                    last_refined_context = " ".join(words[-25:])
                else:
                    last_refined_context = refined_text
            else:
                # Keep original translation if refinement fails
                if log_callback:
                    log_callback("refinement_chunk_failed",
                        f"Refinement failed for chunk {i+1}, keeping original translation")
                refined_parts.append(draft_text)
                failed_count += 1
                last_refined_context = ""

            if stats_callback:
                stats_callback({
                    'completed_chunks': completed_count,
                    'failed_chunks': failed_count,
                    'phase': 'refinement'
                })

    finally:
        if llm_client:
            await llm_client.close()

    if log_callback:
        log_callback("refinement_complete",
            f"✨ Refinement complete: {completed_count} refined, {failed_count} kept original")

    return refined_parts


# Subtitle translation functions moved to subtitle_translator.py