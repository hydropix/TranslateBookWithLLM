"""
EPUB translation orchestration

This module coordinates the translation pipeline for EPUB files, managing
the extraction, translation, and reassembly phases.
"""
import os
import re
import html
import zipfile
import tempfile
import aiofiles
from typing import List, Dict, Any, Optional, Callable
from lxml import etree
from tqdm.auto import tqdm

from src.config import (
    NAMESPACES, IGNORED_TAGS_EPUB, CONTENT_BLOCK_TAGS_EPUB,
    DEFAULT_MODEL, MAIN_LINES_PER_CHUNK, API_ENDPOINT
)
from .constants import (
    MIN_CONTEXT_LINES, MIN_CONTEXT_WORDS, MAX_CONTEXT_LINES,
    MAX_CONTEXT_BLOCKS, PLACEHOLDER_PATTERN
)
from .job_collector import collect_translation_jobs
from .tag_preservation import TagPreserver
from .xml_helpers import rebuild_element_from_translated_content
from ..translator import generate_translation_request
from ..post_processor import clean_residual_tag_placeholders


async def translate_epub_file(
    input_filepath: str,
    output_filepath: str,
    source_language: str = "English",
    target_language: str = "French",
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
    simple_mode: bool = False,
    context_window: int = 2048,
    auto_adjust_context: bool = True,
    min_chunk_size: int = 5
) -> None:
    """
    Translate an EPUB file using LLM

    This is the main entry point for EPUB translation. It orchestrates the
    entire pipeline: extraction, job collection, translation, and reassembly.

    Args:
        input_filepath: Path to input EPUB
        output_filepath: Path to output EPUB
        source_language: Source language
        target_language: Target language
        model_name: LLM model name
        chunk_target_lines_arg: Target lines per chunk
        cli_api_endpoint: API endpoint
        progress_callback: Progress callback
        log_callback: Logging callback
        stats_callback: Statistics callback
        check_interruption_callback: Interruption check callback
        llm_provider: LLM provider (ollama/gemini/openai)
        gemini_api_key: Gemini API key
        openai_api_key: OpenAI API key
        simple_mode: Use simple mode (extract pure text, translate, rebuild)
        context_window: Context window size for LLM
        auto_adjust_context: Auto-adjust context based on model
        min_chunk_size: Minimum chunk size
    """
    if not os.path.exists(input_filepath):
        err_msg = f"ERROR: Input EPUB file '{input_filepath}' not found."
        if log_callback:
            log_callback("epub_input_file_not_found", err_msg)
        else:
            print(err_msg)
        return

    # Route to simple mode if enabled
    if simple_mode:
        await _translate_epub_simple_mode(
            input_filepath, output_filepath, source_language, target_language,
            model_name, chunk_target_lines_arg, cli_api_endpoint,
            progress_callback, log_callback, stats_callback,
            check_interruption_callback,
            llm_provider, gemini_api_key, openai_api_key,
            context_window, auto_adjust_context, min_chunk_size
        )
        return

    # Standard translation pipeline
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Phase 1: Extract and parse EPUB
            epub_data = await _extract_and_parse_epub(
                input_filepath, temp_dir, progress_callback, log_callback
            )

            # Phase 2: Collect translation jobs
            jobs = await _collect_jobs(
                epub_data, chunk_target_lines_arg, progress_callback, log_callback
            )

            if not jobs:
                _log_no_translatable_content(log_callback, progress_callback)
                return

            if stats_callback:
                stats_callback({'total_chunks': len(jobs), 'completed_chunks': 0, 'failed_chunks': 0})

            # Phase 3: Translate jobs
            completed, failed = await _translate_jobs(
                jobs, source_language, target_language, model_name,
                cli_api_endpoint, llm_provider, gemini_api_key, openai_api_key,
                progress_callback, log_callback, stats_callback, check_interruption_callback
            )

            if progress_callback:
                progress_callback(100)

            # Phase 4: Apply translations to parsed documents
            await _apply_translations(jobs, log_callback)

            # Phase 5: Update metadata
            _update_epub_metadata(epub_data['opf_tree'], epub_data['opf_path'], target_language)

            # Phase 6: Save modified EPUB
            await _save_epub(
                epub_data['parsed_xhtml_docs'], output_filepath, temp_dir, log_callback
            )

        except Exception as e_epub:
            _log_major_error(e_epub, input_filepath, log_callback)


