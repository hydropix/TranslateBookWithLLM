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

Translation flow with multi-phase fallback:
1. Phase 1: Normal translation (with retry attempts)
2. Phase 2: Token alignment fallback (translate without placeholders, then reinsert)
3. Phase 3: Return untranslated text if all phases fail

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
from .html_chunker import HtmlChunker
from .translation_metrics import TranslationStats
from .tag_preservation import TagPreserver
from .exceptions import (
    PlaceholderValidationError,
    TagRestorationError,
    XmlParsingError,
    BodyExtractionError
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
from src.utils.unified_logger import LogLevel, LogType


def _log_error(log_callback: Optional[Callable], event_name: str, message: str):
    """Helper to log error messages in red color"""
    if log_callback:
        # Check if this is a new-style logger with LogLevel support
        try:
            from src.utils.unified_logger import get_logger
            logger = get_logger()
            logger.error(message)
        except Exception:
            # Fallback to legacy callback
            log_callback(event_name, message)


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
                _log_error(log_callback, "correction_extract_failed", "Failed to extract corrected text from response")
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

            _log_error(log_callback, "correction_error", f"Correction attempt failed: {str(e)}")
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
    placeholder_format: Optional[Tuple[str, str]] = None
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

    # ==========================================================================
    # PHASE 1: Normal translation with retries
    # ==========================================================================
    translated = None

    for attempt in range(max_retries):
        # Only log retry attempts (not the first attempt)
        if log_callback and attempt > 0:
            log_callback("translation_attempt", f"🔄 Translation retry attempt {attempt + 1}/{max_retries}")

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
            _log_error(log_callback, "chunk_translation_failed", f"Attempt {attempt + 1}/{max_retries}: Translation returned None")
            stats.retry_attempts += 1
            continue  # Try again

        # Validate placeholders
        validation_result = validate_placeholders(translated, local_tag_map)

        if validation_result:
            # Success - restore to global indices
            if attempt == 0:
                stats.successful_first_try += 1
            else:
                stats.successful_after_retry += 1
                if log_callback:
                    log_callback("retry_success", f"✓ Translation succeeded after {attempt + 1} attempt(s)")

            result = placeholder_mgr.restore_to_global(translated, global_indices)
            return result
        else:
            # Track placeholder error
            stats.placeholder_errors += 1
            _log_error(log_callback, "placeholder_mismatch", f"✗ Attempt {attempt + 1}/{max_retries}: Placeholder validation failed")
            stats.retry_attempts += 1
            # Continue to next retry attempt

    # ==========================================================================
    # PHASE 2: TOKEN ALIGNMENT FALLBACK
    # ==========================================================================
    from src.config import EPUB_TOKEN_ALIGNMENT_ENABLED

    if EPUB_TOKEN_ALIGNMENT_ENABLED:
        try:
            stats.token_alignment_used += 1  # Track Phase 2 usage
            if log_callback:
                log_callback("phase2_start", "⚙️ Phase 2: Using token alignment fallback (proportional tag repositioning)...")

            # 1. Extract clean text (without placeholders)
            from src.common.placeholder_format import PlaceholderFormat
            fmt = PlaceholderFormat.from_config()
            clean_text = fmt.remove_all(chunk_text)

            # 2. Translate WITHOUT placeholders (guaranteed to work)
            # Note: generate_translation_request will show its own logs during translation
            translated_clean = await generate_translation_request(
                clean_text,
                context_before="",
                context_after="",
                previous_translation_context="",
                source_language=source_language,
                target_language=target_language,
                model=model_name,
                llm_client=llm_client,
                log_callback=log_callback,
                has_placeholders=False,  # CRITICAL: no placeholder instructions
                context_manager=context_manager,
                placeholder_format=None  # No placeholders in prompt
            )

            if translated_clean is None:
                raise Exception("LLM returned None for clean translation")

            # 3. Initialize aligner (lazy loading, cached on function)
            if not hasattr(translate_chunk_with_fallback, '_aligner'):
                from .token_alignment_fallback import TokenAlignmentFallback
                translate_chunk_with_fallback._aligner = TokenAlignmentFallback()

            # 4. Align and reinsert placeholders
            placeholders_list = list(local_tag_map.keys())  # ["[id0]", "[id1]", ...]

            result_with_placeholders = translate_chunk_with_fallback._aligner.align_and_insert_placeholders(
                original_with_placeholders=chunk_text,
                translated_without_placeholders=translated_clean,
                placeholders=placeholders_list
            )

            # 5. Validate (should always pass, but check anyway)
            if validate_placeholders(result_with_placeholders, local_tag_map):
                stats.token_alignment_success += 1  # Track Phase 2 success
                if log_callback:
                    log_callback("phase2_success", f"✓ Phase 2 successful: Token alignment repositioned {len(placeholders_list)} tags")
                    log_callback("phase2_warning", "⚠️ Note: Proportional repositioning may cause minor layout imperfections")

                # 6. Restore global indices and return
                result = placeholder_mgr.restore_to_global(result_with_placeholders, global_indices)
                return result
            else:
                _log_error(log_callback, "phase2_validation_failed", "✗ Phase 2 validation failed")

        except Exception as e:
            _log_error(log_callback, "phase2_error", f"✗ Phase 2 error: {str(e)}")

    # ==========================================================================
    # PHASE 3: UNTRANSLATED FALLBACK
    # ==========================================================================
    stats.fallback_used += 1

    _log_error(log_callback, "fallback_untranslated",
        "✗ Phase 3: All translation attempts failed - returning original untranslated text")

    if log_callback:
        log_callback("phase3_warning", "⚠️ This chunk will remain in the source language")

    # Return the original chunk_text with global indices restored
    result_final = placeholder_mgr.restore_to_global(chunk_text, global_indices)
    return result_final


# === Private Helper Functions ===

def _setup_translation(
    doc_root: etree._Element,
    log_callback: Optional[Callable] = None,
    container: Optional[TranslationContainer] = None
) -> Tuple[str, etree._Element, TagPreserver]:
    """Extract body HTML and initialize tag preserver.

    Args:
        doc_root: XHTML document root
        log_callback: Optional logging callback
        container: Optional dependency injection container (uses default if None)

    Returns:
        Tuple of (body_html, body_element, tag_preserver)
    """
    # Extract body
    body_html, body_element = extract_body_html(doc_root)

    # Initialize tag preserver (use container if provided, otherwise create directly)
    if container is not None:
        tag_preserver = container.tag_preserver
    else:
        tag_preserver = TagPreserver()

    return body_html, body_element, tag_preserver


def _preserve_tags(
    body_html: str,
    tag_preserver: TagPreserver,
    log_callback: Optional[Callable] = None
) -> Tuple[str, Dict[str, str], Tuple[str, str]]:
    """Replace HTML tags with placeholders.

    Args:
        body_html: HTML content to process
        tag_preserver: TagPreserver instance
        log_callback: Optional logging callback

    Returns:
        Tuple of (text_with_placeholders, global_tag_map, placeholder_format)
    """
    text_with_placeholders, global_tag_map = tag_preserver.preserve_tags(body_html)

    # Extract placeholder format for prompt generation
    placeholder_format = (tag_preserver.placeholder_format.prefix, tag_preserver.placeholder_format.suffix)

    if log_callback:
        format_info = f" using format {placeholder_format[0]}N{placeholder_format[1]}"
        log_callback("tags_preserved", f"Preserved {len(global_tag_map)} tag groups{format_info}")

    return text_with_placeholders, global_tag_map, placeholder_format


def _create_chunks(
    text: str,
    tag_map: Dict[str, str],
    max_tokens: int,
    log_callback: Optional[Callable] = None,
    container: Optional[TranslationContainer] = None
) -> List[Dict]:
    """Chunk text into translatable segments.

    Args:
        text: Text with placeholders
        tag_map: Global tag map
        max_tokens: Maximum tokens per chunk
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
        log_callback: Optional callback for progress
        progress_callback: Optional callback for progress percentage

    Returns:
        Tuple of (translated_chunks, statistics)
    """
    stats = TranslationStats()
    translated_chunks = []

    for i, chunk in enumerate(chunks):
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
            placeholder_format=placeholder_format
        )
        translated_chunks.append(translated)

        # Report progress after completing each chunk
        if progress_callback:
            progress_callback(((i + 1) / len(chunks)) * 100)

    return translated_chunks, stats


