"""
File utilities for translation operations
"""
import os
import asyncio
import aiofiles
import re
import zipfile
from pathlib import Path
from typing import Optional, Callable, Tuple

from src.core.text_processor import split_text_into_chunks_with_context, split_text_into_chunks
from src.core.translator import translate_chunks
from src.core.subtitle_translator import translate_subtitles, translate_subtitles_in_blocks
from src.core.epub import translate_epub_file
from src.core.srt_processor import SRTProcessor
from src.config import DEFAULT_MODEL, MAIN_LINES_PER_CHUNK, API_ENDPOINT, SRT_LINES_PER_BLOCK, SRT_MAX_CHARS_PER_BLOCK


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
                                             openrouter_api_key=None,
                                             context_window=2048, auto_adjust_context=True, min_chunk_size=5,
                                             fast_mode=False, checkpoint_manager=None, translation_id=None,
                                             resume_from_index=0,
                                             use_token_chunking=None, max_tokens_per_chunk=None,
                                             soft_limit_ratio=None):
    """
    Translate a text file with callback support

    Args:
        input_filepath (str): Path to input file
        output_filepath (str): Path to output file
        source_language (str): Source language
        target_language (str): Target language
        model_name (str): LLM model name
        chunk_target_lines_cli (int): Target lines per chunk (legacy mode)
        cli_api_endpoint (str): API endpoint
        progress_callback (callable): Progress callback
        log_callback (callable): Logging callback
        stats_callback (callable): Statistics callback
        check_interruption_callback (callable): Interruption check callback
        fast_mode (bool): If True, uses simplified prompts without placeholder instructions
        use_token_chunking (bool): If True, use token-based chunking instead of line-based
        max_tokens_per_chunk (int): Maximum tokens per chunk (token mode)
        soft_limit_ratio (float): Soft limit ratio for token chunking (default 0.8)
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

    # Use the new unified chunking function (token-based or line-based)
    structured_chunks = split_text_into_chunks(
        original_text,
        use_token_chunking=use_token_chunking,
        max_tokens_per_chunk=max_tokens_per_chunk,
        soft_limit_ratio=soft_limit_ratio,
        chunk_size=chunk_target_lines_cli
    )
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
        # Show appropriate info based on chunking mode
        from src.config import USE_TOKEN_CHUNKING, MAX_TOKENS_PER_CHUNK
        _use_tokens = use_token_chunking if use_token_chunking is not None else USE_TOKEN_CHUNKING
        if _use_tokens:
            _max_tokens = max_tokens_per_chunk if max_tokens_per_chunk is not None else MAX_TOKENS_PER_CHUNK
            log_callback("txt_translation_info_chunks2", f"Target size per segment: ~{_max_tokens} tokens.")
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
        openrouter_api_key=openrouter_api_key,
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
                                           openrouter_api_key=None,
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
        openrouter_api_key=openrouter_api_key,
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
                        openrouter_api_key=None,
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
                                  openrouter_api_key=openrouter_api_key,
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
            openai_api_key=openai_api_key,
            openrouter_api_key=openrouter_api_key
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
            openrouter_api_key=openrouter_api_key,
            context_window=context_window,
            auto_adjust_context=auto_adjust_context,
            min_chunk_size=min_chunk_size,
            fast_mode=True
        )


def _extract_text_from_txt(filepath: str) -> str:
    """Extract text from a plain text file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def _extract_text_from_epub(filepath: str) -> str:
    """
    Extract readable text from an EPUB file.

    Parses all HTML/XHTML content files and extracts text,
    removing HTML tags and keeping only readable content.
    """
    text_parts = []

    with zipfile.ZipFile(filepath, 'r') as epub:
        for name in epub.namelist():
            if name.endswith(('.html', '.xhtml', '.htm')):
                try:
                    content = epub.read(name).decode('utf-8')
                    # Remove HTML tags
                    clean_text = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
                    clean_text = re.sub(r'<style[^>]*>.*?</style>', '', clean_text, flags=re.DOTALL | re.IGNORECASE)
                    clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
                    # Clean up whitespace
                    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                    # Decode HTML entities
                    clean_text = clean_text.replace('&nbsp;', ' ')
                    clean_text = clean_text.replace('&amp;', '&')
                    clean_text = clean_text.replace('&lt;', '<')
                    clean_text = clean_text.replace('&gt;', '>')
                    clean_text = clean_text.replace('&quot;', '"')
                    clean_text = clean_text.replace('&#39;', "'")

                    if clean_text:
                        text_parts.append(clean_text)
                except Exception:
                    continue

    return '\n\n'.join(text_parts)


