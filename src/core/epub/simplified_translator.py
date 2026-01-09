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

Translation flow with LLM placeholder correction:
1. Phase 1: Normal translation (1 attempt)
2. Phase 2: LLM correction (up to MAX_PLACEHOLDER_CORRECTION_ATTEMPTS)
3. Phase 3: Proportional fallback (if correction fails)

Placeholder Indexing Architecture:
===================================

LEVEL 1 - Document level (TagPreserver):
    Input HTML: "<body><p>Hello</p></body>"
    → Preserves tags as placeholders: "[[0]][[1]]Hello[[2]][[3]]"
    → global_tag_map: {"[[0]]": "<body>", "[[1]]": "<p>", ...}

LEVEL 2 - Chunk level (HtmlChunker):
    Global HTML: "[[5]]<p>[[6]]Hello[[7]]</p>[[8]]"
    → Chunk text: "[[0]]<p>[[1]]Hello[[2]]</p>[[3]]" (renumbered locally)
    → global_indices: [5, 6, 7, 8] (mapping to restore later)

LEVEL 3 - Translation (PlaceholderManager):
    Chunk text: "[[0]]<p>[[1]]Hello[[2]]</p>[[3]]" (sent to LLM as-is)
    LLM returns: "[[0]]<p>[[1]]Bonjour[[2]]</p>[[3]]"
    → Restored: "[[5]]<p>[[6]]Bonjour[[7]]</p>[[8]]" (global indices)
