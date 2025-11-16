"""
File utilities for translation operations
"""
import os
import asyncio
import aiofiles
from pathlib import Path
from src.core.text_processor import (
    split_text_into_chunks_with_context,
    split_text_into_chunks_character_based,
    get_chunking_method
)
from src.core.translator import translate_chunks, report_chunk_statistics
from src.core.subtitle_translator import translate_subtitles, translate_subtitles_in_blocks
from src.core.epub import translate_epub_file
from src.core.srt_processor import SRTProcessor
from src.config import (
    DEFAULT_MODEL, MAIN_LINES_PER_CHUNK, API_ENDPOINT, SRT_LINES_PER_BLOCK, SRT_MAX_CHARS_PER_BLOCK,
    ENABLE_CHARACTER_CHUNKING, CHUNK_SIZE_CHARS, CHUNK_TOLERANCE
)


def get_unique_output_path(output_path):
    """
    Generate a unique output path by adding a number suffix if the file already exists.

    Args:
        output_path (str): Desired output path

    Returns:
        str: Unique output path (original or with numeric suffix)

    Examples:
        book.epub -> book.epub (if doesn't exist)
        book.epub -> book (1).epub (if book.epub exists)
        book.epub -> book (2).epub (if book.epub and book (1).epub exist)
    """
    path = Path(output_path)

    # If the file doesn't exist, return the original path
    if not path.exists():
        return output_path

    # Extract components
    parent = path.parent
    stem = path.stem  # filename without extension
    suffix = path.suffix  # .epub, .txt, .srt, etc.

    # Try incrementing numbers until we find a free filename
    counter = 1
    while True:
        new_stem = f"{stem} ({counter})"
        new_path = parent / f"{new_stem}{suffix}"

        if not new_path.exists():
            return str(new_path)

        counter += 1

        # Safety check to avoid infinite loops (highly unlikely)
        if counter > 9999:
            raise RuntimeError(f"Could not find unique filename after 9999 attempts for: {output_path}")


