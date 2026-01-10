"""
Simplified EPUB translation using full-body serialization

This module provides a simplified approach to EPUB translation that:
1. Extracts the entire body as HTML string
2. Replaces all tags with placeholders (TagPreserver)
3. Chunks intelligently by complete HTML blocks (HtmlChunker)
4. Renumbers placeholders locally for each chunk (0, 1, 2...)
5. Translates each chunk (sends with local indices to LLM)
6. Restores global indices after translation (PlaceholderManager)
7. Restores tags and replaces the body

Translation flow with retry:
1. Phase 1: Normal translation (with retry attempts)
2. Phase 2: Return untranslated text if all retries fail

Placeholder Indexing Architecture:
===================================

LEVEL 1 - Document level (TagPreserver):
    Input HTML: "<body><p>Hello</p></body>"
    → Preserves tags as placeholders: "[id0]Hello[id1]"
    → global_tag_map: {"[id0]": "<body><p>", "[id1]": "</p></body>"}

LEVEL 2 - Chunk level (HtmlChunker):
    Global text: "[id5]Hello[id6] [id7]World[id8]"
    → Chunk 1: "[id0]Hello[id1]" (renumbered locally)
    → global_indices: [5, 6] (mapping to restore later)
    → Chunk 2: "[id0]World[id1]" (renumbered locally)
    → global_indices: [7, 8]

LEVEL 3 - Translation (PlaceholderManager):
    Chunk text: "[id0]Hello[id1]" (sent to LLM as-is)
    LLM returns: "[id0]Bonjour[id1]"
    → Restored: "[id5]Bonjour[id6]" (global indices)
"""
import re
from collections import Counter
from typing import List, Dict, Any, Optional, Callable, Tuple
from lxml import etree

from .body_serializer import extract_body_html, replace_body_content
from .html_chunker import (
    HtmlChunker,
    TranslationStats
)
from .tag_preservation import TagPreserver
from .exceptions import (
    PlaceholderValidationError,
    TagRestorationError,
    XmlParsingError
)
from .placeholder_validator import PlaceholderValidator
from .container import TranslationContainer
from ..translator import generate_translation_request
from ..context_optimizer import AdaptiveContextManager, INITIAL_CONTEXT_SIZE, CONTEXT_STEP, MAX_CONTEXT_SIZE
from src.config import (
    PLACEHOLDER_PATTERN,
    MAX_PLACEHOLDER_CORRECTION_ATTEMPTS,
    create_placeholder,
    detect_placeholder_format_in_text,
    detect_format_from_placeholder,
    THINKING_MODELS,
    ADAPTIVE_CONTEXT_INITIAL_THINKING,
)
from prompts.prompts import generate_placeholder_correction_prompt, CORRECTED_TAG_IN, CORRECTED_TAG_OUT
from src.utils.structure_debug_logger import StructureDebugLogger


class PlaceholderManager:
    """
    Manages placeholder indexing during chunk processing.

    This class converts between local chunk indices (0, 1, 2...) and global document indices.
    No boundary stripping is performed - that's already handled by TagPreserver at the document level.

    Key principle: Simple renumbering - local indices (from chunker) to global indices (for final document).

    Example:
        chunk_text = "[[0]]Hello [[1]]world[[2]]"
        global_indices = [5, 6, 7]

        manager = PlaceholderManager()
        # Send chunk_text to LLM as-is (already has local indices 0,1,2)
        translated = "[[0]]Bonjour [[1]]monde[[2]]"

        # Restore to global indices
        restored = manager.restore_to_global(translated, global_indices)
        # Result: "[[5]]Bonjour [[6]]monde[[7]]"
    """

    @staticmethod
    def restore_to_global(translated_text: str, global_indices: List[int]) -> str:
        """
        Convert local placeholder indices (0, 1, 2...) to global indices.

        Args:
            translated_text: Text with local placeholders (0, 1, 2...)
            global_indices: List of global indices to restore

        Returns:
            Text with global placeholder indices
        """
        if not global_indices:
            return translated_text

        result = translated_text

        # Detect placeholder format from the text
        prefix, suffix = detect_placeholder_format_in_text(result)

        # Renumber from local to global using temp markers to avoid conflicts
        for local_idx in range(len(global_indices)):
            local_ph = f"{prefix}{local_idx}{suffix}"
            if local_ph in result:
                result = result.replace(local_ph, f"__RESTORE_{local_idx}__")

        for local_idx, global_idx in enumerate(global_indices):
            result = result.replace(f"__RESTORE_{local_idx}__", f"{prefix}{global_idx}{suffix}")

        return result


