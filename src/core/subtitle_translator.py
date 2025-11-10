"""
Subtitle-specific translation module
"""
from typing import List, Dict, Optional
from tqdm.auto import tqdm

from prompts import generate_subtitle_block_prompt
from src.config import TRANSLATE_TAG_IN, TRANSLATE_TAG_OUT
from .llm_client import create_llm_client
from .post_processor import clean_translated_text
from .translator import generate_translation_request
from .epub import TagPreserver


async def translate_subtitles(subtitles: List[Dict[str, str]], source_language: str,
                            target_language: str, model_name: str, api_endpoint: str,
                            progress_callback=None, log_callback=None,
                            stats_callback=None, check_interruption_callback=None, custom_instructions="",
                            llm_provider="ollama", gemini_api_key=None, openai_api_key=None,
                            enable_post_processing=False, post_processing_instructions="") -> Dict[int, str]:
    """
    Translate subtitle entries preserving structure
    
    Args:
        subtitles (list): List of subtitle dictionaries from SRT parser
        source_language (str): Source language
        target_language (str): Target language
        model_name (str): LLM model name
        api_endpoint (str): API endpoint
        progress_callback (callable): Progress update callback
        log_callback (callable): Logging callback
        stats_callback (callable): Statistics update callback
        check_interruption_callback (callable): Interruption check callback
        
    Returns:
        dict: Mapping of subtitle index to translated text
    """
    total_subtitles = len(subtitles)
    translations = {}
    completed_count = 0
    failed_count = 0
    
    if log_callback:
        log_callback("srt_translation_start", f"Starting translation of {total_subtitles} subtitles...")
    
    # Create LLM client based on provider or custom endpoint
    llm_client = create_llm_client(llm_provider, gemini_api_key, api_endpoint, model_name, openai_api_key)
    
    try:
        iterator = tqdm(enumerate(subtitles), total=total_subtitles, 
                       desc=f"Translating subtitles ({source_language} to {target_language})", 
                       unit="subtitle") if not log_callback else enumerate(subtitles)
        
        for idx, subtitle in iterator:
            if check_interruption_callback and check_interruption_callback():
                if log_callback:
                    log_callback("srt_translation_interrupted", 
                               f"Translation interrupted at subtitle {idx+1}/{total_subtitles}")
                else:
                    tqdm.write(f"\nTranslation interrupted at subtitle {idx+1}/{total_subtitles}")
                break
            
            if progress_callback and total_subtitles > 0:
                progress_callback((idx / total_subtitles) * 100)
            
            text_to_translate = subtitle['text'].strip()
            
            if not text_to_translate:
                translations[idx] = ""
                completed_count += 1
                continue
            
            context_before = ""
            context_after = ""
            
            if idx > 0 and idx-1 in translations:
                context_before = translations[idx-1]
            elif idx > 0:
                context_before = subtitles[idx-1].get('text', '')
            
            if idx < len(subtitles) - 1:
                context_after = subtitles[idx+1].get('text', '')
            
            translated_text = await generate_translation_request(
                text_to_translate,
                context_before,
                context_after,
                "",
                source_language,
                target_language,
                model_name,
                llm_client=llm_client,
                log_callback=log_callback,
                custom_instructions=custom_instructions
            )
            
            if translated_text is not None:
                translations[idx] = translated_text
                completed_count += 1
            else:
                # Keep original text if translation fails
                err_msg = f"Failed to translate subtitle {idx+1}"
                if log_callback:
                    log_callback("srt_subtitle_error", err_msg)
                else:
                    tqdm.write(f"\n{err_msg}")
                translations[idx] = text_to_translate  # Keep original
                failed_count += 1
            
            if stats_callback and total_subtitles > 0:
                stats_callback({
                    'completed_subtitles': completed_count,
                    'failed_subtitles': failed_count,
                    'total_subtitles': total_subtitles
                })
    
        if log_callback:
            log_callback("srt_translation_complete", 
                        f"Completed translation: {completed_count} successful, {failed_count} failed")
    
    finally:
        # Clean up LLM client resources if created
        if llm_client:
            await llm_client.close()
    
    return translations


