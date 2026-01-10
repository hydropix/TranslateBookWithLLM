"""
EPUB translation orchestration using simplified mode

This module coordinates the translation pipeline for EPUB files using the
simplified translation approach:
1. Extract EPUB to temp directory
2. Parse each XHTML file
3. Translate each document using translate_xhtml_simplified()
4. Save the modified EPUB
"""
import os
import zipfile
import tempfile
import aiofiles
from typing import Dict, Any, Optional, Callable, Tuple, List
from lxml import etree
from tqdm.auto import tqdm

from src.config import (
    NAMESPACES, DEFAULT_MODEL, MAIN_LINES_PER_CHUNK, API_ENDPOINT,
    MAX_TOKENS_PER_CHUNK, THINKING_MODELS, ADAPTIVE_CONTEXT_INITIAL_THINKING,
    MAX_TRANSLATION_ATTEMPTS
)
from .xhtml_translator import translate_xhtml_simplified
from ..post_processor import clean_residual_tag_placeholders
from ..context_optimizer import AdaptiveContextManager, INITIAL_CONTEXT_SIZE, CONTEXT_STEP, MAX_CONTEXT_SIZE


async def translate_epub_file(
    input_filepath: str,
    output_filepath: str,
    source_language: str = "English",
    target_language: str = "Chinese",
    model_name: str = DEFAULT_MODEL,
    chunk_target_lines_arg: int = MAIN_LINES_PER_CHUNK,
    cli_api_endpoint: str = API_ENDPOINT,
    progress_callback: Optional[Callable] = None,
    log_callback: Optional[Callable] = None,
    stats_callback: Optional[Callable] = None,
    check_interruption_callback: Optional[Callable] = None,
    llm_provider: str = "ollama",
    gemini_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    openrouter_api_key: Optional[str] = None,
    context_window: int = 2048,
    auto_adjust_context: bool = True,
    min_chunk_size: int = 5,
    checkpoint_manager=None,
    translation_id: Optional[str] = None,
    resume_from_index: int = 0,
    prompt_options: Optional[Dict] = None,
    max_tokens_per_chunk: int = MAX_TOKENS_PER_CHUNK,
    max_attempts: int = None,
) -> None:
    """
    Translate an EPUB file using LLM with simplified mode.

    Main orchestration function is now ~80 lines total (down from 340 lines).

    Uses the simplified translation approach:
    1. Extract EPUB to temp directory
    2. Parse each XHTML file
    3. For each document, call translate_xhtml_simplified()
    4. Save the modified EPUB

    Args:
        input_filepath: Path to input EPUB
        output_filepath: Path to output EPUB
        source_language: Source language
        target_language: Target language
        model_name: LLM model name
        chunk_target_lines_arg: Target lines per chunk (ignored, uses max_tokens_per_chunk)
        cli_api_endpoint: API endpoint
        progress_callback: Progress callback (0-100)
        log_callback: Logging callback
        stats_callback: Statistics callback
        check_interruption_callback: Interruption check callback
        llm_provider: LLM provider (ollama/gemini/openai/openrouter)
        gemini_api_key: Gemini API key
        openai_api_key: OpenAI API key
        openrouter_api_key: OpenRouter API key
        context_window: Context window size for LLM
        auto_adjust_context: Auto-adjust context based on model
        min_chunk_size: Minimum chunk size
        checkpoint_manager: Checkpoint manager for resume functionality
        translation_id: ID of the translation job
        resume_from_index: Index to resume from (file index)
        prompt_options: Optional dict with prompt customization options
        max_tokens_per_chunk: Maximum tokens per chunk for simplified mode
        max_attempts: Maximum translation attempts per chunk
    """
    # Validate input file
    if not os.path.exists(input_filepath):
        err_msg = f"ERROR: Input EPUB file '{input_filepath}' not found."
        if log_callback:
            log_callback("epub_input_file_not_found", err_msg)
        else:
            print(err_msg)
        return

    # Use default MAX_TRANSLATION_ATTEMPTS if not provided
    if max_attempts is None:
        max_attempts = MAX_TRANSLATION_ATTEMPTS

    # Determine initial context size based on model type
    is_known_thinking_model = any(tm in model_name.lower() for tm in THINKING_MODELS)
    if auto_adjust_context:
        if is_known_thinking_model:
            initial_context = ADAPTIVE_CONTEXT_INITIAL_THINKING
        else:
            initial_context = INITIAL_CONTEXT_SIZE
    else:
        initial_context = context_window

    # Create LLM client
    llm_client = _create_llm_client(
        llm_provider=llm_provider,
        model_name=model_name,
        gemini_api_key=gemini_api_key,
        openai_api_key=openai_api_key,
        openrouter_api_key=openrouter_api_key,
        cli_api_endpoint=cli_api_endpoint,
        initial_context=initial_context,
        log_callback=log_callback
    )

    if llm_client is None:
        return

    # Create adaptive context manager
    context_manager = _create_context_manager(
        llm_provider=llm_provider,
        auto_adjust_context=auto_adjust_context,
        initial_context=initial_context,
        is_thinking_model=is_known_thinking_model,
        log_callback=log_callback
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # 1. Extract EPUB
            _setup_epub_extraction(input_filepath, temp_dir, log_callback)

            # 2. Parse manifest
            manifest_data = _parse_epub_manifest(temp_dir, log_callback)

            # 3. Process content files
            results = await _process_all_content_files(
                content_files=manifest_data['content_files'],
                opf_dir=manifest_data['opf_dir'],
                source_language=source_language,
                target_language=target_language,
                model_name=model_name,
                llm_client=llm_client,
                max_tokens_per_chunk=max_tokens_per_chunk,
                max_attempts=max_attempts,
                context_manager=context_manager,
                translation_id=translation_id,
                resume_from_index=resume_from_index,
                checkpoint_manager=checkpoint_manager,
                log_callback=log_callback,
                progress_callback=progress_callback,
                stats_callback=stats_callback,
                check_interruption_callback=check_interruption_callback
            )

            # 4. Save translated files
            await _save_translated_files(
                parsed_xhtml_docs=results['parsed_docs'],
                log_callback=log_callback
            )

            # 5. Update metadata
            _update_epub_metadata(
                opf_tree=manifest_data['opf_tree'],
                opf_path=manifest_data['opf_path'],
                target_language=target_language
            )

            # 6. Repackage EPUB
            _repackage_epub(
                temp_dir=temp_dir,
                output_filepath=output_filepath,
                log_callback=log_callback,
                progress_callback=progress_callback
            )

            # 7. Final summary
            if log_callback:
                log_callback("epub_save_success",
                             f"Translated EPUB saved: '{output_filepath}' "
                             f"({results['completed_files']} files translated, {results['failed_files']} failed)")
            else:
                print(f"Translated EPUB saved: '{output_filepath}'")

        except Exception as e_epub:
            err_msg = f"MAJOR ERROR processing EPUB '{input_filepath}': {e_epub}"
            if log_callback:
                log_callback("epub_major_error", err_msg)
                import traceback
                log_callback("epub_major_error_traceback", traceback.format_exc())
            else:
                print(err_msg)
                import traceback
                traceback.print_exc()


def _find_opf_file(temp_dir: str) -> Optional[str]:
    """Find OPF file in extracted EPUB"""
    for root_dir, _, files in os.walk(temp_dir):
        for file in files:
            if file.endswith('.opf'):
                return os.path.join(root_dir, file)
    return None


def _get_content_files_from_spine(spine: etree._Element, manifest: etree._Element) -> list:
    """Extract content file hrefs from spine"""
    content_files = []
    for itemref in spine.findall('.//opf:itemref', namespaces=NAMESPACES):
        idref = itemref.get('idref')
        item = manifest.find(f'.//opf:item[@id="{idref}"]', namespaces=NAMESPACES)
        if item is not None:
            media_type = item.get('media-type')
            href = item.get('href')
            if media_type in ['application/xhtml+xml', 'text/html'] and href:
                content_files.append(href)
    return content_files


# === Private Helper Functions ===

def _setup_epub_extraction(input_filepath: str, temp_dir: str, log_callback: Optional[Callable] = None) -> zipfile.ZipFile:
    """Extract EPUB to temporary directory.

    Args:
        input_filepath: Path to input EPUB
        temp_dir: Temporary directory path
        log_callback: Optional logging callback

    Returns:
        Extracted zipfile object
    """
    if log_callback:
        log_callback("epub_extract_start", "Extracting EPUB...")

    with zipfile.ZipFile(input_filepath, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    return zip_ref


def _parse_epub_manifest(temp_dir: str, log_callback: Optional[Callable] = None) -> Dict:
    """Parse OPF manifest and extract metadata.

    Args:
        temp_dir: Temporary extraction directory
        log_callback: Optional logging callback

    Returns:
        Dictionary with keys: opf_path, opf_tree, opf_dir, content_files
    """
    # Find OPF file
    opf_path = _find_opf_file(temp_dir)
    if not opf_path:
        raise FileNotFoundError("CRITICAL ERROR: content.opf not found in EPUB.")

    # Parse OPF to get content files
    opf_tree = etree.parse(opf_path)
    opf_root = opf_tree.getroot()
    opf_dir = os.path.dirname(opf_path)

    manifest = opf_root.find('.//opf:manifest', namespaces=NAMESPACES)
    spine = opf_root.find('.//opf:spine', namespaces=NAMESPACES)
    if manifest is None or spine is None:
        raise ValueError("CRITICAL ERROR: manifest or spine missing in EPUB.")

    # Get content files from spine
    content_files = _get_content_files_from_spine(spine, manifest)

    if log_callback:
        log_callback("epub_files_found", f"Found {len(content_files)} content files to translate.")

    return {
        'opf_path': opf_path,
        'opf_tree': opf_tree,
        'opf_dir': opf_dir,
        'content_files': content_files
    }


def _create_llm_client(
    llm_provider: str,
    model_name: str,
    gemini_api_key: Optional[str],
    openai_api_key: Optional[str],
    openrouter_api_key: Optional[str],
    cli_api_endpoint: str,
    initial_context: int,
    log_callback: Optional[Callable] = None
) -> Any:
    """Create LLM client with specified configuration.

    Args:
        llm_provider: LLM provider (ollama/gemini/openai/openrouter)
        model_name: Model name
        gemini_api_key: Gemini API key
        openai_api_key: OpenAI API key
        openrouter_api_key: OpenRouter API key
        cli_api_endpoint: API endpoint
        initial_context: Initial context window size
        log_callback: Optional logging callback

    Returns:
        LLM client instance
    """
    from ..llm_client import create_llm_client

    llm_client = create_llm_client(
        llm_provider, gemini_api_key, cli_api_endpoint, model_name,
        openai_api_key, openrouter_api_key,
        context_window=initial_context,
        log_callback=log_callback
    )

    if llm_client is None:
        err_msg = "ERROR: Could not create LLM client."
        if log_callback:
            log_callback("llm_client_error", err_msg)
        else:
            print(err_msg)

    return llm_client


def _create_context_manager(
    llm_provider: str,
    auto_adjust_context: bool,
    initial_context: int,
    is_thinking_model: bool,
    log_callback: Optional[Callable] = None
) -> Optional[AdaptiveContextManager]:
    """Create adaptive context manager if applicable.

    Args:
        llm_provider: LLM provider name
        auto_adjust_context: Whether to auto-adjust context
        initial_context: Initial context size
        is_thinking_model: Whether using a thinking model
        log_callback: Optional logging callback

    Returns:
        AdaptiveContextManager instance or None
    """
    context_manager = None
    if llm_provider == "ollama" and auto_adjust_context:
        context_manager = AdaptiveContextManager(
            initial_context=initial_context,
            context_step=CONTEXT_STEP,
            max_context=MAX_CONTEXT_SIZE,
            log_callback=log_callback
        )
        model_type = "thinking" if is_thinking_model else "standard"
        if log_callback:
            log_callback("context_adaptive",
                f"🎯 Adaptive context enabled for EPUB ({model_type} model): starting at {initial_context} tokens, "
                f"max={MAX_CONTEXT_SIZE}, step={CONTEXT_STEP}")

    return context_manager


async def _translate_single_file(
    file_idx: int,
    content_href: str,
    opf_dir: str,
    source_language: str,
    target_language: str,
    model_name: str,
    llm_client: Any,
    max_tokens_per_chunk: int,
    max_attempts: int,
    context_manager: Optional[AdaptiveContextManager],
    translation_id: Optional[str],
    total_files: int,
    log_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None
) -> Tuple[Optional[etree._Element], str, bool]:
    """Translate a single XHTML file.

    Args:
        file_idx: File index
        content_href: Content file href
        opf_dir: OPF directory path
        source_language: Source language
        target_language: Target language
        model_name: Model name
        llm_client: LLM client instance
        max_tokens_per_chunk: Max tokens per chunk
        max_attempts: Max translation attempts
        context_manager: Optional context manager
        translation_id: Optional translation ID
        total_files: Total number of files
        log_callback: Optional logging callback
        progress_callback: Optional progress callback

    Returns:
        Tuple of (doc_root, file_path_abs, success)
    """
    file_path_abs = os.path.normpath(os.path.join(opf_dir, content_href))
    if not os.path.exists(file_path_abs):
        if log_callback:
            log_callback("epub_file_not_found",
                         f"WARNING: File '{content_href}' not found, skipped.")
        return None, file_path_abs, False

    try:
        # Parse XHTML file
        async with aiofiles.open(file_path_abs, 'r', encoding='utf-8') as f_chap:
            chap_str_content = await f_chap.read()

        parser = etree.XMLParser(encoding='utf-8', recover=True, remove_blank_text=False)
        doc_root = etree.fromstring(chap_str_content.encode('utf-8'), parser)

        if log_callback:
            log_callback("epub_file_translate_start",
                         f"Translating file {file_idx + 1}/{total_files}: {content_href}")

        # Translate using simplified mode
        # Note: progress_callback is now token-aware wrapper from _process_all_content_files
        success = await translate_xhtml_simplified(
            doc_root=doc_root,
            source_language=source_language,
            target_language=target_language,
            model_name=model_name,
            llm_client=llm_client,
            max_tokens_per_chunk=max_tokens_per_chunk,
            log_callback=log_callback,
            progress_callback=progress_callback,  # Pass through token-based wrapper directly
            context_manager=context_manager,
            max_retries=max_attempts
        )

        if success:
            if log_callback:
                log_callback("epub_file_translate_complete",
                             f"Completed file {file_idx + 1}/{total_files}: {content_href}")
        else:
            if log_callback:
                log_callback("epub_file_translate_failed",
                             f"Failed to translate file {file_idx + 1}/{total_files}: {content_href}")

        return doc_root, file_path_abs, success

    except etree.XMLSyntaxError as e_xml:
        if log_callback:
            log_callback("epub_xml_error",
                         f"XML error in '{content_href}': {e_xml}")
        return None, file_path_abs, False
    except Exception as e_file:
        if log_callback:
            log_callback("epub_file_error",
                         f"Error processing '{content_href}': {e_file}")
        return None, file_path_abs, False


async def _count_all_chunks(
    content_files: list,
    opf_dir: str,
    max_tokens_per_chunk: int,
    log_callback: Optional[Callable] = None
) -> List[Tuple[str, List[Dict], int]]:
    """
    Pre-count all chunks across all XHTML files.

    Returns list of (file_href, chunks_info, total_tokens) for each file.
    This allows accurate progress tracking based on actual chunk count, not file count.
    """
    from .xhtml_translator import _setup_translation, _preserve_tags, _create_chunks
    from .body_serializer import extract_body_html
    import aiofiles
    from lxml import etree

    file_chunk_info = []
    total_chunks_all_files = 0

    if log_callback:
        log_callback("epub_precount_start", f"📊 Pre-counting chunks across {len(content_files)} files...")

    for content_href in content_files:
        file_path_abs = os.path.normpath(os.path.join(opf_dir, content_href))
        if not os.path.exists(file_path_abs):
            # File not found, will be skipped during translation
            file_chunk_info.append((content_href, [], 0))
            continue

        try:
            async with aiofiles.open(file_path_abs, 'r', encoding='utf-8') as f:
                content = await f.read()

            parser = etree.XMLParser(encoding='utf-8', recover=True, remove_blank_text=False)
            doc_root = etree.fromstring(content.encode('utf-8'), parser)

            # Extract body and count chunks (same logic as translation)
            body_html, body_element, tag_preserver = _setup_translation(doc_root, log_callback, None)

            if not body_html:
                file_chunk_info.append((content_href, [], 0))
                continue

            # Preserve tags
            text_with_placeholders, global_tag_map, _ = _preserve_tags(body_html, tag_preserver, log_callback)

            # Create chunks
            chunks = _create_chunks(text_with_placeholders, global_tag_map, max_tokens_per_chunk, log_callback, None)

            # Calculate total tokens for this file
            from src.core.chunking.token_chunker import TokenChunker
            token_counter = TokenChunker(max_tokens=max_tokens_per_chunk)
            file_total_tokens = sum(token_counter.count_tokens(chunk['text']) for chunk in chunks)

            file_chunk_info.append((content_href, chunks, file_total_tokens))
            total_chunks_all_files += len(chunks)

        except Exception as e:
            if log_callback:
                log_callback("epub_precount_error", f"Error pre-counting chunks in '{content_href}': {e}")
            file_chunk_info.append((content_href, [], 0))

    if log_callback:
        log_callback("epub_precount_complete",
                     f"📊 Pre-count complete: {total_chunks_all_files} total chunks across {len(content_files)} files")
        # Log per-file breakdown for debugging
        for i, (href, chunks, tokens) in enumerate(file_chunk_info[:5]):  # Show first 5 files
            log_callback("epub_precount_file_detail",
                         f"  File {i+1}: {href} → {len(chunks)} chunks, {tokens} tokens")
        if len(file_chunk_info) > 5:
            log_callback("epub_precount_more", f"  ... and {len(file_chunk_info) - 5} more files")

    return file_chunk_info


async def _process_all_content_files(
    content_files: list,
    opf_dir: str,
    source_language: str,
    target_language: str,
    model_name: str,
    llm_client: Any,
    max_tokens_per_chunk: int,
    max_attempts: int,
    context_manager: Optional[AdaptiveContextManager],
    translation_id: Optional[str],
    resume_from_index: int = 0,
    checkpoint_manager=None,
    log_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None,
    stats_callback: Optional[Callable] = None,
    check_interruption_callback: Optional[Callable] = None
) -> Dict:
    """Process all XHTML content files with accurate token-based progress tracking.

    Args:
        content_files: List of content file hrefs
        opf_dir: OPF directory path
        source_language: Source language
        target_language: Target language
        model_name: Model name
        llm_client: LLM client instance
        max_tokens_per_chunk: Max tokens per chunk
        max_attempts: Max translation attempts
        context_manager: Optional context manager
        translation_id: Optional translation ID
        resume_from_index: Index to resume from
        checkpoint_manager: Optional checkpoint manager
        log_callback: Optional logging callback
        progress_callback: Optional progress callback
        stats_callback: Optional stats callback
        check_interruption_callback: Optional interruption check callback

    Returns:
        Dictionary with processing results and parsed documents
    """
    from src.core.progress_tracker import TokenProgressTracker

    # Pre-count all chunks across all files for accurate progress
    file_chunk_info = await _count_all_chunks(content_files, opf_dir, max_tokens_per_chunk, log_callback)

    # Initialize token-based progress tracker
    progress_tracker = TokenProgressTracker()
    progress_tracker.start()

    # Register all chunks with their token counts
    total_registered_chunks = 0
    total_registered_tokens = 0
    for file_href, chunks, file_tokens in file_chunk_info:
        if chunks:
            from src.core.chunking.token_chunker import TokenChunker
            token_counter = TokenChunker(max_tokens=max_tokens_per_chunk)
            for chunk in chunks:
                token_count = token_counter.count_tokens(chunk['text'])
                progress_tracker.register_chunk(token_count)
                total_registered_chunks += 1
                total_registered_tokens += token_count

    if log_callback:
        log_callback("epub_tracker_initialized",
                     f"📈 Progress tracker initialized: {total_registered_chunks} chunks, {total_registered_tokens} tokens")

    # Initial stats
    if stats_callback:
        stats_callback(progress_tracker.get_stats().to_dict())

    parsed_xhtml_docs: Dict[str, etree._Element] = {}
    total_files = len(content_files)
    completed_files = 0
    failed_files = 0
    global_chunk_index = 0  # Track global chunk index across all files

    iterator = tqdm(
        enumerate(content_files),
        total=total_files,
        desc="Translating EPUB files",
        unit="file"
    ) if not log_callback else enumerate(content_files)

    for file_idx, content_href in iterator:
        # Check for interruption
        if check_interruption_callback and check_interruption_callback():
            if log_callback:
                log_callback("epub_translation_interrupted",
                             f"Translation interrupted at file {file_idx + 1}/{total_files}")
            break

        # Get chunk info for this file
        _, file_chunks, _ = file_chunk_info[file_idx]
        file_chunk_count = len(file_chunks)

        # Skip already processed files on resume
        if file_idx < resume_from_index:
            completed_files += 1
            # Mark all chunks in this file as completed for progress tracker
            for chunk_idx in range(file_chunk_count):
                progress_tracker.mark_completed(global_chunk_index + chunk_idx, 0.0)
            global_chunk_index += file_chunk_count
            continue

        # Create wrapper progress callback
        # The existing code calls progress_callback with percentage (0-100) per file
        # We intercept that and update the global tracker based on chunk completion
        file_start_chunk_idx = global_chunk_index
        last_reported_chunk = [0]  # Mutable to capture in closure

        def file_progress_wrapper(file_percent: float):
            """
            Intercept file-level progress (0-100%) and convert to chunk-level progress.

            file_percent: Progress within this file (0-100)
            """
            if file_chunk_count == 0:
                return

            # Estimate which chunk we're on based on percentage
            chunks_completed_in_file = int((file_percent / 100) * file_chunk_count)
            chunks_completed_in_file = min(chunks_completed_in_file, file_chunk_count)

            # Mark newly completed chunks since last call
            for chunk_offset in range(last_reported_chunk[0], chunks_completed_in_file):
                actual_global_idx = file_start_chunk_idx + chunk_offset
                progress_tracker.mark_completed(actual_global_idx, 0.0)  # No time measurement available

            last_reported_chunk[0] = chunks_completed_in_file

            # Update global progress
            if progress_callback:
                progress_callback(progress_tracker.get_progress_percent())
            if stats_callback:
                stats_callback(progress_tracker.get_stats().to_dict())

        # Translate the file (reuse existing function)
        doc_root, file_path_abs, success = await _translate_single_file(
            file_idx=file_idx,
            content_href=content_href,
            opf_dir=opf_dir,
            source_language=source_language,
            target_language=target_language,
            model_name=model_name,
            llm_client=llm_client,
            max_tokens_per_chunk=max_tokens_per_chunk,
            max_attempts=max_attempts,
            context_manager=context_manager,
            translation_id=translation_id,
            total_files=total_files,
            log_callback=log_callback,
            progress_callback=file_progress_wrapper  # Use our wrapper
        )

        # Ensure all chunks in this file are marked complete after translation finishes
        for chunk_offset in range(last_reported_chunk[0], file_chunk_count):
            actual_global_idx = file_start_chunk_idx + chunk_offset
            progress_tracker.mark_completed(actual_global_idx, 0.0)

        # Advance global chunk index by number of chunks in this file
        global_chunk_index += file_chunk_count

        # Save the document if translation succeeded
        # Note: doc_root is modified in-place only if _replace_body succeeds
        # If it fails, doc_root still contains the original content (no data loss)
        if success and doc_root is not None:
            parsed_xhtml_docs[file_path_abs] = doc_root
            completed_files += 1
        elif not success and doc_root is not None:
            # Translation attempted but XML reconstruction failed
            # Save the original document (better than losing the file entirely)
            parsed_xhtml_docs[file_path_abs] = doc_root
            failed_files += 1
            if log_callback:
                log_callback("epub_xml_reconstruction_failed",
                             f"File {file_idx + 1}/{total_files} kept original due to XML errors: {content_href}")
        else:
            failed_files += 1

        # Update statistics from progress tracker
        if stats_callback:
            stats_callback(progress_tracker.get_stats().to_dict())

        # Save checkpoint after each file
        if checkpoint_manager and translation_id:
            stats = progress_tracker.get_stats()
            checkpoint_manager.save_checkpoint(
                translation_id=translation_id,
                chunk_index=file_idx + 1,
                original_text=content_href,
                translated_text=content_href,
                chunk_data={'last_file': content_href},
                total_chunks=stats.total_chunks,
                completed_chunks=stats.completed_chunks,
                failed_chunks=stats.failed_chunks
            )

    return {
        'parsed_docs': parsed_xhtml_docs,
        'completed_files': completed_files,
        'failed_files': failed_files
    }


async def _save_translated_files(
    parsed_xhtml_docs: Dict[str, etree._Element],
    log_callback: Optional[Callable] = None
) -> None:
    """Save modified XHTML files.

    Args:
        parsed_xhtml_docs: Dictionary of file paths to parsed documents
        log_callback: Optional logging callback
    """
    if log_callback:
        log_callback("epub_save_start", "Saving translated files...")

    for file_path_abs, doc_root in parsed_xhtml_docs.items():
        try:
            # Clean residual placeholders
            for element in doc_root.iter():
                if element.text:
                    element.text = clean_residual_tag_placeholders(element.text)
                if element.tail:
                    element.tail = clean_residual_tag_placeholders(element.tail)

            async with aiofiles.open(file_path_abs, 'wb') as f_out:
                await f_out.write(
                    etree.tostring(doc_root, encoding='utf-8', xml_declaration=True,
                                   pretty_print=True, method='xml')
                )
        except Exception as e_write:
            if log_callback:
                log_callback("epub_write_error",
                             f"Error writing '{file_path_abs}': {e_write}")


def _repackage_epub(
    temp_dir: str,
    output_filepath: str,
    log_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None
) -> None:
    """Repackage the EPUB file.

    Args:
        temp_dir: Temporary directory with extracted EPUB
        output_filepath: Output EPUB file path
        log_callback: Optional logging callback
        progress_callback: Optional progress callback
    """
    if progress_callback:
        progress_callback(95)

    if log_callback:
        log_callback("epub_zip_start", "Creating translated EPUB file...")

    with zipfile.ZipFile(output_filepath, 'w', zipfile.ZIP_DEFLATED) as epub_zip:
        # Add mimetype first (uncompressed)
        mimetype_path = os.path.join(temp_dir, 'mimetype')
        if os.path.exists(mimetype_path):
            epub_zip.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)

        # Add all other files
        for root_path, _, files in os.walk(temp_dir):
            for file_item in files:
                if file_item != 'mimetype':
                    file_path_abs = os.path.join(root_path, file_item)
                    arcname = os.path.relpath(file_path_abs, temp_dir)
                    epub_zip.write(file_path_abs, arcname)

    if progress_callback:
        progress_callback(100)


def _update_epub_metadata(
    opf_tree: etree._ElementTree,
    opf_path: str,
    target_language: str
) -> None:
    """
    Update EPUB metadata with target language and translation signature

    Args:
        opf_tree: Parsed OPF tree
        opf_path: Path to OPF file
        target_language: Target language
    """
    from src.config import ATTRIBUTION_ENABLED, GENERATOR_NAME, GENERATOR_SOURCE

    opf_root = opf_tree.getroot()
    metadata = opf_root.find('.//opf:metadata', namespaces=NAMESPACES)
    if metadata is not None:
        # Update language
        lang_el = metadata.find('.//dc:language', namespaces=NAMESPACES)
        if lang_el is not None:
            lang_el.text = target_language.lower()[:2]

        # Add translation signature if enabled
        if ATTRIBUTION_ENABLED:
            # Add contributor (translator) - Dublin Core standard
            contributor_el = etree.SubElement(
                metadata,
                '{http://purl.org/dc/elements/1.1/}contributor'
            )
            contributor_el.text = GENERATOR_NAME
            contributor_el.set('{http://www.idpf.org/2007/opf}role', 'trl')

            # Add or update description with signature
            desc_el = metadata.find('.//dc:description', namespaces=NAMESPACES)
            signature_text = f"\n\nTranslated using {GENERATOR_NAME}\n{GENERATOR_SOURCE}"

            if desc_el is None:
                desc_el = etree.SubElement(
                    metadata,
                    '{http://purl.org/dc/elements/1.1/}description'
                )
                desc_el.text = signature_text.strip()
            else:
                # Append to existing description
                if desc_el.text:
                    desc_el.text += signature_text
                else:
                    desc_el.text = signature_text.strip()

    opf_tree.write(opf_path, encoding='utf-8', xml_declaration=True, pretty_print=True)
