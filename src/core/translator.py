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
from prompts import generate_translation_prompt, generate_subtitle_block_prompt, generate_post_processing_prompt
from .llm_client import default_client, LLMClient, create_llm_client
from .post_processor import clean_translated_text
from typing import List, Dict, Tuple, Optional




async def generate_translation_request(main_content, context_before, context_after, previous_translation_context,
                                       source_language="English", target_language="French", model=DEFAULT_MODEL,
                                       llm_client=None, log_callback=None, custom_instructions=""):
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
        api_endpoint_param (str): API endpoint to use
        log_callback (callable): Logging callback function
        custom_instructions (str): Additional translation instructions
        
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
        custom_instructions=custom_instructions
    )
    
    print("\n-------SENT to LLM-------")
    print(structured_prompt)
    print("-------SENT to LLM-------\n")

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

    print("\n-------LLM RESPONSE-------")
    print(full_raw_response)
    print("-------LLM RESPONSE-------\n")

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


async def post_process_translation(translated_text, target_language="French", model=DEFAULT_MODEL,
                                 llm_client=None, log_callback=None, custom_instructions="",
                                 tag_map=None):
    """
    Post-process translated text to improve quality
    
    Args:
        translated_text (str): Previously translated text to improve
        target_language (str): Target language
        model (str): LLM model name
        llm_client: LLM client instance
        log_callback (callable): Logging callback function
        custom_instructions (str): Additional improvement instructions
        tag_map (dict): Optional tag mapping for placeholder validation
        
    Returns:
        str: Improved text or original if post-processing fails
    """
    # Skip post-processing for very short text
    if len(translated_text.strip()) <= 1:
        return translated_text
    
    # Import TagPreserver for placeholder validation
    from .epub_processor import TagPreserver
    
    # Check for placeholders in input if tag_map provided
    has_placeholders = tag_map is not None and len(tag_map) > 0
    
    structured_prompt = generate_post_processing_prompt(
        translated_text,
        target_language,
        custom_instructions=custom_instructions
    )
    
    print("\n-------POST-PROCESSING SENT to LLM-------")
    print(structured_prompt)
    print("-------POST-PROCESSING SENT to LLM-------\n")
    
    start_time = time.time()
    
    # Use provided client or default
    client = llm_client or default_client
    full_raw_response = await client.make_request(structured_prompt, model)
    execution_time = time.time() - start_time
    
    if not full_raw_response:
        err_msg = "ERROR: Post-processing LLM API request failed"
        if log_callback:
            log_callback("post_process_api_error", err_msg)
        else:
            tqdm.write(f"\n{err_msg}")
        return translated_text  # Return original if post-processing fails
    
    print("\n-------POST-PROCESSING LLM RESPONSE-------")
    print(full_raw_response)
    print("-------POST-PROCESSING LLM RESPONSE-------\n")
    
    improved_text = client.extract_translation(full_raw_response)
    
    if improved_text:
        # Validate placeholders if we have a tag map
        if has_placeholders:
            tag_preserver = TagPreserver()
            is_valid, missing, mutated = tag_preserver.validate_placeholders(improved_text, tag_map)
            
            if not is_valid:
                if log_callback:
                    log_callback("post_process_placeholder_validation_failed", 
                               f"Post-processing placeholder validation failed. Missing: {missing}, Mutated: {mutated}")
                
                # Try to fix mutated placeholders
                if mutated:
                    improved_text = tag_preserver.fix_mutated_placeholders(improved_text, mutated)
                    is_valid, missing, mutated = tag_preserver.validate_placeholders(improved_text, tag_map)
                
                # If still missing placeholders, retry with stronger instructions
                if not is_valid and missing:
                    if log_callback:
                        log_callback("post_process_retrying", 
                                   f"Retrying post-processing due to missing placeholders: {missing}")
                    
                    retry_instructions = (f"{custom_instructions}\n\n"
                                        f"CRITICAL: You MUST preserve ALL placeholder tags EXACTLY as they appear. "
                                        f"Tags like ⟦TAG0⟧, ⟦TAG1⟧, etc. must remain COMPLETELY UNCHANGED. "
                                        f"Missing tags that MUST be preserved: {', '.join(missing)}")
                    
                    retry_prompt = generate_post_processing_prompt(
                        translated_text,
                        target_language,
                        custom_instructions=retry_instructions
                    )
                    
                    retry_response = await client.make_request(retry_prompt, model)
                    
                    if retry_response:
                        retry_text = client.extract_translation(retry_response)
                        if retry_text:
                            # Validate retry
                            is_valid_retry, missing_retry, mutated_retry = tag_preserver.validate_placeholders(retry_text, tag_map)
                            
                            if is_valid_retry or (not missing_retry):
                                improved_text = retry_text
                                if log_callback:
                                    log_callback("post_process_retry_successful", 
                                               "Post-processing retry successful - placeholders preserved")
                            else:
                                # If retry still failed, use original to avoid losing placeholders
                                if log_callback:
                                    log_callback("post_process_retry_failed", 
                                               f"Post-processing retry failed - using original. Still missing: {missing_retry}")
                                return translated_text
        
        # Apply post-processor cleaning
        cleaned_text = clean_translated_text(improved_text)
        return cleaned_text
    else:
        warn_msg = "WARNING: Post-processing tags missing in LLM response. Using original."
        if log_callback:
            log_callback("post_process_tag_warning", warn_msg)
        else:
            tqdm.write(f"\n{warn_msg}")
        return translated_text  # Return original if extraction fails


