"""
File utilities for translation operations
"""
import os
import asyncio
import aiofiles
from src.core.text_processor import split_text_into_chunks_with_context
from src.core.translator import translate_chunks
from src.core.subtitle_translator import translate_subtitles, translate_subtitles_in_blocks
from src.core.epub import translate_epub_file
from src.core.srt_processor import SRTProcessor
from src.config import DEFAULT_MODEL, MAIN_LINES_PER_CHUNK, API_ENDPOINT, SRT_LINES_PER_BLOCK, SRT_MAX_CHARS_PER_BLOCK


async def translate_text_file_with_callbacks(input_filepath, output_filepath,
                                             source_language="English", target_language="French",
                                             model_name=DEFAULT_MODEL, chunk_target_lines_cli=MAIN_LINES_PER_CHUNK,
                                             cli_api_endpoint=API_ENDPOINT,
                                             progress_callback=None, log_callback=None, stats_callback=None,
                                             check_interruption_callback=None, custom_instructions="",
                                             llm_provider="ollama", gemini_api_key=None, openai_api_key=None,
                                             enable_post_processing=False, post_processing_instructions="",
                                             context_window=2048, auto_adjust_context=True, min_chunk_size=5):
    """
    Translate a text file with callback support
    
    Args:
        input_filepath (str): Path to input file
        output_filepath (str): Path to output file
        source_language (str): Source language
        target_language (str): Target language
        model_name (str): LLM model name
        chunk_target_lines_cli (int): Target lines per chunk
        cli_api_endpoint (str): API endpoint
        progress_callback (callable): Progress callback
        log_callback (callable): Logging callback
        stats_callback (callable): Statistics callback
        check_interruption_callback (callable): Interruption check callback
    """
    if not os.path.exists(input_filepath):
        err_msg = f"ERROR: Input file '{input_filepath}' not found."
        if log_callback: 
            log_callback("file_not_found_error", err_msg)
        else: 
            print(err_msg)
        return

    try:
        async with aiofiles.open(input_filepath, 'r', encoding='utf-8') as f:
            original_text = await f.read()
    except Exception as e:
        err_msg = f"ERROR: Reading input file '{input_filepath}': {e}"
        if log_callback: 
            log_callback("file_read_error", err_msg)
        else: 
            print(err_msg)
        return

    if log_callback: 
        log_callback("txt_split_start", f"Splitting text from '{source_language}'...")

    structured_chunks = split_text_into_chunks_with_context(original_text, chunk_target_lines_cli)
    total_chunks = len(structured_chunks)

    if stats_callback and total_chunks > 0:
        stats_callback({'total_chunks': total_chunks, 'completed_chunks': 0, 'failed_chunks': 0})

    if total_chunks == 0 and original_text.strip():
        warn_msg = "WARNING: No segments generated for non-empty text. Processing as a single block."
        if log_callback: 
            log_callback("txt_no_chunks_warning", warn_msg)
        structured_chunks = [{"context_before": "", "main_content": original_text, "context_after": ""}]
        total_chunks = 1
        if stats_callback: 
            stats_callback({'total_chunks': 1, 'completed_chunks': 0, 'failed_chunks': 0})
    elif total_chunks == 0:
        info_msg = "Empty input file. No translation needed."
        if log_callback: 
            log_callback("txt_empty_input", info_msg)
        try:
            async with aiofiles.open(output_filepath, 'w', encoding='utf-8') as f: 
                await f.write("")
            if log_callback: 
                log_callback("txt_empty_output_created", f"Empty output file '{output_filepath}' created.")
        except Exception as e:
            err_msg = f"ERROR: Saving empty file '{output_filepath}': {e}"
            if log_callback: 
                log_callback("txt_empty_save_error", err_msg)
        if progress_callback: 
            progress_callback(100)
        return

    if log_callback:
        log_callback("txt_translation_info_lang", f"Translating from {source_language} to {target_language}.")
        log_callback("txt_translation_info_chunks1", f"{total_chunks} main segments in memory.")
        log_callback("txt_translation_info_chunks2", f"Target size per segment: ~{chunk_target_lines_cli} lines.")

    # Translate chunks
    translated_parts = await translate_chunks(
        structured_chunks,
        source_language,
        target_language,
        model_name,
        cli_api_endpoint,
        progress_callback=progress_callback,
        log_callback=log_callback,
        stats_callback=stats_callback,
        check_interruption_callback=check_interruption_callback,
        custom_instructions=custom_instructions,
        llm_provider=llm_provider,
        gemini_api_key=gemini_api_key,
        openai_api_key=openai_api_key,
        enable_post_processing=enable_post_processing,
        post_processing_instructions=post_processing_instructions,
        context_window=context_window,
        auto_adjust_context=auto_adjust_context,
        min_chunk_size=min_chunk_size
    )

    if progress_callback: 
        progress_callback(100)

    final_translated_text = "\n".join(translated_parts)
    try:
        async with aiofiles.open(output_filepath, 'w', encoding='utf-8') as f:
            await f.write(final_translated_text)
        success_msg = f"Full/Partial translation saved: '{output_filepath}'"
        if log_callback: 
            log_callback("txt_save_success", success_msg)
    except Exception as e:
        err_msg = f"ERROR: Saving output file '{output_filepath}': {e}"
        if log_callback: 
            log_callback("txt_save_error", err_msg)
        else: 
            print(err_msg)