def validate_placeholders(translated_text: str, local_tag_map: Dict[str, str]) -> bool:
    """
    Validate that translated text contains all expected placeholders.

    Automatically detects placeholder format from the tag_map keys.

    Args:
        translated_text: Text with placeholders after translation
        local_tag_map: Expected local tag map

    Returns:
        True if all placeholders present and valid
    """
    # Use centralized PlaceholderValidator
    is_valid, error_msg = PlaceholderValidator.validate_strict(translated_text, local_tag_map)
    return is_valid


def build_specific_error_details(translated_text: str, expected_count: int, local_tag_map: Dict[str, str] = None) -> str:
    """
    Analyze placeholder errors and generate a detailed error message in English.

    Args:
        translated_text: Translated text to analyze
        expected_count: Number of placeholders expected (0 to expected_count-1)
        local_tag_map: Optional tag map to detect format from

    Returns:
        Detailed error message for the correction prompt
    """
    errors = []

    # Detect format from tag_map keys
    current_format = "safe"
    if local_tag_map:
        sample_placeholder = next((k for k in local_tag_map.keys() if not k.startswith("__")), "[[0]]")
        current_format = detect_format_from_placeholder(sample_placeholder)

    # Set appropriate pattern and placeholder functions based on format
    if current_format == "id":
        pattern = r'\[id(\d+)\]'
        prefix = "[id"
        suffix = "]"
    elif current_format == "slash":
        pattern = r'/(\d+)(?!/)'
        prefix = "/"
        suffix = ""
    elif current_format == "dollar":
        pattern = r'\$(\d+)\$'
        prefix = "$"
        suffix = "$"
    elif current_format == "simple":
        pattern = r'(?<!\[)\[(\d+)\](?!\])'
        prefix = "["
        suffix = "]"
    else:  # safe
        pattern = r'\[\[(\d+)\]\]'
        prefix = "[["
        suffix = "]]"

    def make_placeholder(i):
        return f"{prefix}{i}{suffix}"

    # 1. Find correct placeholders present
    found_correct = re.findall(pattern, translated_text)
    # Extract indices from found placeholders
    found_indices = [int(num_str) for num_str in found_correct]
    expected_indices = set(range(expected_count))

    # 2. Detect missing placeholders
    found_set = set(found_indices)
    missing = expected_indices - found_set
    if missing:
        missing_str = ", ".join(make_placeholder(i) for i in sorted(missing))
        errors.append(f"- Missing placeholders: {missing_str}")

    # 3. Detect duplicates
    counts = Counter(found_indices)
    duplicates = {idx: count for idx, count in counts.items() if count > 1}
    if duplicates:
        for idx, count in duplicates.items():
            errors.append(f"- Duplicate: {make_placeholder(idx)} appears {count} times (should appear once)")

    # 4. Check order
    if found_indices != sorted(found_indices):
        errors.append("- Out of order: placeholders are not in sequential order")

    # 5. Count summary
    if len(found_correct) != expected_count:
        errors.append(f"- Count mismatch: Expected {expected_count} placeholders, found {len(found_correct)}")

    # 6. Position hint - if count matches but indices don't, placeholders are shifted
    if len(found_correct) == expected_count and found_set != expected_indices:
        # Some placeholders have wrong indices (shifted)
        wrong_indices = found_set - expected_indices
        if wrong_indices:
            wrong_str = ", ".join(make_placeholder(i) for i in sorted(wrong_indices))
            errors.append(f"- Wrong indices used: {wrong_str} (should be {make_placeholder(0)} to {make_placeholder(expected_count - 1)})")

    if errors:
        error_msg = "ERRORS FOUND:\n" + "\n".join(errors)
        error_msg += "\n\nIMPORTANT: Compare the ORIGINAL text to see where each placeholder should be positioned around the equivalent translated content."
        return error_msg
    return "No specific errors detected, but validation failed. Check placeholder positions against the original text."