async def translate_text_file_with_callbacks(input_filepath, output_filepath,
                                             source_language="English", target_language="Chinese",
                                             model_name=DEFAULT_MODEL, chunk_target_lines_cli=MAIN_LINES_PER_CHUNK,
                                             cli_api_endpoint=API_ENDPOINT,
                                             progress_callback=None, log_callback=None, stats_callback=None,
                                             check_interruption_callback=None,
                                             llm_provider="ollama", gemini_api_key=None, openai_api_key=None,
                                             context_window=2048, auto_adjust_context=True, min_chunk_size=5,
                                             fast_mode=False, checkpoint_manager=None, translation_id=None,
                                             resume_from_index=0,
                                             enable_character_chunking=None, chunk_size_chars=None,
                                             chunk_tolerance=None):
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
        fast_mode (bool): If True, uses simplified prompts without placeholder instructions
        enable_character_chunking (bool): Enable character-based chunking (T053)
        chunk_size_chars (int): Target chunk size in characters
        chunk_tolerance (float): Tolerance for chunk size
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

    # T053: Feature flag check for character-based chunking
    # T054: Backward compatibility with line-based chunking fallback
    chunking_stats = None
    use_char_chunking = enable_character_chunking if enable_character_chunking is not None else ENABLE_CHARACTER_CHUNKING

    if use_char_chunking:
        # Use new character-based chunking
        target_size = chunk_size_chars if chunk_size_chars is not None else CHUNK_SIZE_CHARS
        tolerance = chunk_tolerance if chunk_tolerance is not None else CHUNK_TOLERANCE

        if log_callback:
            log_callback("txt_chunking_mode", f"Using character-based chunking (target: {target_size} chars)")

        structured_chunks, chunking_stats = split_text_into_chunks_character_based(
            original_text, target_size=target_size, tolerance=tolerance
        )

        # Report chunk statistics (T049)
        if chunking_stats:
            report_chunk_statistics(chunking_stats, log_callback)

    else:
        # Fallback to legacy line-based chunking
        if log_callback:
            log_callback("txt_chunking_mode", f"Using line-based chunking (target: {chunk_target_lines_cli} lines)")

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
        if use_char_chunking:
            target_size = chunk_size_chars if chunk_size_chars is not None else CHUNK_SIZE_CHARS
            log_callback("txt_translation_info_chunks2", f"Target size per segment: ~{target_size} characters.")
        else:
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
        llm_provider=llm_provider,
        gemini_api_key=gemini_api_key,
        openai_api_key=openai_api_key,
        context_window=context_window,
        auto_adjust_context=auto_adjust_context,
        min_chunk_size=min_chunk_size,
        fast_mode=fast_mode,
        checkpoint_manager=checkpoint_manager,
        translation_id=translation_id,
        resume_from_index=resume_from_index
    )

    if progress_callback:
        progress_callback(100)

    # Add signature footer if enabled
    from src.config import SIGNATURE_ENABLED, PROJECT_NAME, PROJECT_GITHUB

    final_translated_text = "\n".join(translated_parts)

    if SIGNATURE_ENABLED:
        signature_footer = f"\n\n{'='*60}\n"
        signature_footer += f"Translated with {PROJECT_NAME}\n"
        signature_footer += f"{PROJECT_GITHUB}\n"
        signature_footer += f"{'='*60}\n"
        final_translated_text += signature_footer

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
                                           source_language="English", target_language="Chinese",
                                           model_name=DEFAULT_MODEL, chunk_target_lines_cli=MAIN_LINES_PER_CHUNK,
                                           cli_api_endpoint=API_ENDPOINT,
                                           progress_callback=None, log_callback=None, stats_callback=None,
                                           check_interruption_callback=None,
                                           llm_provider="ollama", gemini_api_key=None, openai_api_key=None,
                                           checkpoint_manager=None, translation_id=None, resume_from_block_index=0):
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
        llm_provider=llm_provider,
        gemini_api_key=gemini_api_key,
        openai_api_key=openai_api_key,
        checkpoint_manager=checkpoint_manager,
        translation_id=translation_id,
        resume_from_block_index=resume_from_block_index
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
                        source_language="English", target_language="Chinese",
                        model_name=DEFAULT_MODEL, chunk_target_size_cli=MAIN_LINES_PER_CHUNK,
                        cli_api_endpoint=API_ENDPOINT,
                        progress_callback=None, log_callback=None, stats_callback=None,
                        check_interruption_callback=None,
                        llm_provider="ollama", gemini_api_key=None, openai_api_key=None,
                        context_window=2048, auto_adjust_context=True, min_chunk_size=5,
                        fast_mode=False):
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
                                  llm_provider=llm_provider,
                                  gemini_api_key=gemini_api_key,
                                  openai_api_key=openai_api_key,
                                  fast_mode=fast_mode)
    elif ext == '.srt':
        await translate_srt_file_with_callbacks(
            input_filepath, output_filepath,
            source_language, target_language,
            model_name, chunk_target_size_cli,
            cli_api_endpoint,
            progress_callback, log_callback, stats_callback,
            check_interruption_callback=check_interruption_callback,
            llm_provider=llm_provider,
            gemini_api_key=gemini_api_key,
            openai_api_key=openai_api_key
        )
    else:
        # For .txt files, always use fast mode (no placeholder preservation needed)
        await translate_text_file_with_callbacks(
            input_filepath, output_filepath,
            source_language, target_language,
            model_name, chunk_target_size_cli,
            cli_api_endpoint,
            progress_callback, log_callback, stats_callback,
            check_interruption_callback=check_interruption_callback,
            llm_provider=llm_provider,
            gemini_api_key=gemini_api_key,
            openai_api_key=openai_api_key,
            context_window=context_window,
            auto_adjust_context=auto_adjust_context,
            min_chunk_size=min_chunk_size,
            fast_mode=True
        )