async def translate_srt_file_with_callbacks(input_filepath, output_filepath,
                                           source_language="English", target_language="French",
                                           model_name=DEFAULT_MODEL, chunk_target_lines_cli=MAIN_LINES_PER_CHUNK,
                                           cli_api_endpoint=API_ENDPOINT,
                                           progress_callback=None, log_callback=None, stats_callback=None,
                                           check_interruption_callback=None, custom_instructions="",
                                           llm_provider="ollama", gemini_api_key=None, openai_api_key=None,
                                           enable_post_processing=False, post_processing_instructions=""):
    """
    Translate an SRT subtitle file with callback support
    
    Args:
        input_filepath (str): Path to input SRT file
        output_filepath (str): Path to output SRT file
        source_language (str): Source language
        target_language (str): Target language
        model_name (str): LLM model name
        chunk_target_lines_cli (int): Not used for SRT (kept for consistency)
        cli_api_endpoint (str): API endpoint
        progress_callback (callable): Progress callback
        log_callback (callable): Logging callback
        stats_callback (callable): Statistics callback
        check_interruption_callback (callable): Interruption check callback
    """
    if not os.path.exists(input_filepath):
        err_msg = f"ERROR: SRT file '{input_filepath}' not found."
        if log_callback:
            log_callback("srt_file_not_found", err_msg)
        else:
            print(err_msg)
        return
    
    # Initialize SRT processor
    srt_processor = SRTProcessor()
    
    # Read SRT file
    try:
        async with aiofiles.open(input_filepath, 'r', encoding='utf-8') as f:
            srt_content = await f.read()
    except Exception as e:
        err_msg = f"ERROR: Reading SRT file '{input_filepath}': {e}"
        if log_callback:
            log_callback("srt_read_error", err_msg)
        else:
            print(err_msg)
        return
    
    # Validate SRT format
    if not srt_processor.validate_srt(srt_content):
        err_msg = "Invalid SRT file format"
        if log_callback:
            log_callback("srt_invalid_format", err_msg)
        else:
            print(err_msg)
        return
    
    # Parse SRT file
    if log_callback:
        log_callback("srt_parse_start", "Parsing SRT file...")
    
    subtitles = srt_processor.parse_srt(srt_content)
    
    if not subtitles:
        err_msg = "No subtitles found in file"
        if log_callback:
            log_callback("srt_no_subtitles", err_msg)
        else:
            print(err_msg)
        return
    
    if log_callback:
        log_callback("srt_parse_complete", f"Parsed {len(subtitles)} subtitles")
    
    # Update stats
    if stats_callback:
        stats_callback({
            'total_subtitles': len(subtitles),
            'completed_subtitles': 0,
            'failed_subtitles': 0
        })
    
    # Group subtitles into blocks for translation
    if log_callback:
        log_callback("srt_grouping", f"Grouping {len(subtitles)} subtitles into blocks...")
    
    # Use SRT-specific configuration for block sizes
    lines_per_block = SRT_LINES_PER_BLOCK
    subtitle_blocks = srt_processor.group_subtitles_for_translation(
        subtitles, 
        lines_per_block=lines_per_block,
        max_chars_per_block=SRT_MAX_CHARS_PER_BLOCK
    )
    
    if log_callback:
        log_callback("srt_translation_start", 
                    f"Translating {len(subtitles)} subtitles in {len(subtitle_blocks)} blocks from {source_language} to {target_language}...")
    
    translations = await translate_subtitles_in_blocks(
        subtitle_blocks,
        source_language,
        target_language,
        model_name,
        cli_api_endpoint,
        progress_callback=progress_callback,
        log_callback=log_callback,
        stats_callback=stats_callback,
        check_interruption_callback=check_interruption_callback,
        custom_instructions=custom_instructions,
        llm_provider=llm_provider,
        gemini_api_key=gemini_api_key,
        openai_api_key=openai_api_key,
        enable_post_processing=enable_post_processing,
        post_processing_instructions=post_processing_instructions
    )
    
    # Update subtitles with translations
    translated_subtitles = srt_processor.update_translated_subtitles(subtitles, translations)
    
    # Reconstruct SRT file
    if log_callback:
        log_callback("srt_reconstruct", "Reconstructing SRT file...")
    
    translated_srt = srt_processor.reconstruct_srt(translated_subtitles)
    
    # Save translated SRT
    try:
        async with aiofiles.open(output_filepath, 'w', encoding='utf-8') as f:
            await f.write(translated_srt)
        success_msg = f"SRT translation saved: '{output_filepath}'"
        if log_callback:
            log_callback("srt_save_success", success_msg)
        else:
            print(success_msg)
    except Exception as e:
        err_msg = f"ERROR: Saving SRT file '{output_filepath}': {e}"
        if log_callback:
            log_callback("srt_save_error", err_msg)
        else:
            print(err_msg)
    
    if progress_callback:
        progress_callback(100)