def extract_corrected_text(response: str) -> Optional[str]:
    """
    Extract the corrected text from LLM response.

    Args:
        response: Raw LLM response

    Returns:
        Extracted text or None if tags not found
    """
    if CORRECTED_TAG_IN not in response or CORRECTED_TAG_OUT not in response:
        return None

    start = response.find(CORRECTED_TAG_IN) + len(CORRECTED_TAG_IN)
    end = response.find(CORRECTED_TAG_OUT)

    if start >= end:
        return None

    return response[start:end].strip()


async def attempt_placeholder_correction(
    original_text: str,
    translated_text: str,
    local_tag_map: Dict[str, str],
    source_language: str,
    target_language: str,
    llm_client: Any,
    log_callback: Optional[Callable],
    placeholder_format: Optional[Tuple[str, str]] = None,
    context_manager: Optional[AdaptiveContextManager] = None
) -> Tuple[str, bool]:
    """
    Attempt to correct placeholder errors via LLM.

    Args:
        original_text: Source text with correct placeholders
        translated_text: Translation with placeholder errors
        local_tag_map: Expected local tag map
        source_language: Source language name
        target_language: Target language name
        llm_client: LLM client instance
        log_callback: Optional logging callback
        placeholder_format: Optional tuple of (prefix, suffix) for placeholders
        context_manager: Optional AdaptiveContextManager for handling context overflow

    Returns:
        Tuple (corrected_text, success)
    """
    expected_count = len(local_tag_map)

    # Generate error details
    specific_errors = build_specific_error_details(translated_text, expected_count, local_tag_map)

    # Generate correction prompt
    prompt_pair = generate_placeholder_correction_prompt(
        original_text=original_text,
        translated_text=translated_text,
        specific_errors=specific_errors,
        source_language=source_language,
        target_language=target_language,
        expected_count=expected_count,
        placeholder_format=placeholder_format
    )

    # Call LLM for correction with adaptive context retry
    max_retries = 3
    for retry in range(max_retries):
        try:
            # Log the correction request
            if log_callback and retry == 0:
                log_callback("correction_request", "Sending correction request to LLM")

            # Set context from manager if available
            if context_manager and hasattr(llm_client, 'context_window'):
                new_ctx = context_manager.get_context_size()
                if llm_client.context_window != new_ctx:
                    if log_callback:
                        log_callback("context_update",
                            f"📐 Correction: Updating context window: {llm_client.context_window} → {new_ctx}")
                llm_client.context_window = new_ctx

            llm_response = await llm_client.make_request(
                prompt_pair.user,
                system_prompt=prompt_pair.system
            )

            if llm_response is None:
                return translated_text, False

            # Check if we should retry with larger context (adaptive strategy)
            if context_manager and llm_response.was_truncated:
                if context_manager.should_retry_with_larger_context(
                    llm_response.was_truncated, llm_response.context_used
                ):
                    context_manager.increase_context()
                    if log_callback:
                        log_callback("correction_context_retry",
                            f"Retrying correction with larger context ({context_manager.get_context_size()} tokens)")
                    continue  # Retry with larger context

            # Record success if context manager is available
            if context_manager and llm_response.prompt_tokens > 0:
                context_manager.record_success(
                    llm_response.prompt_tokens,
                    llm_response.completion_tokens,
                    llm_response.context_limit
                )

            # Extract corrected text from response content
            corrected = extract_corrected_text(llm_response.content)
            if corrected is None:
                if log_callback:
                    log_callback("correction_extract_failed", "Failed to extract corrected text from response")
                return translated_text, False

            # Validate corrected text
            if validate_placeholders(corrected, local_tag_map):
                return corrected, True

            return translated_text, False

        except Exception as e:
            # Try to increase context if we have a manager and hit overflow/repetition errors
            from ..llm_providers import ContextOverflowError, RepetitionLoopError

            if context_manager and isinstance(e, (ContextOverflowError, RepetitionLoopError)):
                if context_manager.should_retry_with_larger_context(True, 0):
                    context_manager.increase_context()
                    if log_callback:
                        log_callback("correction_context_overflow",
                            f"Context overflow in correction - retrying with {context_manager.get_context_size()} tokens")
                    continue  # Retry with larger context

            if log_callback:
                log_callback("correction_error", f"Correction attempt failed: {str(e)}")
            return translated_text, False

    # Max retries exceeded
    return translated_text, False