async def translate_subtitles_in_blocks(subtitle_blocks: List[List[Dict[str, str]]],
                                      source_language: str, target_language: str,
                                      model_name: str, api_endpoint: str,
                                      progress_callback=None, log_callback=None,
                                      stats_callback=None, check_interruption_callback=None,
                                      custom_instructions="", llm_provider="ollama",
                                      gemini_api_key=None, openai_api_key=None,
                                      enable_post_processing=False,
                                      post_processing_instructions="") -> Dict[int, str]:
    """
    Translate subtitle entries in blocks for better context preservation.
    
    Args:
        subtitle_blocks: List of subtitle blocks (each block is a list of subtitle dicts)
        source_language: Source language
        target_language: Target language
        model_name: LLM model name
        api_endpoint: API endpoint
        progress_callback: Progress update callback
        log_callback: Logging callback
        stats_callback: Statistics update callback
        check_interruption_callback: Interruption check callback
        custom_instructions: Additional translation instructions
        
    Returns:
        dict: Mapping of subtitle index to translated text
    """
    from src.core.srt_processor import SRTProcessor
    from .llm_client import default_client
    
    srt_processor = SRTProcessor()
    
    total_blocks = len(subtitle_blocks)
    total_subtitles = sum(len(block) for block in subtitle_blocks)
    translations = {}
    completed_count = 0
    failed_count = 0
    previous_translation_block = ""
    
    if log_callback:
        log_callback("srt_block_translation_start", 
                    f"Starting block translation: {total_subtitles} subtitles in {total_blocks} blocks...")
    
    # Create LLM client based on provider or custom endpoint
    llm_client = create_llm_client(llm_provider, gemini_api_key, api_endpoint, model_name, openai_api_key)
    
    try:
        for block_idx, block in enumerate(subtitle_blocks):
            if check_interruption_callback and check_interruption_callback():
                if log_callback:
                    log_callback("srt_translation_interrupted", 
                               f"Translation interrupted at block {block_idx+1}/{total_blocks}")
                else:
                    tqdm.write(f"\nTranslation interrupted at block {block_idx+1}/{total_blocks}")
                break
            
            if progress_callback and total_blocks > 0:
                progress_callback((block_idx / total_blocks) * 100)
            
            # Prepare subtitle blocks with indices
            subtitle_tuples = []
            block_indices = []
            
            for subtitle in block:
                idx = int(subtitle['number']) - 1  # Convert to 0-based index
                text = subtitle['text'].strip()
                if text:  # Only include non-empty subtitles
                    subtitle_tuples.append((idx, text))
                    block_indices.append(idx)
            
            if not subtitle_tuples:
                continue
            
            # Generate prompt for this block
            prompt = generate_subtitle_block_prompt(
                subtitle_tuples,
                previous_translation_block,
                source_language,
                target_language,
                TRANSLATE_TAG_IN,
                TRANSLATE_TAG_OUT,
                custom_instructions
            )
            
            # Make translation request using LLM client with retry mechanism
            max_retries = 3
            retry_count = 0
            translated_block_text = None
            
            while retry_count < max_retries:
                try:
                    if retry_count > 0 and log_callback:
                        log_callback("srt_block_retry", f"Retry attempt {retry_count} for block {block_idx+1}")
                    
                    print("\n-------SENT to LLM-------")
                    print(prompt)
                    print("-------SENT to LLM-------\n")
                    
                    # Use provided client or default
                    client = llm_client or default_client
                    full_raw_response = await client.make_request(prompt, model_name)
                    
                    print("\n-------LLM RESPONSE-------")
                    print(full_raw_response or "None")
                    print("-------LLM RESPONSE-------\n")
                    
                    if full_raw_response:
                        translated_block_text = client.extract_translation(full_raw_response)
                        
                        # Validate placeholder tags if translation succeeded
                        if translated_block_text:
                            # Check if all expected [NUMBER] tags are present
                            expected_tags = set(f"[{idx}]" for idx in block_indices)
                            found_tags = set()
                            import re
                            for match in re.finditer(r'\[(\d+)\]', translated_block_text):
                                found_tags.add(match.group(0))
                            
                            missing_tags = expected_tags - found_tags
                            
                            if missing_tags:
                                if log_callback:
                                    log_callback("srt_placeholder_validation_failed", 
                                               f"Block {block_idx+1} missing tags: {missing_tags}")
                                
                                if retry_count < max_retries - 1:
                                    # Enhance prompt with stronger instructions about preserving tags
                                    prompt = generate_subtitle_block_prompt(
                                        subtitle_tuples,
                                        previous_translation_block,
                                        source_language,
                                        target_language,
                                        TRANSLATE_TAG_IN,
                                        TRANSLATE_TAG_OUT,
                                        custom_instructions + f"\n\nCRITICAL: You MUST preserve ALL [NUMBER] tags EXACTLY as they appear. Missing tags: {', '.join(missing_tags)}"
                                    )
                                    retry_count += 1
                                    continue
                                else:
                                    # Final retry failed, will use original text
                                    translated_block_text = None
                                    break
                            else:
                                # All tags present, translation successful
                                if retry_count > 0 and log_callback:
                                    log_callback("srt_retry_successful", 
                                               f"Block {block_idx+1} translation successful after {retry_count} retries")
                                break
                        else:
                            # No translation extracted
                            if retry_count < max_retries - 1:
                                retry_count += 1
                                continue
                            else:
                                break
                    else:
                        translated_block_text = None
                        if retry_count < max_retries - 1:
                            retry_count += 1
                            continue
                        else:
                            break
                            
                except Exception as e:
                    if log_callback:
                        log_callback("srt_block_translation_error", f"Error: {str(e)}")
                    translated_block_text = None
                    if retry_count < max_retries - 1:
                        retry_count += 1
                        continue
                    else:
                        break
            
            if translated_block_text:
                # Extract individual translations from block
                block_translations = srt_processor.extract_block_translations(
                    translated_block_text, block_indices
                )
                
                # Update translations dictionary
                for idx, trans_text in block_translations.items():
                    translations[idx] = trans_text
                    completed_count += 1
                
                # Track failed translations in block
                for idx in block_indices:
                    if idx not in block_translations:
                        # Keep original text for missing translations
                        for subtitle in block:
                            if int(subtitle['number']) - 1 == idx:
                                translations[idx] = subtitle['text']
                                failed_count += 1
                                break
                
                # Store translated block for context (last 5 subtitles)
                last_subtitles = []
                for idx in sorted(block_translations.keys())[-5:]:
                    last_subtitles.append(f"[{idx}]{block_translations[idx]}")
                previous_translation_block = '\n'.join(last_subtitles)
                
            else:
                # Block translation failed - keep original text
                err_msg = f"Failed to translate block {block_idx+1}"
                if log_callback:
                    log_callback("srt_block_error", err_msg)
                else:
                    tqdm.write(f"\n{err_msg}")
                
                for subtitle in block:
                    idx = int(subtitle['number']) - 1
                    translations[idx] = subtitle['text']
                    failed_count += 1
                
                previous_translation_block = ""  # Reset context on failure
            
            if stats_callback and total_subtitles > 0:
                stats_callback({
                    'completed_subtitles': completed_count,
                    'failed_subtitles': failed_count,
                    'total_subtitles': total_subtitles,
                    'completed_blocks': block_idx + 1,
                    'total_blocks': total_blocks
                })
        
        if log_callback:
            log_callback("srt_block_translation_complete", 
                        f"Completed block translation: {completed_count} successful, {failed_count} failed")
    
    finally:
        # Clean up LLM client resources if created
        if llm_client:
            await llm_client.close()
    
    return translations