async def _extract_and_parse_epub(
    input_filepath: str,
    temp_dir: str,
    progress_callback: Optional[Callable],
    log_callback: Optional[Callable]
) -> Dict[str, Any]:
    """
    Extract EPUB and parse content files

    Args:
        input_filepath: Path to EPUB file
        temp_dir: Temporary directory for extraction
        progress_callback: Progress callback
        log_callback: Logging callback

    Returns:
        Dictionary containing parsed EPUB data:
        - opf_path: Path to OPF file
        - opf_tree: Parsed OPF tree
        - opf_root: OPF root element
        - content_files: List of content file hrefs
        - opf_dir: OPF directory path
        - parsed_xhtml_docs: Dict mapping file paths to parsed documents
    """
    # Extract EPUB
    with zipfile.ZipFile(input_filepath, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    # Find OPF file
    opf_path = _find_opf_file(temp_dir)
    if not opf_path:
        raise FileNotFoundError("CRITICAL ERROR: content.opf not found in EPUB.")

    # Parse OPF
    opf_tree = etree.parse(opf_path)
    opf_root = opf_tree.getroot()

    manifest = opf_root.find('.//opf:manifest', namespaces=NAMESPACES)
    spine = opf_root.find('.//opf:spine', namespaces=NAMESPACES)
    if manifest is None or spine is None:
        raise ValueError("CRITICAL ERROR: manifest or spine missing in EPUB.")

    # Get content files from spine
    content_files = _get_content_files_from_spine(spine, manifest)
    opf_dir = os.path.dirname(opf_path)

    return {
        'opf_path': opf_path,
        'opf_tree': opf_tree,
        'opf_root': opf_root,
        'content_files': content_files,
        'opf_dir': opf_dir,
        'parsed_xhtml_docs': {}
    }


async def _collect_jobs(
    epub_data: Dict[str, Any],
    chunk_size: int,
    progress_callback: Optional[Callable],
    log_callback: Optional[Callable]
) -> List[Dict[str, Any]]:
    """
    Collect translation jobs from EPUB content files

    Args:
        epub_data: EPUB data from extraction phase
        chunk_size: Target chunk size
        progress_callback: Progress callback
        log_callback: Logging callback

    Returns:
        List of translation jobs
    """
    if log_callback:
        log_callback("epub_phase1_start", "Phase 1: Collecting and splitting text from EPUB...")

    jobs = []
    content_files = epub_data['content_files']
    opf_dir = epub_data['opf_dir']

    iterator = tqdm(content_files, desc="Analyzing EPUB files", unit="file") if not log_callback else content_files

    for file_idx, content_href in enumerate(iterator):
        if progress_callback and len(content_files) > 0:
            progress_callback((file_idx / len(content_files)) * 10)

        file_path_abs = os.path.normpath(os.path.join(opf_dir, content_href))
        if not os.path.exists(file_path_abs):
            _log_file_not_found(content_href, file_path_abs, log_callback)
            continue

        try:
            # Parse XHTML file
            async with aiofiles.open(file_path_abs, 'r', encoding='utf-8') as f_chap:
                chap_str_content = await f_chap.read()

            parser = etree.XMLParser(encoding='utf-8', recover=True, remove_blank_text=False)
            doc_chap_root = etree.fromstring(chap_str_content.encode('utf-8'), parser)
            epub_data['parsed_xhtml_docs'][file_path_abs] = doc_chap_root

            # Collect jobs from body element
            body_el = doc_chap_root.find('.//{http://www.w3.org/1999/xhtml}body')
            if body_el is not None:
                collect_translation_jobs(
                    body_el, file_path_abs, jobs, chunk_size,
                    IGNORED_TAGS_EPUB, CONTENT_BLOCK_TAGS_EPUB, log_callback
                )

        except etree.XMLSyntaxError as e_xml:
            _log_xml_error(content_href, e_xml, log_callback)
        except Exception as e_chap:
            _log_collection_error(content_href, e_chap, log_callback)

    if jobs and log_callback:
        log_callback("epub_jobs_collected", f"{len(jobs)} translatable segments collected.")

    return jobs


async def _translate_jobs(
    jobs: List[Dict[str, Any]],
    source_language: str,
    target_language: str,
    model_name: str,
    cli_api_endpoint: str,
    llm_provider: str,
    gemini_api_key: Optional[str],
    openai_api_key: Optional[str],
    progress_callback: Optional[Callable],
    log_callback: Optional[Callable],
    stats_callback: Optional[Callable],
    check_interruption_callback: Optional[Callable]
) -> tuple[int, int]:
    """
    Translate all collected jobs

    Args:
        jobs: List of translation jobs
        source_language: Source language
        target_language: Target language
        model_name: Model name
        cli_api_endpoint: API endpoint
        llm_provider: LLM provider
        gemini_api_key: Gemini API key
        openai_api_key: OpenAI API key
        progress_callback: Progress callback
        log_callback: Logging callback
        stats_callback: Statistics callback
        check_interruption_callback: Interruption check callback

    Returns:
        Tuple of (completed_count, failed_count)
    """
    if log_callback:
        log_callback("epub_phase2_start", "\nPhase 2: Translating EPUB text segments...")

    # Create LLM client
    from ..llm_client import create_llm_client
    llm_client = create_llm_client(llm_provider, gemini_api_key, cli_api_endpoint, model_name, openai_api_key)

    last_successful_context = ""
    context_accumulator = []
    completed_count = 0
    failed_count = 0

    iterator = tqdm(jobs, desc="Translating EPUB segments", unit="seg") if not log_callback else jobs

    for job_idx, job in enumerate(iterator):
        if check_interruption_callback and check_interruption_callback():
            _log_interruption(job_idx, len(jobs), log_callback)
            break

        if progress_callback and len(jobs) > 0:
            base_progress = ((job_idx + 1) / len(jobs)) * 90
            progress_callback(10 + base_progress)

        # Translate job
        translated_parts = await _translate_epub_chunks_with_context(
            job['sub_chunks'], source_language, target_language,
            model_name, llm_client, last_successful_context,
            log_callback, check_interruption_callback
        )

        # Join translated parts
        translated_text = "\n".join(translated_parts)

        # Restore tags if this job had them
        if 'tag_map' in job and job['tag_map']:
            translated_text = _validate_and_restore_tags(
                translated_text, job['tag_map'], log_callback
            )

        job['translated_text'] = translated_text

        # Update statistics
        has_error = any("[TRANSLATION_ERROR" in part for part in translated_parts)
        if has_error:
            failed_count += 1
        else:
            completed_count += 1
            # Update context
            last_successful_context = _build_context_from_translation(
                translated_parts, context_accumulator
            )

        if stats_callback:
            stats_callback({'completed_chunks': completed_count, 'failed_chunks': failed_count})

    return completed_count, failed_count


async def _translate_epub_chunks_with_context(
    chunks: List[Dict[str, str]],
    source_language: str,
    target_language: str,
    model_name: str,
    llm_client: Any,
    previous_context: str,
    log_callback: Optional[Callable],
    check_interruption_callback: Optional[Callable]
) -> List[str]:
    """
    Translate EPUB chunks with previous translation context for consistency

    Args:
        chunks: List of chunk dictionaries
        source_language: Source language
        target_language: Target language
        model_name: Model name
        llm_client: LLM client instance
        previous_context: Previous translation for context
        log_callback: Logging callback
        check_interruption_callback: Interruption check callback

    Returns:
        List of translated chunks
    """
    total_chunks = len(chunks)
    translated_parts = []

    for i, chunk_data in enumerate(chunks):
        if check_interruption_callback and check_interruption_callback():
            if log_callback:
                log_callback("epub_translation_interrupted",
                           f"EPUB translation process for chunk {i+1}/{total_chunks} interrupted by user signal.")
            break

        main_content = chunk_data["main_content"]
        context_before = chunk_data["context_before"]
        context_after = chunk_data["context_after"]

        if not main_content.strip():
            translated_parts.append(main_content)
            continue

        # Extract placeholders for validation
        source_placeholders = set(re.findall(PLACEHOLDER_PATTERN, main_content))

        # Translate
        translated_chunk = await generate_translation_request(
            main_content, context_before, context_after,
            previous_context, source_language, target_language,
            model_name, llm_client=llm_client, log_callback=log_callback
        )

        if translated_chunk is not None:
            # Validate and retry if placeholders missing
            if source_placeholders:
                translated_chunk = await _validate_placeholders_and_retry(
                    translated_chunk, source_placeholders, main_content,
                    context_before, context_after, previous_context,
                    source_language, target_language, model_name,
                    llm_client, log_callback
                )

            translated_parts.append(translated_chunk)
        else:
            # Translation failed
            error_placeholder = f"[TRANSLATION_ERROR EPUB CHUNK {i+1}]\n{main_content}\n[/TRANSLATION_ERROR EPUB CHUNK {i+1}]"
            translated_parts.append(error_placeholder)
            if log_callback:
                log_callback("epub_chunk_translation_error",
                           f"ERROR translating EPUB chunk {i+1}. Original content preserved.")

    return translated_parts


async def _validate_placeholders_and_retry(
    translated_text: str,
    source_placeholders: set,
    main_content: str,
    context_before: str,
    context_after: str,
    previous_context: str,
    source_language: str,
    target_language: str,
    model_name: str,
    llm_client: Any,
    log_callback: Optional[Callable]
) -> str:
    """
    Validate placeholders in translation and retry if missing

    Args:
        translated_text: Translated text to validate
        source_placeholders: Set of expected placeholders
        main_content: Original content
        context_before: Context before
        context_after: Context after
        previous_context: Previous translation context
        source_language: Source language
        target_language: Target language
        model_name: Model name
        llm_client: LLM client
        log_callback: Logging callback

    Returns:
        Validated/retried translation
    """
    translated_placeholders = set(re.findall(PLACEHOLDER_PATTERN, translated_text))
    missing = source_placeholders - translated_placeholders

    if missing:
        if log_callback:
            log_callback("epub_translation_missing_placeholders",
                       f"Translation missing placeholders: {missing}. Missing: {', '.join(sorted(missing))}")

        # Retry translation (prompt already includes placeholder preservation instructions)
        retry_text = await generate_translation_request(
            main_content, context_before, context_after,
            previous_context, source_language, target_language,
            model_name, llm_client=llm_client, log_callback=log_callback
        )

        if retry_text is not None:
            retry_placeholders = set(re.findall(PLACEHOLDER_PATTERN, retry_text))
            if not (source_placeholders - retry_placeholders):  # All placeholders present
                if log_callback:
                    log_callback("epub_translation_retry_successful",
                               "Translation retry successful - placeholders preserved")
                return retry_text

    return translated_text


def _validate_and_restore_tags(
    translated_text: str,
    tag_map: Dict[str, str],
    log_callback: Optional[Callable]
) -> str:
    """
    Validate and restore tags in translated text

    Args:
        translated_text: Translated text with placeholders
        tag_map: Tag map for restoration
        log_callback: Logging callback

    Returns:
        Text with restored tags
    """
    tag_preserver = TagPreserver()

    # Final validation
    is_valid, missing, mutated = tag_preserver.validate_placeholders(translated_text, tag_map)

    if not is_valid:
        # Try to fix mutations
        if mutated:
            translated_text = tag_preserver.fix_mutated_placeholders(translated_text, mutated)
            if log_callback:
                log_callback("epub_fixed_mutations_final",
                           f"Fixed placeholder mutations in final check: {mutated}")

        # Log if still missing
        if missing:
            if log_callback:
                log_callback("epub_placeholders_still_missing",
                           f"WARNING: Some placeholders still missing after all retries: {missing}")
                log_callback("epub_suggest_simple_mode",
                           "💡 TIP: If you see many placeholder warnings, enable 'Simple Mode' in the web interface. "
                           "Simple Mode removes all HTML tags before translation, eliminating placeholder issues. "
                           "Perfect for weaker LLM models!")

    # Restore tags
    return tag_preserver.restore_tags(translated_text, tag_map)


def _build_context_from_translation(
    translated_parts: List[str],
    context_accumulator: List[str]
) -> str:
    """
    Build context string from recent translations

    Args:
        translated_parts: Latest translated parts
        context_accumulator: Accumulator of recent translations

    Returns:
        Context string for next translation
    """
    if not translated_parts:
        return ""

    last_translation = "\n".join(translated_parts)
    context_accumulator.append(last_translation)

    # Build context from multiple recent blocks
    combined_context_lines = []
    for recent_translation in reversed(context_accumulator):
        translation_lines = recent_translation.split('\n')
        combined_context_lines = translation_lines + combined_context_lines

        # Stop if we have enough context
        if (len(combined_context_lines) >= MIN_CONTEXT_LINES or
            len(' '.join(combined_context_lines).split()) >= MIN_CONTEXT_WORDS):
            break

    # Limit context size
    if len(combined_context_lines) > MAX_CONTEXT_LINES:
        combined_context_lines = combined_context_lines[-MAX_CONTEXT_LINES:]

    # Keep accumulator bounded
    if len(context_accumulator) > MAX_CONTEXT_BLOCKS:
        context_accumulator[:] = context_accumulator[-MAX_CONTEXT_BLOCKS:]

    return '\n'.join(combined_context_lines)


async def _apply_translations(
    jobs: List[Dict[str, Any]],
    log_callback: Optional[Callable]
) -> None:
    """
    Apply translated text back to EPUB elements

    Args:
        jobs: List of translation jobs with results
        log_callback: Logging callback
    """
    if log_callback:
        log_callback("epub_phase3_start", "\nPhase 3: Applying translations to EPUB files...")

    iterator = tqdm(jobs, desc="Updating EPUB content", unit="seg") if not log_callback else jobs

    for job in iterator:
        if job.get('translated_text') is None:
            continue

        element = job['element_ref']
        translated_content = job['translated_text']

        # Unescape HTML entities
        translated_content_unescaped = html.unescape(translated_content)

        if job['type'] == 'block_content':
            # Rebuild element structure if it had inline tags
            if job.get('has_inline_tags'):
                rebuild_element_from_translated_content(element, translated_content_unescaped)
            else:
                element.text = translated_content_unescaped
                for child_node in list(element):
                    element.remove(child_node)
        elif job['type'] == 'text':
            element.text = job['leading_space'] + translated_content_unescaped + job['trailing_space']
        elif job['type'] == 'tail':
            element.tail = job['leading_space'] + translated_content_unescaped + job['trailing_space']


def _update_epub_metadata(
    opf_tree: etree._ElementTree,
    opf_path: str,
    target_language: str
) -> None:
    """
    Update EPUB metadata with target language

    Args:
        opf_tree: Parsed OPF tree
        opf_path: Path to OPF file
        target_language: Target language
    """
    opf_root = opf_tree.getroot()
    metadata = opf_root.find('.//opf:metadata', namespaces=NAMESPACES)
    if metadata is not None:
        lang_el = metadata.find('.//dc:language', namespaces=NAMESPACES)
        if lang_el is not None:
            lang_el.text = target_language.lower()[:2]

    opf_tree.write(opf_path, encoding='utf-8', xml_declaration=True, pretty_print=True)


async def _save_epub(
    parsed_xhtml_docs: Dict[str, etree._Element],
    output_filepath: str,
    temp_dir: str,
    log_callback: Optional[Callable]
) -> None:
    """
    Save modified EPUB files and create output archive

    Args:
        parsed_xhtml_docs: Dictionary of parsed XHTML documents
        output_filepath: Output file path
        temp_dir: Temporary directory
        log_callback: Logging callback
    """
    # Save XHTML files
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
            _log_write_error(file_path_abs, e_write, log_callback)

    # Create output EPUB
    if log_callback:
        log_callback("epub_zip_start", "\nCreating translated EPUB file...")

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

    success_msg = f"Translated (Full/Partial) EPUB saved: '{output_filepath}'"
    if log_callback:
        log_callback("epub_save_success", success_msg)
    else:
        tqdm.write(success_msg)


async def _translate_epub_simple_mode(
    input_filepath: str,
    output_filepath: str,
    source_language: str,
    target_language: str,
    model_name: str,
    chunk_target_lines_arg: int,
    cli_api_endpoint: str,
    progress_callback: Optional[Callable],
    log_callback: Optional[Callable],
    stats_callback: Optional[Callable],
    check_interruption_callback: Optional[Callable],
    llm_provider: str,
    gemini_api_key: Optional[str],
    openai_api_key: Optional[str],
    context_window: int,
    auto_adjust_context: bool,
    min_chunk_size: int
) -> None:
    """
    Translate EPUB in simple mode (extract text, translate, rebuild)

    Args:
        See translate_epub_file() for parameter descriptions
    """
    if log_callback:
        log_callback("epub_simple_mode_active",
                   "Simple mode activated: extracting pure text for translation")

    from .epub_simple_processor import (
        extract_pure_text_from_epub,
        translate_text_as_string,
        create_simple_epub
    )

    try:
        # Phase 1: Extract pure text
        pure_text, metadata = await extract_pure_text_from_epub(input_filepath, log_callback)

        # Phase 2: Translate
        translated_text = await translate_text_as_string(
            pure_text, source_language, target_language, model_name,
            cli_api_endpoint, chunk_target_lines_arg,
            progress_callback=progress_callback,
            log_callback=log_callback,
            stats_callback=stats_callback,
            check_interruption_callback=check_interruption_callback,
            llm_provider=llm_provider,
            gemini_api_key=gemini_api_key,
            openai_api_key=openai_api_key,
            context_window=context_window,
            auto_adjust_context=auto_adjust_context,
            min_chunk_size=min_chunk_size
        )

        # Phase 3: Rebuild EPUB
        await create_simple_epub(
            translated_text, output_filepath, metadata, target_language, log_callback
        )

        if log_callback:
            log_callback("epub_simple_mode_complete",
                       f"Simple mode: EPUB translation complete - {output_filepath}")

    except Exception as e:
        _log_simple_mode_error(e, log_callback)


# Helper functions for file discovery and logging

def _find_opf_file(temp_dir: str) -> Optional[str]:
    """Find OPF file in extracted EPUB"""
    for root_dir, _, files in os.walk(temp_dir):
        for file in files:
            if file.endswith('.opf'):
                return os.path.join(root_dir, file)
    return None


def _get_content_files_from_spine(spine: etree._Element, manifest: etree._Element) -> List[str]:
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


def _log_no_translatable_content(log_callback: Optional[Callable], progress_callback: Optional[Callable]) -> None:
    """Log when no translatable content found"""
    msg = "No translatable text segments found in the EPUB."
    if log_callback:
        log_callback("epub_no_translatable_segments", msg)
    else:
        tqdm.write(msg)
    if progress_callback:
        progress_callback(100)


def _log_file_not_found(content_href: str, file_path: str, log_callback: Optional[Callable]) -> None:
    """Log file not found warning"""
    warn_msg = f"WARNING: EPUB file '{content_href}' not found at '{file_path}', ignored."
    if log_callback:
        log_callback("epub_content_file_not_found", warn_msg)
    else:
        tqdm.write(warn_msg)


def _log_xml_error(content_href: str, error: Exception, log_callback: Optional[Callable]) -> None:
    """Log XML syntax error"""
    err_msg = f"XML Syntax ERROR in '{content_href}': {error}. Ignored."
    if log_callback:
        log_callback("epub_xml_syntax_error", err_msg)
    else:
        tqdm.write(err_msg)


def _log_collection_error(content_href: str, error: Exception, log_callback: Optional[Callable]) -> None:
    """Log job collection error"""
    err_msg = f"ERROR Collecting chapter jobs '{content_href}': {error}. Ignored."
    if log_callback:
        log_callback("epub_collect_job_error", err_msg)
    else:
        tqdm.write(err_msg)


def _log_interruption(job_idx: int, total_jobs: int, log_callback: Optional[Callable]) -> None:
    """Log user interruption"""
    msg = f"EPUB translation process (job {job_idx+1}/{total_jobs}) interrupted by user signal."
    if log_callback:
        log_callback("epub_translation_interrupted", msg)
    else:
        tqdm.write(f"\nEPUB translation interrupted by user at job {job_idx+1}/{total_jobs}.")


def _log_write_error(file_path: str, error: Exception, log_callback: Optional[Callable]) -> None:
    """Log file write error"""
    err_msg = f"ERROR writing modified EPUB file '{file_path}': {error}"
    if log_callback:
        log_callback("epub_write_error", err_msg)
    else:
        tqdm.write(err_msg)


def _log_major_error(error: Exception, input_filepath: str, log_callback: Optional[Callable]) -> None:
    """Log major error"""
    major_err_msg = f"MAJOR ERROR processing EPUB '{input_filepath}': {error}"
    if log_callback:
        log_callback("epub_major_error", major_err_msg)
        import traceback
        log_callback("epub_major_error_traceback", traceback.format_exc())
    else:
        print(major_err_msg)
        import traceback
        traceback.print_exc()


def _log_simple_mode_error(error: Exception, log_callback: Optional[Callable]) -> None:
    """Log simple mode error"""
    err_msg = f"ERROR in simple mode EPUB translation: {error}"
    if log_callback:
        log_callback("epub_simple_mode_error", err_msg)
        import traceback
        log_callback("epub_simple_mode_traceback", traceback.format_exc())
    else:
        print(err_msg)
        import traceback
        traceback.print_exc()