async def translate_chunk_with_fallback(
    chunk_text: str,
    local_tag_map: Dict[str, str],
    global_indices: List[int],
    source_language: str,
    target_language: str,
    model_name: str,
    llm_client: Any,
    stats: TranslationStats,
    log_callback: Optional[Callable] = None,
    max_retries: int = 1,
    context_manager: Optional[AdaptiveContextManager] = None,
    placeholder_format: Optional[Tuple[str, str]] = None,
    debug_logger: Optional[StructureDebugLogger] = None,
    chunk_index: int = 0
) -> str:
    """
    Translate a chunk with retry mechanism.

    Translation flow:
    1. Phase 1: Normal translation (up to max_retries attempts)
    2. Phase 2: Return untranslated text if all retries fail
    3. Restore global indices

    Args:
        chunk_text: Text with local placeholders (0, 1, 2...)
        local_tag_map: Local placeholder to tag mapping
        global_indices: Global indices for this chunk (maps local → global)
        source_language: Source language
        target_language: Target language
        model_name: LLM model name
        llm_client: LLM client
        stats: TranslationStats instance for tracking
        log_callback: Optional logging callback
        max_retries: Maximum translation retry attempts (default from config)
        context_manager: Optional AdaptiveContextManager for handling context overflow

    Returns:
        Translated text with global placeholders restored
    """
    stats.total_chunks += 1

    # Initialize placeholder manager
    placeholder_mgr = PlaceholderManager()

    # Calculate if this chunk has placeholders
    has_placeholders = len(local_tag_map) > 0

    # DEBUG: Log translation request
    if debug_logger:
        debug_logger.log_translation_request(chunk_index, chunk_text, has_placeholders)

    # ==========================================================================
    # PHASE 1: Normal translation with retries
    # ==========================================================================
    translated = None

    for attempt in range(max_retries):
        if log_callback and max_retries > 1:
            log_callback("translation_attempt", f"Translation attempt {attempt + 1}/{max_retries}")

        # Send chunk as-is to LLM (already has local indices 0, 1, 2...)
        translated = await generate_translation_request(
            chunk_text,
            context_before="",
            context_after="",
            previous_translation_context="",
            source_language=source_language,
            target_language=target_language,
            model=model_name,
            llm_client=llm_client,
            log_callback=log_callback,
            has_placeholders=has_placeholders,
            context_manager=context_manager,
            placeholder_format=placeholder_format
        )

        if translated is None:
            if log_callback:
                log_callback("chunk_translation_failed", f"Attempt {attempt + 1}/{max_retries}: Translation returned None")
            stats.retry_attempts += 1
            continue  # Try again

        # Validate placeholders
        validation_result = validate_placeholders(translated, local_tag_map)

        # DEBUG: Log translation response (only failures)
        if debug_logger:
            debug_logger.log_translation_response(
                chunk_index,
                translated,
                len(local_tag_map),
                validation_result,
                retry_attempt=attempt
            )

        if validation_result:
            # Success - restore to global indices
            if attempt == 0:
                stats.successful_first_try += 1
            else:
                stats.successful_after_retry += 1
                if log_callback:
                    log_callback("retry_success", f"Translation succeeded after {attempt + 1} attempt(s)")

            result = placeholder_mgr.restore_to_global(translated, global_indices)

            # DEBUG: Log global restoration (only if problems occur, checked inside function)
            if debug_logger:
                debug_logger.log_global_restoration(
                    chunk_index,
                    translated,
                    result,
                    global_indices,
                    is_fallback=False
                )

            return result
        else:
            if log_callback:
                log_callback("placeholder_mismatch", f"Attempt {attempt + 1}/{max_retries}: Placeholder validation failed")
            stats.retry_attempts += 1
            # Continue to next retry attempt

    # ==========================================================================
    # PHASE 2: Return untranslated text (all retry attempts failed)
    # ==========================================================================
    stats.fallback_used += 1

    if log_callback:
        log_callback("fallback_untranslated",
            "All translation attempts failed - returning original untranslated text")

    # Return the original chunk_text with global indices restored
    result_final = placeholder_mgr.restore_to_global(chunk_text, global_indices)

    # DEBUG: Log fallback usage
    if debug_logger:
        debug_logger.log_fallback_usage(
            chunk_index,
            "untranslated",
            f"All {max_retries} translation attempts failed validation - returning untranslated text",
            original_text=chunk_text,
            translated_text=translated if translated is not None else "None (translation failed)",
            positions_before={},
            positions_after={},
            result_with_placeholders=chunk_text
        )
        debug_logger.log_global_restoration(
            chunk_index,
            chunk_text,
            result_final,
            global_indices,
            is_fallback=True
        )

    return result_final