async def translate_file(input_filepath, output_filepath,
                        source_language="English", target_language="French",
                        model_name=DEFAULT_MODEL, chunk_target_size_cli=MAIN_LINES_PER_CHUNK,
                        cli_api_endpoint=API_ENDPOINT,
                        progress_callback=None, log_callback=None, stats_callback=None,
                        check_interruption_callback=None, custom_instructions="",
                        llm_provider="ollama", gemini_api_key=None, openai_api_key=None,
                        enable_post_processing=False, post_processing_instructions="",
                        context_window=2048, auto_adjust_context=True, min_chunk_size=5):
    """
    Translate a file (auto-detect format)
    
    Args:
        input_filepath (str): Path to input file
        output_filepath (str): Path to output file
        source_language (str): Source language
        target_language (str): Target language
        model_name (str): LLM model name
        chunk_target_size_cli (int): Target chunk size
        cli_api_endpoint (str): API endpoint
        progress_callback (callable): Progress callback
        log_callback (callable): Logging callback
        stats_callback (callable): Statistics callback
        check_interruption_callback (callable): Interruption check callback
    """
    _, ext = os.path.splitext(input_filepath.lower())

    if ext == '.epub':
        await translate_epub_file(input_filepath, output_filepath,
                                  source_language, target_language,
                                  model_name, chunk_target_size_cli,
                                  cli_api_endpoint,
                                  progress_callback, log_callback, stats_callback,
                                  check_interruption_callback=check_interruption_callback,
                                  custom_instructions=custom_instructions,
                                  llm_provider=llm_provider,
                                  gemini_api_key=gemini_api_key,
                                  openai_api_key=openai_api_key,
                                  enable_post_processing=enable_post_processing,
                                  post_processing_instructions=post_processing_instructions)
    elif ext == '.srt':
        await translate_srt_file_with_callbacks(
            input_filepath, output_filepath,
            source_language, target_language,
            model_name, chunk_target_size_cli,
            cli_api_endpoint,
            progress_callback, log_callback, stats_callback,
            check_interruption_callback=check_interruption_callback,
            custom_instructions=custom_instructions,
            llm_provider=llm_provider,
            gemini_api_key=gemini_api_key,
            openai_api_key=openai_api_key,
            enable_post_processing=enable_post_processing,
            post_processing_instructions=post_processing_instructions
        )
    else:
        await translate_text_file_with_callbacks(
            input_filepath, output_filepath,
            source_language, target_language,
            model_name, chunk_target_size_cli,
            cli_api_endpoint,
            progress_callback, log_callback, stats_callback,
            check_interruption_callback=check_interruption_callback,
            custom_instructions=custom_instructions,
            llm_provider=llm_provider,
            gemini_api_key=gemini_api_key,
            openai_api_key=openai_api_key,
            enable_post_processing=enable_post_processing,
            post_processing_instructions=post_processing_instructions,
            context_window=context_window,
            auto_adjust_context=auto_adjust_context,
            min_chunk_size=min_chunk_size
        )