async def translate_chunks(chunks, source_language, target_language, model_name,
                          api_endpoint, progress_callback=None, log_callback=None,
                          stats_callback=None, check_interruption_callback=None, custom_instructions="",
                          llm_provider="ollama", gemini_api_key=None, openai_api_key=None,
                          enable_post_processing=False, post_processing_instructions=""):
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
        
    Returns:
        list: List of translated chunks
    """
    total_chunks = len(chunks)
    full_translation_parts = []
    last_successful_llm_context = ""
    completed_chunks_count = 0
    failed_chunks_count = 0

    if log_callback: 
        log_callback("txt_translation_loop_start", "Starting segment translation...")

    # Create LLM client based on provider or custom endpoint
    llm_client = create_llm_client(llm_provider, gemini_api_key, api_endpoint, model_name, openai_api_key)

    try:
        iterator = tqdm(chunks, desc=f"Translating {source_language} to {target_language}", unit="seg") if not log_callback else chunks

        for i, chunk_data in enumerate(iterator):
            if check_interruption_callback and check_interruption_callback():
                if log_callback: 
                    log_callback("txt_translation_interrupted", f"Translation process for segment {i+1}/{total_chunks} interrupted by user signal.")
                else: 
                    tqdm.write(f"\nTranslation interrupted by user at segment {i+1}/{total_chunks}.")
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
                continue

            translated_chunk_text = await generate_translation_request(
                main_content_to_translate, context_before_text, context_after_text,
                last_successful_llm_context, source_language, target_language,
                model_name, llm_client=llm_client, log_callback=log_callback,
                custom_instructions=custom_instructions
            )

            if translated_chunk_text is not None:
                # Apply post-processing if enabled
                if enable_post_processing:
                    if log_callback:
                        log_callback("post_processing_chunk", f"Post-processing chunk {i+1}/{total_chunks}")
                    
                    improved_text = await post_process_translation(
                        translated_chunk_text,
                        target_language,
                        model_name,
                        llm_client=llm_client,
                        log_callback=log_callback,
                        custom_instructions=post_processing_instructions
                    )
                    translated_chunk_text = improved_text
                else:
                    # Always apply basic cleaning even without post-processing
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
    
    finally:
        # Clean up LLM client resources if created
        if llm_client:
            await llm_client.close()

    return full_translation_parts


# Subtitle translation functions moved to subtitle_translator.py