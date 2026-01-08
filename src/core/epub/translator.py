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
from typing import Dict, Any, Optional, Callable
from lxml import etree
from tqdm.auto import tqdm

from src.config import (
    NAMESPACES, DEFAULT_MODEL, MAIN_LINES_PER_CHUNK, API_ENDPOINT,
    MAX_TOKENS_PER_CHUNK
)
from .simplified_translator import translate_xhtml_simplified
from ..post_processor import clean_residual_tag_placeholders


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
) -> None:
    """
    Translate an EPUB file using LLM with simplified mode.

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
    """
    if not os.path.exists(input_filepath):
        err_msg = f"ERROR: Input EPUB file '{input_filepath}' not found."
        if log_callback:
            log_callback("epub_input_file_not_found", err_msg)
        else:
            print(err_msg)
        return

    # Create LLM client
    from ..llm_client import create_llm_client
    llm_client = create_llm_client(
        llm_provider, gemini_api_key, cli_api_endpoint, model_name,
        openai_api_key, openrouter_api_key, log_callback=log_callback
    )

    if llm_client is None:
        err_msg = "ERROR: Could not create LLM client."
        if log_callback:
            log_callback("llm_client_error", err_msg)
        else:
            print(err_msg)
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Phase 1: Extract EPUB
            if log_callback:
                log_callback("epub_extract_start", "Extracting EPUB...")

            with zipfile.ZipFile(input_filepath, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

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

            # Phase 2: Translate each XHTML file
            parsed_xhtml_docs: Dict[str, etree._Element] = {}
            total_files = len(content_files)
            completed_files = 0
            failed_files = 0

            if stats_callback:
                stats_callback({
                    'total_chunks': total_files,
                    'completed_chunks': 0,
                    'failed_chunks': 0
                })

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

                # Skip already processed files on resume
                if file_idx < resume_from_index:
                    completed_files += 1
                    continue

                # Update progress
                if progress_callback:
                    progress_percent = ((file_idx / total_files) * 90) + 5
                    progress_callback(progress_percent)

                file_path_abs = os.path.normpath(os.path.join(opf_dir, content_href))
                if not os.path.exists(file_path_abs):
                    if log_callback:
                        log_callback("epub_file_not_found",
                                     f"WARNING: File '{content_href}' not found, skipped.")
                    failed_files += 1
                    continue

                try:
                    # Parse XHTML file
                    async with aiofiles.open(file_path_abs, 'r', encoding='utf-8') as f_chap:
                        chap_str_content = await f_chap.read()

                    parser = etree.XMLParser(encoding='utf-8', recover=True, remove_blank_text=False)
                    doc_root = etree.fromstring(chap_str_content.encode('utf-8'), parser)

                    if log_callback:
                        log_callback("epub_file_translate_start",
                                     f"Translating file {file_idx + 1}/{total_files}: {content_href}")

                    # Create file-specific progress callback
                    def file_progress_callback(file_progress):
                        if progress_callback:
                            # Map file progress (0-100) to overall progress
                            base_progress = ((file_idx / total_files) * 90) + 5
                            file_contribution = (file_progress / 100) * (90 / total_files)
                            progress_callback(base_progress + file_contribution)

                    # Translate using simplified mode
                    success = await translate_xhtml_simplified(
                        doc_root=doc_root,
                        source_language=source_language,
                        target_language=target_language,
                        model_name=model_name,
                        llm_client=llm_client,
                        max_tokens_per_chunk=max_tokens_per_chunk,
                        log_callback=log_callback,
                        progress_callback=file_progress_callback
                    )

                    if success:
                        parsed_xhtml_docs[file_path_abs] = doc_root
                        completed_files += 1
                        if log_callback:
                            log_callback("epub_file_translate_complete",
                                         f"Completed file {file_idx + 1}/{total_files}: {content_href}")
                    else:
                        failed_files += 1
                        if log_callback:
                            log_callback("epub_file_translate_failed",
                                         f"Failed to translate file {file_idx + 1}/{total_files}: {content_href}")

                    # Update statistics
                    if stats_callback:
                        stats_callback({
                            'completed_chunks': completed_files,
                            'failed_chunks': failed_files
                        })

                    # Save checkpoint after each file
                    if checkpoint_manager and translation_id:
                        checkpoint_manager.save_checkpoint(
                            translation_id,
                            file_idx + 1,
                            {'last_file': content_href}
                        )

                except etree.XMLSyntaxError as e_xml:
                    failed_files += 1
                    if log_callback:
                        log_callback("epub_xml_error",
                                     f"XML error in '{content_href}': {e_xml}")
                except Exception as e_file:
                    failed_files += 1
                    if log_callback:
                        log_callback("epub_file_error",
                                     f"Error processing '{content_href}': {e_file}")

            # Phase 3: Save modified XHTML files
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

            # Phase 4: Update metadata
            _update_epub_metadata(opf_tree, opf_path, target_language)

            # Phase 5: Create output EPUB
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

            # Final summary
            if log_callback:
                log_callback("epub_save_success",
                             f"Translated EPUB saved: '{output_filepath}' "
                             f"({completed_files} files translated, {failed_files} failed)")
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
    from src.config import SIGNATURE_ENABLED, PROJECT_NAME, PROJECT_GITHUB

    opf_root = opf_tree.getroot()
    metadata = opf_root.find('.//opf:metadata', namespaces=NAMESPACES)
    if metadata is not None:
        # Update language
        lang_el = metadata.find('.//dc:language', namespaces=NAMESPACES)
        if lang_el is not None:
            lang_el.text = target_language.lower()[:2]

        # Add translation signature if enabled
        if SIGNATURE_ENABLED:
            # Add contributor (translator) - Dublin Core standard
            contributor_el = etree.SubElement(
                metadata,
                '{http://purl.org/dc/elements/1.1/}contributor'
            )
            contributor_el.text = PROJECT_NAME
            contributor_el.set('{http://www.idpf.org/2007/opf}role', 'trl')

            # Add or update description with signature
            desc_el = metadata.find('.//dc:description', namespaces=NAMESPACES)
            signature_text = f"\n\nTranslated using {PROJECT_NAME}\n{PROJECT_GITHUB}"

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