def _extract_text_from_srt(filepath: str) -> str:
    """
    Extract readable text from an SRT subtitle file.

    Extracts only the subtitle text, removing timing information
    and index numbers.
    """
    srt_processor = SRTProcessor()

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    subtitles = srt_processor.parse_srt(content)

    # Extract just the text from each subtitle
    text_parts = [sub.get('text', '') for sub in subtitles if sub.get('text')]

    return ' '.join(text_parts)


def extract_text_from_file(filepath: str) -> str:
    """
    Extract readable text from a translated file.

    Supports txt, epub, and srt files. Used for TTS generation
    after translation is complete.

    Args:
        filepath: Path to the translated file

    Returns:
        Extracted text content

    Raises:
        ValueError: If file type is not supported
        FileNotFoundError: If file doesn't exist
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    _, ext = os.path.splitext(filepath.lower())

    if ext == '.txt':
        return _extract_text_from_txt(filepath)
    elif ext == '.epub':
        return _extract_text_from_epub(filepath)
    elif ext == '.srt':
        return _extract_text_from_srt(filepath)
    else:
        raise ValueError(f"Unsupported file type for TTS: {ext}")


async def generate_tts_for_translation(
    translated_filepath: str,
    target_language: str,
    tts_config: 'TTSConfig',
    log_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None
) -> Tuple[bool, str, Optional[str]]:
    """
    Generate TTS audio from a translated file.

    Extracts text from the translated file (txt, epub, or srt),
    then generates audio using the configured TTS provider.

    Args:
        translated_filepath: Path to the translated file
        target_language: Target language (for voice selection)
        tts_config: TTS configuration object
        log_callback: Optional logging callback
        progress_callback: Optional progress callback

    Returns:
        Tuple of (success: bool, message: str, audio_path: Optional[str])
    """
    from src.tts.tts_config import TTSConfig
    from src.tts.audio_processor import generate_tts_for_text

    if log_callback:
        log_callback("tts_start", f"Starting TTS generation for: {translated_filepath}")

    # Generate output audio path
    base, _ = os.path.splitext(translated_filepath)
    audio_extension = tts_config.get_output_extension()
    audio_path = f"{base}_audio{audio_extension}"

    # Ensure unique path
    audio_path = get_unique_output_path(audio_path)

    try:
        # Extract text from translated file
        if log_callback:
            log_callback("tts_extract", "Extracting text from translated file...")

        text = extract_text_from_file(translated_filepath)

        if not text.strip():
            return False, "No text found in translated file", None

        text_length = len(text)
        if log_callback:
            log_callback("tts_text_extracted", f"Extracted {text_length:,} characters for TTS")

        # Set target language in config
        tts_config.target_language = target_language

        # Create progress wrapper for TTS
        def tts_progress(current, total, message):
            if log_callback:
                log_callback("tts_progress", f"TTS: {message} ({current}/{total})")
            if progress_callback:
                # Pass all arguments to the callback
                progress_callback(current, total, message)

        # Generate audio
        if log_callback:
            log_callback("tts_synthesize", f"Synthesizing audio with voice: {tts_config.get_effective_voice(target_language)}")

        success, message = await generate_tts_for_text(
            text=text,
            output_path=audio_path,
            config=tts_config,
            language=target_language,
            progress_callback=tts_progress
        )

        if success:
            if log_callback:
                log_callback("tts_complete", f"TTS audio saved: {audio_path}")
            return True, message, audio_path
        else:
            if log_callback:
                log_callback("tts_error", f"TTS generation failed: {message}")
            return False, message, None

    except FileNotFoundError as e:
        error_msg = f"Translated file not found: {e}"
        if log_callback:
            log_callback("tts_error", error_msg)
        return False, error_msg, None
    except ValueError as e:
        error_msg = f"Unsupported file type: {e}"
        if log_callback:
            log_callback("tts_error", error_msg)
        return False, error_msg, None
    except Exception as e:
        error_msg = f"TTS generation error: {e}"
        if log_callback:
            log_callback("tts_error", error_msg)
        return False, error_msg, None