"""
import re
from collections import Counter
from typing import List, Dict, Any, Optional, Callable, Tuple
from lxml import etree

from .body_serializer import extract_body_html, replace_body_content
from .html_chunker import (
    HtmlChunker,
    extract_text_and_positions,
    reinsert_placeholders,
    TranslationStats
)
from .tag_preservation import TagPreserver
from ..translator import generate_translation_request
from ..context_optimizer import AdaptiveContextManager, INITIAL_CONTEXT_SIZE, CONTEXT_STEP, MAX_CONTEXT_SIZE
from src.config import (
    PLACEHOLDER_PATTERN,
    MAX_PLACEHOLDER_CORRECTION_ATTEMPTS,
    create_placeholder,
    detect_placeholder_format_in_text,
    get_mutation_variants,
    THINKING_MODELS,
    ADAPTIVE_CONTEXT_INITIAL_THINKING,
)
from prompts.prompts import generate_placeholder_correction_prompt, CORRECTED_TAG_IN, CORRECTED_TAG_OUT
from src.utils.llm_logger import log_llm_interaction


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
        local_tag_map: Expected local tag map (may contain __boundary_* keys)

    Returns:
        True if all placeholders present and valid
    """
    # Count only regular placeholders (not boundary keys)
    expected_count = len([k for k in local_tag_map.keys() if not k.startswith("__")])
    if expected_count == 0:
        return True

    # Detect format from tag_map keys (get first non-boundary placeholder)
    sample_placeholder = next((k for k in local_tag_map.keys() if not k.startswith("__")), "[[0]]")
    use_simple_format = sample_placeholder.startswith("[") and not sample_placeholder.startswith("[[")

    # Use appropriate pattern based on detected format
    if use_simple_format:
        # Use negative lookahead/behind to avoid matching [[0]] when looking for [0]
        pattern = r'(?<!\[)\[(\d+)\](?!\])'
        prefix_len = 1
        suffix_len = 1
    else:
        pattern = r'\[\[(\d+)\]\]'
        prefix_len = 2
        suffix_len = 2

    found = re.findall(pattern, translated_text)

    if len(found) != expected_count:
        return False

    # Check sequential order (0, 1, 2, ...)
    expected_indices = set(range(expected_count))
    found_indices = set()

    for num_str in found:
        idx = int(num_str)
        found_indices.add(idx)

    return found_indices == expected_indices


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
    use_simple_format = False
    if local_tag_map:
        sample_placeholder = next((k for k in local_tag_map.keys() if not k.startswith("__")), "[[0]]")
        use_simple_format = sample_placeholder.startswith("[") and not sample_placeholder.startswith("[[")

    # Set appropriate pattern and placeholder functions
    if use_simple_format:
        # Use negative lookahead/behind to avoid matching [[0]] when looking for [0]
        pattern = r'(?<!\[)\[(\d+)\](?!\])'
        prefix = "["
        suffix = "]"
    else:
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

    # 4. Detect mutations (incorrect formats) - use get_mutation_variants()
    mutations_found = []
    for i in range(expected_count):
        if i not in found_set:
            correct_placeholder = make_placeholder(i)
            # Search for possible mutations
            for variant in get_mutation_variants(i, use_simple_format):
                if variant in translated_text and correct_placeholder not in translated_text:
                    mutations_found.append(f"{variant} instead of {correct_placeholder}")
                    break  # One mutation per index
    if mutations_found:
        errors.append(f"- Mutated placeholders: Found {', '.join(mutations_found)}")

    # 5. Check order
    if found_indices != sorted(found_indices):
        errors.append("- Out of order: placeholders are not in sequential order")

    # 6. Count summary
    if len(found_correct) != expected_count:
        errors.append(f"- Count mismatch: Expected {expected_count} placeholders, found {len(found_correct)}")

    # 7. Position hint - if count matches but indices don't, placeholders are shifted
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
        local_tag_map: Expected local tag map (may contain __boundary_* keys)
        source_language: Source language name
        target_language: Target language name
        llm_client: LLM client instance
        log_callback: Optional logging callback
        placeholder_format: Optional tuple of (prefix, suffix) for placeholders
        context_manager: Optional AdaptiveContextManager for handling context overflow

    Returns:
        Tuple (corrected_text, success)
    """
    # Count only regular placeholders (not boundary keys)
    expected_count = len([k for k in local_tag_map.keys() if not k.startswith("__")])

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

            # Log full interaction if DEBUG_MODE is enabled
            if llm_response is not None:
                log_llm_interaction(
                    system_prompt=prompt_pair.system,
                    user_prompt=prompt_pair.user,
                    raw_response=llm_response.content,
                    interaction_type="placeholder_correction",
                    prefix=f"Attempt {retry + 1}/{max_retries}"
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
    placeholder_format: Optional[Tuple[str, str]] = None
) -> str:
    """
    Translate a chunk with LLM correction and proportional fallback.

    Translation flow:
    1. Phase 1: Normal translation (1 attempt) - chunk already has local indices (0, 1, 2...)
    2. Phase 2: LLM correction (up to MAX_PLACEHOLDER_CORRECTION_ATTEMPTS)
    3. Phase 3: Proportional fallback (if correction fails)
    4. Restore global indices

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
        max_retries: Maximum initial translation attempts (unused, kept for compatibility)
        context_manager: Optional AdaptiveContextManager for handling context overflow

    Returns:
        Translated text with global placeholders restored
    """
    stats.total_chunks += 1

    # Initialize placeholder manager
    placeholder_mgr = PlaceholderManager()

    # Calculate if this chunk has placeholders (excluding boundary keys)
    placeholder_count = len([k for k in local_tag_map.keys() if not k.startswith("__")])
    has_placeholders = placeholder_count > 0

    # ==========================================================================
    # PHASE 1: Normal translation (1 attempt)
    # ==========================================================================
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
            log_callback("chunk_translation_failed", "Translation returned None")
    elif validate_placeholders(translated, local_tag_map):
        # Success on first try - restore to global indices
        stats.successful_first_try += 1
        result = placeholder_mgr.restore_to_global(translated, global_indices)
        return result
    else:
        if log_callback:
            log_callback("placeholder_mismatch", "Phase 1: Placeholder validation failed")

    # ==========================================================================
    # PHASE 2: LLM Correction (up to MAX_PLACEHOLDER_CORRECTION_ATTEMPTS)
    # ==========================================================================
    if translated is not None and has_placeholders:
        if log_callback:
            log_callback("placeholder_correction_start",
                f"Starting LLM correction phase ({MAX_PLACEHOLDER_CORRECTION_ATTEMPTS} attempts)")

        for correction_attempt in range(MAX_PLACEHOLDER_CORRECTION_ATTEMPTS):
            stats.correction_attempts += 1
            if log_callback:
                log_callback("placeholder_correction_attempt",
                    f"Correction attempt {correction_attempt + 1}/{MAX_PLACEHOLDER_CORRECTION_ATTEMPTS}")

            corrected, success = await attempt_placeholder_correction(
                original_text=chunk_text,
                translated_text=translated,
                local_tag_map=local_tag_map,
                source_language=source_language,
                target_language=target_language,
                llm_client=llm_client,
                log_callback=log_callback,
                placeholder_format=placeholder_format,
                context_manager=context_manager
            )

            if success:
                stats.successful_after_retry += 1
                if log_callback:
                    log_callback("placeholder_correction_success",
                        f"Correction succeeded after {correction_attempt + 1} attempt(s)")
                return placeholder_mgr.restore_to_global(corrected, global_indices)

            # Use corrected text for next attempt even if validation failed
            translated = corrected

        if log_callback:
            log_callback("placeholder_correction_failed",
                "All correction attempts failed, falling back to proportional insertion")

    # ==========================================================================
    # PHASE 3: Proportional fallback with boundary restoration
    # ==========================================================================
    stats.fallback_used += 1

    # Proportional reinsertion if we have a translation and placeholders
    if translated is not None and has_placeholders:
        if log_callback:
            log_callback("fallback_proportional",
                "Using proportional fallback - reinserting placeholders into translated text")

        # Extract placeholder positions from original chunk
        translated_pure, global_positions = extract_text_and_positions(chunk_text)

        # Reinsert placeholders proportionally into the translation
        result_with_placeholders = reinsert_placeholders(
            translated,
            global_positions,
            placeholder_format=placeholder_format
        )

        # Restore global indices
        result_with_globals = placeholder_mgr.restore_to_global(
            result_with_placeholders,
            global_indices
        )

        # Restore boundary tags
        boundary_prefix = local_tag_map.get("__boundary_prefix__", "")
        boundary_suffix = local_tag_map.get("__boundary_suffix__", "")

        if boundary_prefix or boundary_suffix:
            result_with_globals = boundary_prefix + result_with_globals + boundary_suffix

        return result_with_globals

    # SAFE FALLBACK: Return original text with global placeholders and boundaries
    # Used when: translated=None OR has_placeholders=False
    # This preserves HTML structure perfectly
    if log_callback:
        log_callback("fallback_original",
            "Using safe fallback - returning original untranslated text with proper HTML structure")

    # Restore global indices for internal placeholders
    result_with_globals = placeholder_mgr.restore_to_global(chunk_text, global_indices)

    # Restore boundary tags if present
    boundary_prefix = local_tag_map.get("__boundary_prefix__", "")
    boundary_suffix = local_tag_map.get("__boundary_suffix__", "")

    if boundary_prefix or boundary_suffix:
        result_with_globals = boundary_prefix + result_with_globals + boundary_suffix

    return result_with_globals


async def translate_xhtml_simplified(
    doc_root: etree._Element,
    source_language: str,
    target_language: str,
    model_name: str,
    llm_client: Any,
    max_tokens_per_chunk: int = 450,
    log_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None,
    context_manager: Optional[AdaptiveContextManager] = None
) -> bool:
    """
    Translate an XHTML document using the simplified approach.

    1. Extract body as HTML string
    2. Replace all tags with placeholders
    3. Chunk by complete HTML blocks with local renumbering
    4. Translate each chunk
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

    Returns:
        True if successful, False otherwise
    """
    # 1. Extract body
    body_html, body_element = extract_body_html(doc_root)
    if not body_html or body_element is None:
        if log_callback:
            log_callback("no_body", "No <body> element found")
        return False

    # 2. Preserve tags (with boundary optimization - first/last tags stored separately)
    tag_preserver = TagPreserver()
    text_with_placeholders, global_tag_map = tag_preserver.preserve_tags(body_html)

    # Extract placeholder format for prompt generation
    placeholder_format = (tag_preserver.placeholder_prefix, tag_preserver.placeholder_suffix)

    # Count actual placeholders (excluding boundary keys)
    internal_placeholder_count = len([k for k in global_tag_map.keys() if not k.startswith("__")])
    has_boundaries = tag_preserver.boundary_prefix or tag_preserver.boundary_suffix

    if log_callback:
        boundary_info = " (+ boundary tags stripped)" if has_boundaries else ""
        format_info = f" using format {placeholder_format[0]}N{placeholder_format[1]}"
        log_callback("tags_preserved", f"Preserved {internal_placeholder_count} internal tag groups{boundary_info}{format_info}")

    # 3. Chunk by complete HTML blocks
    chunker = HtmlChunker(max_tokens=max_tokens_per_chunk)
    chunks = chunker.chunk_html_with_placeholders(text_with_placeholders, global_tag_map)

    if log_callback:
        log_callback("chunks_created", f"Created {len(chunks)} chunks")

    # 4. Translate each chunk
    translated_chunks = []
    stats = TranslationStats()

    for i, chunk in enumerate(chunks):
        if progress_callback:
            progress_callback((i / len(chunks)) * 100)

        # Translate with fallback
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
            context_manager=context_manager,
            placeholder_format=placeholder_format
        )

        translated_chunks.append(translated)

    # Log translation statistics
    stats.log_summary(log_callback)

    # 5. Reconstruct full HTML
    full_translated = "".join(translated_chunks)

    # Restore tags
    final_html = tag_preserver.restore_tags(full_translated, global_tag_map)

    # 6. Replace body content
    replace_body_content(body_element, final_html)

    if log_callback:
        log_callback("translation_complete", "Body translation complete")

    if progress_callback:
        progress_callback(100)

    return True