# === Private Helper Functions ===

def _setup_translation(
    doc_root: etree._Element,
    enable_structure_debug: bool = True,
    translation_id: str = None,
    file_path: str = None,
    log_callback: Optional[Callable] = None,
    container: Optional[TranslationContainer] = None
) -> Tuple[str, etree._Element, TagPreserver, Optional[StructureDebugLogger]]:
    """Extract body HTML and initialize tag preserver.

    Args:
        doc_root: XHTML document root
        enable_structure_debug: Enable detailed structure debugging
        translation_id: Optional translation ID for debug logs
        file_path: Optional file path for debug logs
        log_callback: Optional logging callback
        container: Optional dependency injection container (uses default if None)

    Returns:
        Tuple of (body_html, body_element, tag_preserver, debug_logger)
    """
    # Initialize debug logger if enabled
    debug_logger = None
    if enable_structure_debug:
        debug_logger = StructureDebugLogger(translation_id=translation_id)
        if log_callback:
            log_callback("debug_logger", f"Structure debug logging enabled: {debug_logger.log_file}")

    # Extract body
    body_html, body_element = extract_body_html(doc_root)

    # DEBUG: Log original HTML
    if debug_logger:
        debug_logger.log_original_html(body_html, file_path)

    # Initialize tag preserver (use container if provided, otherwise create directly)
    if container is not None:
        tag_preserver = container.tag_preserver
    else:
        tag_preserver = TagPreserver()

    return body_html, body_element, tag_preserver, debug_logger


def _preserve_tags(
    body_html: str,
    tag_preserver: TagPreserver,
    debug_logger: Optional[StructureDebugLogger],
    log_callback: Optional[Callable] = None
) -> Tuple[str, Dict[str, str], Tuple[str, str]]:
    """Replace HTML tags with placeholders.

    Args:
        body_html: HTML content to process
        tag_preserver: TagPreserver instance
        debug_logger: Optional debug logger
        log_callback: Optional logging callback

    Returns:
        Tuple of (text_with_placeholders, global_tag_map, placeholder_format)
    """
    text_with_placeholders, global_tag_map = tag_preserver.preserve_tags(body_html)

    # Extract placeholder format for prompt generation
    placeholder_format = (tag_preserver.placeholder_prefix, tag_preserver.placeholder_suffix)

    if log_callback:
        format_info = f" using format {placeholder_format[0]}N{placeholder_format[1]}"
        log_callback("tags_preserved", f"Preserved {len(global_tag_map)} tag groups{format_info}")

    # DEBUG: Log tag preservation
    if debug_logger:
        debug_logger.log_tag_preservation(text_with_placeholders, global_tag_map, placeholder_format)

    return text_with_placeholders, global_tag_map, placeholder_format