def _reconstruct_html(
    translated_chunks: List[str],
    global_tag_map: Dict[str, str],
    tag_preserver: TagPreserver
) -> str:
    """Reconstruct full HTML from translated chunks.

    Args:
        translated_chunks: List of translated chunk texts
        global_tag_map: Global tag map
        tag_preserver: TagPreserver instance

    Returns:
        Reconstructed HTML string
    """
    full_translated_text = ''.join(translated_chunks)
    final_html = tag_preserver.restore_tags(full_translated_text, global_tag_map)
    return final_html


def _replace_body(
    body_element: etree._Element,
    new_html: str,
    log_callback: Optional[Callable] = None
) -> bool:
    """Replace body content with translated HTML.

    Args:
        body_element: Body element to update
        new_html: New HTML content
        log_callback: Optional logging callback

    Returns:
        True if successful, False otherwise
    """
    # Check for unreplaced placeholders in the HTML before attempting to replace body
    import re
    # Only check for the actual placeholder format used by the system
    # Use PlaceholderFormat to get the correct pattern
    from src.common.placeholder_format import PlaceholderFormat
    fmt = PlaceholderFormat.from_config()

    remaining_placeholders = []
    matches = re.findall(fmt.pattern, new_html)
    if matches:
        # Reconstruct full placeholder strings (pattern captures just the number)
        remaining_placeholders = [fmt.create(int(num)) for num in matches]

    if remaining_placeholders:
        _log_error(log_callback, "unreplaced_placeholders_warning",
                     f"⚠️ WARNING: {len(remaining_placeholders)} unreplaced placeholders found in reconstructed HTML: {remaining_placeholders[:10]}")

    # Capture XML parsing errors if they occur
    try:
        replace_body_content(body_element, new_html)
        xml_success = True
    except (XmlParsingError, BodyExtractionError) as e:
        # Expected XML/parsing errors - handle gracefully
        xml_success = False
        _log_error(log_callback, "replace_body_error", f"Failed to replace body content: {str(e)}")
        if log_callback:
            # Show preview of problematic HTML
            preview = new_html[:500] if len(new_html) > 500 else new_html
            log_callback("replace_body_html_preview", f"HTML preview: {preview}")
    except Exception as e:
        # Unexpected error - log full traceback for debugging
        import traceback
        xml_success = False

        _log_error(log_callback, "replace_body_unexpected_error",
                    f"⚠️ UNEXPECTED ERROR in replace_body_content: {type(e).__name__}: {str(e)}")
        if log_callback:
            # Log full traceback
            full_traceback = traceback.format_exc()
            log_callback("replace_body_traceback", f"Full traceback:\n{full_traceback}")
            # Show preview of problematic HTML
            preview = new_html[:500] if len(new_html) > 500 else new_html
            log_callback("replace_body_html_preview", f"HTML preview: {preview}")

        # In debug mode, re-raise unexpected errors to fail fast
        from src.config import DEBUG_MODE
        if DEBUG_MODE:
            raise

    return xml_success