def _create_chunks(
    text: str,
    tag_map: Dict[str, str],
    max_tokens: int,
    debug_logger: Optional[StructureDebugLogger],
    log_callback: Optional[Callable] = None,
    container: Optional[TranslationContainer] = None
) -> List[Dict]:
    """Chunk text into translatable segments.

    Args:
        text: Text with placeholders
        tag_map: Global tag map
        max_tokens: Maximum tokens per chunk
        debug_logger: Optional debug logger
        log_callback: Optional logging callback
        container: Optional dependency injection container (uses default if None)

    Returns:
        List of chunk dictionaries
    """
    # Use container's chunker if provided, otherwise create directly
    if container is not None:
        chunker = container.chunker
    else:
        chunker = HtmlChunker(max_tokens=max_tokens)

    chunks = chunker.chunk_html_with_placeholders(text, tag_map)

    if log_callback:
        log_callback("chunks_created", f"Created {len(chunks)} chunks")

    # DEBUG: Log chunk creation
    if debug_logger:
        debug_logger.log_chunk_creation(chunks, tag_map)

    return chunks


async def _translate_all_chunks(
    chunks: List[Dict],
    source_language: str,
    target_language: str,
    model_name: str,
    llm_client: Any,
    max_retries: int,
    context_manager: Optional[AdaptiveContextManager],
    placeholder_format: Tuple[str, str],
    debug_logger: Optional[StructureDebugLogger],
    log_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None
) -> Tuple[List[str], TranslationStats]:
    """Translate all chunks with fallback.

    Args:
        chunks: List of chunk dictionaries
        source_language: Source language name
        target_language: Target language name
        model_name: LLM model name
        llm_client: LLM client instance
        max_retries: Maximum retry attempts per chunk
        context_manager: Optional context window manager
        placeholder_format: Tuple of (prefix, suffix) for placeholders
        debug_logger: Optional debug logger
        log_callback: Optional callback for progress
        progress_callback: Optional callback for progress percentage

    Returns:
        Tuple of (translated_chunks, statistics)
    """
    stats = TranslationStats()
    translated_chunks = []

    for i, chunk in enumerate(chunks):
        if progress_callback:
            progress_callback((i / len(chunks)) * 100)

        translated = await translate_chunk_with_fallback(
            chunk_text=chunk['text'],
            local_tag_map=chunk['local_tag_map'],
            global_indices=chunk['global_indices'],
            source_language=source_language,
            target_language=target_language,
            model_name=model_name,
            llm_client=llm_client,
            stats=stats,
            log_callback=log_callback,
            max_retries=max_retries,
            context_manager=context_manager,
            placeholder_format=placeholder_format,
            debug_logger=debug_logger,
            chunk_index=i
        )
        translated_chunks.append(translated)

    return translated_chunks, stats


def _reconstruct_html(
    translated_chunks: List[str],
    global_tag_map: Dict[str, str],
    tag_preserver: TagPreserver,
    debug_logger: Optional[StructureDebugLogger]
) -> str:
    """Reconstruct full HTML from translated chunks.

    Args:
        translated_chunks: List of translated chunk texts
        global_tag_map: Global tag map
        tag_preserver: TagPreserver instance
        debug_logger: Optional debug logger

    Returns:
        Reconstructed HTML string
    """
    full_translated_text = ''.join(translated_chunks)
    final_html = tag_preserver.restore_tags(full_translated_text, global_tag_map)

    # DEBUG: Log tag restoration
    if debug_logger:
        debug_logger.log_tag_restoration(full_translated_text, final_html, global_tag_map)

    return final_html


def _replace_body(
    body_element: etree._Element,
    new_html: str,
    debug_logger: Optional[StructureDebugLogger]
) -> bool:
    """Replace body content with translated HTML.

    Args:
        body_element: Body element to update
        new_html: New HTML content
        debug_logger: Optional debug logger

    Returns:
        True if successful, False otherwise
    """
    # Capture XML parsing errors if they occur
    xml_errors = []
    try:
        replace_body_content(body_element, new_html)
        xml_success = True
    except Exception as e:
        xml_success = False
        xml_errors.append(str(e))

    # DEBUG: Log XML validation
    if debug_logger:
        # Try to parse the HTML to check for errors
        from lxml import etree as ET
        parser = ET.XMLParser(recover=True)
        try:
            ET.fromstring(f"<root>{new_html}</root>", parser)
            parse_errors = [str(err) for err in parser.error_log]
            debug_logger.log_xml_validation(new_html, xml_success, parse_errors if parse_errors else xml_errors)
        except Exception as e:
            debug_logger.log_xml_validation(new_html, False, [str(e)])

    return xml_success