def _report_statistics(
    stats: TranslationStats,
    log_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None
) -> None:
    """Report translation statistics.

    Args:
        stats: TranslationStats instance
        log_callback: Optional callback for logging
        progress_callback: Optional callback for progress percentage
    """
    stats.log_summary(log_callback)

    if log_callback:
        log_callback("translation_complete", "Body translation complete")

    if progress_callback:
        progress_callback(100)


async def _refine_epub_chunks(
    translated_chunks: List[str],
    chunks: List[Dict],
    target_language: str,
    model_name: str,
    llm_client: Any,
    context_manager: Optional[AdaptiveContextManager],
    placeholder_format: Tuple[str, str],
    log_callback: Optional[Callable],
    progress_callback: Optional[Callable],
    prompt_options: Optional[Dict]
) -> List[str]:
    """
    Refine translated EPUB chunks using a second LLM pass.

    This function applies refinement to already-translated chunks while preserving
    HTML placeholders. It uses the same generate_translation_request approach
    but with a refinement-focused prompt.

    Args:
        translated_chunks: List of translated chunk texts (with placeholders)
        chunks: Original chunk dictionaries (for structure)
        target_language: Target language
        model_name: LLM model name
        llm_client: LLM client instance
        context_manager: Optional context manager
        placeholder_format: Placeholder format tuple (prefix, suffix)
        log_callback: Optional logging callback
        progress_callback: Optional progress callback
        prompt_options: Prompt options dict

    Returns:
        List of refined chunk texts
    """
    from prompts.prompts import generate_post_processing_prompt

    total_chunks = len(translated_chunks)
    refined_chunks = []

    if log_callback:
        log_callback("epub_refinement_info",
                     f"Refining {total_chunks} EPUB chunks (original chunks: {len(chunks)})...")

    # Ensure we have matching lengths
    if len(translated_chunks) != len(chunks):
        _log_error(log_callback, "epub_refinement_warning",
                    f"Warning: Length mismatch - translated_chunks: {len(translated_chunks)}, chunks: {len(chunks)}")

    for idx, (translated_text, chunk_dict) in enumerate(zip(translated_chunks, chunks)):
        # Build context from surrounding chunks
        context_before = translated_chunks[idx - 1] if idx > 0 else ""
        context_after = translated_chunks[idx + 1] if idx < len(translated_chunks) - 1 else ""

        # Extract refinement instructions from prompt_options
        refinement_instructions = prompt_options.get('refinement_instructions', '') if prompt_options else ''

        # Get local tag map for placeholder validation
        local_tag_map = chunk_dict.get('local_tag_map', {})

        # Generate refinement prompt
        prompt_pair = generate_post_processing_prompt(
            translated_text=translated_text,
            target_language=target_language,
            context_before=context_before,
            context_after=context_after,
            additional_instructions=refinement_instructions,
            has_placeholders=True,
            placeholder_format=placeholder_format,
            prompt_options=prompt_options
        )

        # Make refinement request
        try:
            # Log the refinement request (like translation does)
            if log_callback:
                log_callback("llm_request", "Sending refinement request to LLM", data={
                    'type': 'llm_request',
                    'system_prompt': prompt_pair.system,
                    'user_prompt': prompt_pair.user,
                    'model': model_name
                })

            # Set context from manager if available
            if context_manager and hasattr(llm_client, 'context_window'):
                new_ctx = context_manager.get_context_size()
                if llm_client.context_window != new_ctx:
                    llm_client.context_window = new_ctx

            import time
            start_time = time.time()
            llm_response = await llm_client.make_request(
                prompt_pair.user, model_name, system_prompt=prompt_pair.system
            )
            execution_time = time.time() - start_time

            # Log the response (like translation does)
            if log_callback and llm_response:
                log_callback("llm_response", "LLM Response received", data={
                    'type': 'llm_response',
                    'response': llm_response.content,
                    'execution_time': execution_time,
                    'model': model_name,
                    'tokens': {
                        'prompt': llm_response.prompt_tokens,
                        'completion': llm_response.completion_tokens,
                        'total': llm_response.context_used,
                        'limit': llm_response.context_limit
                    }
                })

            if llm_response and llm_response.content:
                # Extract refined text
                refined_text = llm_client.extract_translation(llm_response.content)

                if refined_text:
                    # CRITICAL: Validate placeholders before accepting refinement
                    # If placeholders are corrupted, fall back to original translation
                    if local_tag_map and not validate_placeholders(refined_text, local_tag_map):
                        _log_error(log_callback, "epub_refinement_placeholder_corruption",
                                    f"Chunk {idx + 1}/{total_chunks}: refinement corrupted placeholders, using original translation")
                        refined_chunks.append(translated_text)
                    else:
                        refined_chunks.append(refined_text)
                        if log_callback:
                            log_callback("epub_chunk_refined", f"Chunk {idx + 1}/{total_chunks} refined successfully")
                else:
                    # Fallback to original translation if extraction fails
                    refined_chunks.append(translated_text)
                    if log_callback:
                        log_callback("epub_refinement_fallback", f"Chunk {idx + 1}/{total_chunks}: using original translation")
            else:
                # Fallback to original translation if request fails
                refined_chunks.append(translated_text)
                _log_error(log_callback, "epub_refinement_failed", f"Chunk {idx + 1}/{total_chunks}: refinement failed, using original")

        except Exception as e:
            # Fallback to original translation on error
            refined_chunks.append(translated_text)
            _log_error(log_callback, "epub_refinement_error", f"Chunk {idx + 1}/{total_chunks}: error during refinement: {e}")

        # Update progress
        if progress_callback:
            progress_callback(((idx + 1) / total_chunks) * 100)

    if log_callback:
        successful_refinements = sum(1 for orig, ref in zip(translated_chunks, refined_chunks) if orig != ref)
        log_callback("epub_refinement_complete",
                     f"✨ Refinement complete: {successful_refinements}/{total_chunks} chunks improved")

    return refined_chunks


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
    container: Optional[TranslationContainer] = None,
    prompt_options: Optional[Dict] = None
) -> Tuple[bool, 'TranslationStats']:
    """
    Translate an XHTML document using the simplified approach.

    Simplified to call focused sub-functions for each step.
    Main orchestration function is now ~40 lines total.

    1. Extract body as HTML string
    2. Replace all tags with placeholders
    3. Chunk by complete HTML blocks with local renumbering
    4. Translate each chunk (with retry attempts)
    5. (Optional) Refine translated chunks if prompt_options['refine'] is True
    6. Reconstruct and replace body

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
        container: Optional dependency injection container for components
        prompt_options: Optional dict with prompt customization options (e.g., refine=True)

    Returns:
        Tuple of (success: bool, stats: TranslationStats)
    """
    # 1. Setup
    body_html, body_element, tag_preserver = _setup_translation(
        doc_root,
        log_callback,
        container
    )

    if not body_html or body_element is None:
        if log_callback:
            log_callback("no_body", "No <body> element found")
        from .translation_metrics import TranslationStats
        return False, TranslationStats()

    # 2. Tag Preservation
    text_with_placeholders, global_tag_map, placeholder_format = _preserve_tags(
        body_html,
        tag_preserver,
        log_callback
    )

    # 3. Chunking
    chunks = _create_chunks(
        text_with_placeholders,
        global_tag_map,
        max_tokens_per_chunk,
        log_callback,
        container
    )

    # Check if refinement is enabled
    enable_refinement = prompt_options and prompt_options.get('refine')

    if log_callback:
        log_callback("epub_refinement_config",
                     f"Refinement enabled: {enable_refinement} (prompt_options={prompt_options})")

    # 4. Translation
    # Note: Progress is reported as raw 0-100% chunk-based progress
    # The parent epub/translator.py handles token-based progress via its own ProgressTracker
    translated_chunks, stats = await _translate_all_chunks(
        chunks=chunks,
        source_language=source_language,
        target_language=target_language,
        model_name=model_name,
        llm_client=llm_client,
        max_retries=max_retries,
        context_manager=context_manager,
        placeholder_format=placeholder_format,
        log_callback=log_callback,
        progress_callback=progress_callback  # Pass through to parent's token tracker
    )

    # 4.5. Refinement (optional)
    if enable_refinement and translated_chunks:
        if log_callback:
            log_callback("epub_refinement_start",
                        f"✨ Starting EPUB refinement pass to polish translation quality... ({len(translated_chunks)} chunks)")

        refined_result = await _refine_epub_chunks(
            translated_chunks=translated_chunks,
            chunks=chunks,
            target_language=target_language,
            model_name=model_name,
            llm_client=llm_client,
            context_manager=context_manager,
            placeholder_format=placeholder_format,
            log_callback=log_callback,
            progress_callback=progress_callback,  # Pass through to parent's token tracker
            prompt_options=prompt_options
        )

        if refined_result:
            translated_chunks = refined_result
            if log_callback:
                log_callback("epub_refinement_applied", f"Applied refinement to {len(refined_result)} chunks")
        else:
            _log_error(log_callback, "epub_refinement_empty", "Warning: Refinement returned empty result, using original translation")
    elif enable_refinement and not translated_chunks:
        if log_callback:
            log_callback("epub_refinement_skipped", "Refinement skipped: no translated chunks available")

    # 5. Reconstruction
    final_html = _reconstruct_html(
        translated_chunks,
        global_tag_map,
        tag_preserver
    )

    # 6. Replace body
    xml_success = _replace_body(body_element, final_html, log_callback)

    # 7. Report stats
    _report_statistics(stats, log_callback, progress_callback)

    return xml_success, stats