def _report_statistics(
    stats: TranslationStats,
    debug_logger: Optional[StructureDebugLogger],
    log_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None
) -> None:
    """Report translation statistics.

    Args:
        stats: TranslationStats instance
        debug_logger: Optional debug logger
        log_callback: Optional callback for logging
        progress_callback: Optional callback for progress percentage
    """
    stats.log_summary(log_callback)

    # DEBUG: Log summary
    if debug_logger:
        debug_logger.log_summary(stats)

    if log_callback:
        log_callback("translation_complete", "Body translation complete")

    if progress_callback:
        progress_callback(100)


async def translate_xhtml_simplified(
    doc_root: etree._Element,
    source_language: str,
    target_language: str,
    model_name: str,
    llm_client: Any,
    max_tokens_per_chunk: int = 450,
    log_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None,
    context_manager: Optional[AdaptiveContextManager] = None,
    max_retries: int = 1,
    translation_id: str = None,
    file_path: str = None,
    enable_structure_debug: bool = True,
    container: Optional[TranslationContainer] = None
) -> bool:
    """
    Translate an XHTML document using the simplified approach.

    Simplified to call focused sub-functions for each step.
    Main orchestration function is now ~40 lines total.

    1. Extract body as HTML string
    2. Replace all tags with placeholders
    3. Chunk by complete HTML blocks with local renumbering
    4. Translate each chunk (with retry attempts)
    5. Reconstruct and replace body

    Args:
        doc_root: Parsed XHTML document (modified in-place)
        source_language: Source language
        target_language: Target language
        model_name: LLM model name
        llm_client: LLM client
        max_tokens_per_chunk: Maximum tokens per chunk
        log_callback: Optional logging callback
        progress_callback: Optional progress callback (0-100)
        context_manager: Optional AdaptiveContextManager for handling context overflow
        max_retries: Maximum translation retry attempts per chunk
        translation_id: Optional translation ID for debug logs
        file_path: Optional file path for debug logs
        enable_structure_debug: Enable detailed structure debugging (default: True)
        container: Optional dependency injection container for components

    Returns:
        True if successful, False otherwise
    """
    # 1. Setup
    body_html, body_element, tag_preserver, debug_logger = _setup_translation(
        doc_root,
        enable_structure_debug,
        translation_id,
        file_path,
        log_callback,
        container
    )

    if not body_html or body_element is None:
        if log_callback:
            log_callback("no_body", "No <body> element found")
        return False

    # 2. Tag Preservation
    text_with_placeholders, global_tag_map, placeholder_format = _preserve_tags(
        body_html,
        tag_preserver,
        debug_logger,
        log_callback
    )

    # 3. Chunking
    chunks = _create_chunks(
        text_with_placeholders,
        global_tag_map,
        max_tokens_per_chunk,
        debug_logger,
        log_callback,
        container
    )

    # 4. Translation
    translated_chunks, stats = await _translate_all_chunks(
        chunks=chunks,
        source_language=source_language,
        target_language=target_language,
        model_name=model_name,
        llm_client=llm_client,
        max_retries=max_retries,
        context_manager=context_manager,
        placeholder_format=placeholder_format,
        debug_logger=debug_logger,
        log_callback=log_callback,
        progress_callback=progress_callback
    )

    # 5. Reconstruction
    final_html = _reconstruct_html(
        translated_chunks,
        global_tag_map,
        tag_preserver,
        debug_logger
    )

    # 6. Replace body
    xml_success = _replace_body(body_element, final_html, debug_logger)

    # 7. Report stats
    _report_statistics(stats, debug_logger, log_callback, progress_callback)

    return xml_success
