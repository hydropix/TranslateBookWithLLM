"""
Simplified EPUB translation using full-body serialization

This module provides a simplified approach to EPUB translation that:
1. Extracts the entire body as HTML string
2. Replaces all tags with placeholders
3. Chunks intelligently by complete HTML blocks
4. Renumbers placeholders locally for each chunk (0, 1, 2...)
5. Translates each chunk
6. Applies offset to restore global indices
7. Restores tags and replaces the body

Translation flow with LLM placeholder correction:
1. Phase 1: Normal translation (1 attempt)
2. Phase 2: LLM correction (up to MAX_PLACEHOLDER_CORRECTION_ATTEMPTS)
3. Phase 3: Proportional fallback (if correction fails)
"""
import re
from collections import Counter
from typing import List, Dict, Any, Optional, Callable, Tuple
from lxml import etree

from .body_serializer import extract_body_html, replace_body_content
from .html_chunker import (
    HtmlChunker,
    restore_global_indices,
    extract_text_and_positions,
    reinsert_placeholders,
    TranslationStats
)
from .tag_preservation import TagPreserver
from ..translator import generate_translation_request
from src.config import (
    PLACEHOLDER_PATTERN,
    MAX_PLACEHOLDER_CORRECTION_ATTEMPTS,
    create_placeholder,
    get_mutation_variants,
)
from prompts.prompts import generate_placeholder_correction_prompt, CORRECTED_TAG_IN, CORRECTED_TAG_OUT


def validate_placeholders(translated_text: str, local_tag_map: Dict[str, str]) -> bool:
    """
    Validate that translated text contains all expected placeholders.

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

    found = re.findall(r'\[\[\d+\]\]', translated_text)

    if len(found) != expected_count:
        return False

    # Check sequential order (0, 1, 2, ...)
    expected_indices = set(range(expected_count))
    found_indices = set()

    for placeholder in found:
        idx = int(placeholder[2:-2])
        found_indices.add(idx)

    return found_indices == expected_indices


def build_specific_error_details(translated_text: str, expected_count: int) -> str:
    """
    Analyze placeholder errors and generate a detailed error message in English.

    Args:
        translated_text: Translated text to analyze
        expected_count: Number of placeholders expected (0 to expected_count-1)

    Returns:
        Detailed error message for the correction prompt
    """
    errors = []

    # 1. Find correct placeholders present (using PLACEHOLDER_PATTERN)
    found_correct = re.findall(PLACEHOLDER_PATTERN, translated_text)
    # Extract indices from found placeholders
    found_indices = [int(re.search(r'\d+', p).group()) for p in found_correct]
    expected_indices = set(range(expected_count))

    # 2. Detect missing placeholders
    found_set = set(found_indices)
    missing = expected_indices - found_set
    if missing:
        missing_str = ", ".join(create_placeholder(i) for i in sorted(missing))
        errors.append(f"- Missing placeholders: {missing_str}")

    # 3. Detect duplicates
    counts = Counter(found_indices)
    duplicates = {idx: count for idx, count in counts.items() if count > 1}
    if duplicates:
        for idx, count in duplicates.items():
            errors.append(f"- Duplicate: {create_placeholder(idx)} appears {count} times (should appear once)")

    # 4. Detect mutations (incorrect formats) - use get_mutation_variants()
    mutations_found = []
    for i in range(expected_count):
        if i not in found_set:
            correct_placeholder = create_placeholder(i)
            # Search for possible mutations
            for variant in get_mutation_variants(i):
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
            wrong_str = ", ".join(create_placeholder(i) for i in sorted(wrong_indices))
            errors.append(f"- Wrong indices used: {wrong_str} (should be {create_placeholder(0)} to {create_placeholder(expected_count - 1)})")

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
    log_callback: Optional[Callable]
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

    Returns:
        Tuple (corrected_text, success)
    """
    # Count only regular placeholders (not boundary keys)
    expected_count = len([k for k in local_tag_map.keys() if not k.startswith("__")])

    # Generate error details
    specific_errors = build_specific_error_details(translated_text, expected_count)

    # Generate correction prompt
    prompt_pair = generate_placeholder_correction_prompt(
        original_text=original_text,
        translated_text=translated_text,
        specific_errors=specific_errors,
        source_language=source_language,
        target_language=target_language,
        expected_count=expected_count
    )

    # Call LLM for correction
    try:
        # Log the correction request
        if log_callback:
            log_callback("correction_request", "Sending correction request to LLM")

        llm_response = await llm_client.make_request(
            prompt_pair.user,
            system_prompt=prompt_pair.system
        )

        if llm_response is None:
            return translated_text, False

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
        if log_callback:
            log_callback("correction_error", f"Correction attempt failed: {str(e)}")
        return translated_text, False


def strip_chunk_boundaries(
    chunk_text: str,
    local_tag_map: Dict[str, str]
) -> Tuple[str, str, str, Dict[str, str], List[int]]:
    """
    Strip boundary placeholders from a chunk before sending to LLM.

    This optimization only applies to SIMPLE chunks that have exactly 2 placeholders
    (one opening tag at start, one closing tag at end). For chunks with multiple
    paragraphs or complex structure, we keep all placeholders.

    Args:
        chunk_text: Text with placeholders like "[[0]]Content here[[1]]"
        local_tag_map: Mapping of placeholders to HTML tags

    Returns:
        Tuple of:
        - stripped_text: Text without boundary placeholders (if stripped)
        - boundary_prefix_placeholder: The first placeholder (e.g., "[[0]]") or ""
        - boundary_suffix_placeholder: The last placeholder (e.g., "[[1]]") or ""
        - inner_tag_map: Tag map with only inner placeholders (empty if boundaries stripped)
        - inner_to_original_indices: Mapping to restore original indices (empty if no inner)
    """
    # Get regular placeholders (not __boundary_* keys)
    regular_keys = [k for k in local_tag_map.keys() if not k.startswith("__")]

    # Only strip boundaries for simple chunks with exactly 2 placeholders
    # This covers the common case: [[0]]text[[1]] (single paragraph)
    if len(regular_keys) != 2:
        # Complex chunk with multiple paragraphs - keep all placeholders
        return chunk_text, "", "", local_tag_map, list(range(len(regular_keys)))

    # Find the two placeholder indices
    placeholder_indices = []
    for key in regular_keys:
        try:
            idx = int(key[2:-2])  # Extract number from [[N]]
            placeholder_indices.append(idx)
        except (ValueError, IndexError):
            pass

    if len(placeholder_indices) != 2:
        return chunk_text, "", "", local_tag_map, list(range(len(regular_keys)))

    min_idx = min(placeholder_indices)
    max_idx = max(placeholder_indices)

    first_placeholder = f"[[{min_idx}]]"
    last_placeholder = f"[[{max_idx}]]"

    # Check if chunk starts with first and ends with last placeholder
    if not chunk_text.startswith(first_placeholder) or not chunk_text.endswith(last_placeholder):
        return chunk_text, "", "", local_tag_map, list(range(len(regular_keys)))

    # Verify they are consecutive (no gaps) - should be [[0]] and [[1]]
    if max_idx != min_idx + 1:
        return chunk_text, "", "", local_tag_map, list(range(len(regular_keys)))

    # Strip boundaries - this is a simple [[0]]text[[1]] chunk
    stripped_text = chunk_text[len(first_placeholder):-len(last_placeholder)]

    # No inner placeholders for simple chunks
    return stripped_text, first_placeholder, last_placeholder, {}, []


def restore_chunk_boundaries(
    translated_text: str,
    boundary_prefix: str,
    boundary_suffix: str,
    inner_to_original: List[int],
    original_min_idx: int
) -> str:
    """
    Restore boundary placeholders and renumber inner placeholders back to original.

    Args:
        translated_text: Translated text with renumbered inner placeholders
        boundary_prefix: First placeholder (e.g., "[[0]]")
        boundary_suffix: Last placeholder (e.g., "[[5]]")
        inner_to_original: List mapping new indices to original indices
        original_min_idx: The original minimum index (usually 0)

    Returns:
        Text with boundaries restored and placeholders renumbered to original
    """
    result = translated_text

    # Renumber inner placeholders back to original (in reverse to avoid conflicts)
    for new_idx in range(len(inner_to_original) - 1, -1, -1):
        original_idx = inner_to_original[new_idx]
        result = result.replace(f"[[{new_idx}]]", f"[[{original_idx}]]")

    # Add boundaries back
    if boundary_prefix or boundary_suffix:
        result = boundary_prefix + result + boundary_suffix

    return result


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
    max_retries: int = 1
) -> str:
    """
    Translate a chunk with LLM correction and proportional fallback.

    New flow:
    1. Phase 0: Strip boundary placeholders (first/last) - they're always present
    2. Phase 1: Normal translation (1 attempt)
    3. Phase 2: LLM correction (up to MAX_PLACEHOLDER_CORRECTION_ATTEMPTS)
    4. Phase 3: Proportional fallback (if correction fails)
    5. Restore boundary placeholders

    Args:
        chunk_text: Text with local placeholders (0, 1, 2...)
        local_tag_map: Local placeholder to tag mapping
        global_indices: Global indices for reconstruction
        source_language: Source language
        target_language: Target language
        model_name: LLM model name
        llm_client: LLM client
        stats: TranslationStats instance for tracking
        log_callback: Optional logging callback
        max_retries: Maximum initial translation attempts (default: 1)

    Returns:
        Translated text with global placeholders restored
    """
    stats.total_chunks += 1

    # ==========================================================================
    # PHASE 0: Strip boundary placeholders
    # ==========================================================================
    stripped_text, boundary_prefix, boundary_suffix, inner_tag_map, inner_to_original = \
        strip_chunk_boundaries(chunk_text, local_tag_map)

    # Determine what to send to LLM
    text_for_llm = stripped_text
    tag_map_for_validation = inner_tag_map

    # Get original min index for restoration
    regular_keys = [k for k in local_tag_map.keys() if not k.startswith("__")]
    original_min_idx = 0
    if regular_keys:
        try:
            original_min_idx = min(int(k[2:-2]) for k in regular_keys)
        except (ValueError, IndexError):
            pass

    # ==========================================================================
    # PHASE 1: Normal translation (1 attempt)
    # ==========================================================================
    translated = await generate_translation_request(
        text_for_llm,
        context_before="",
        context_after="",
        previous_translation_context="",
        source_language=source_language,
        target_language=target_language,
        model=model_name,
        llm_client=llm_client,
        log_callback=log_callback
    )

    if translated is None:
        if log_callback:
            log_callback("chunk_translation_failed", "Translation returned None")
    elif validate_placeholders(translated, tag_map_for_validation):
        # Success on first try - restore boundaries and return
        stats.successful_first_try += 1
        restored = restore_chunk_boundaries(
            translated, boundary_prefix, boundary_suffix,
            inner_to_original, original_min_idx
        )
        return restore_global_indices(restored, global_indices)
    else:
        if log_callback:
            log_callback("placeholder_mismatch", "Phase 1: Placeholder validation failed")

    # ==========================================================================
    # PHASE 2: LLM Correction (up to MAX_PLACEHOLDER_CORRECTION_ATTEMPTS)
    # ==========================================================================
    # Only attempt correction if there are inner placeholders to correct
    inner_placeholder_count = len([k for k in tag_map_for_validation.keys() if not k.startswith("__")])
    if translated is not None and inner_placeholder_count > 0:
        if log_callback:
            log_callback("placeholder_correction_start",
                f"Starting LLM correction phase ({MAX_PLACEHOLDER_CORRECTION_ATTEMPTS} attempts)")

        for correction_attempt in range(MAX_PLACEHOLDER_CORRECTION_ATTEMPTS):
            stats.correction_attempts += 1
            if log_callback:
                log_callback("placeholder_correction_attempt",
                    f"Correction attempt {correction_attempt + 1}/{MAX_PLACEHOLDER_CORRECTION_ATTEMPTS}")

            corrected, success = await attempt_placeholder_correction(
                original_text=text_for_llm,
                translated_text=translated,
                local_tag_map=tag_map_for_validation,
                source_language=source_language,
                target_language=target_language,
                llm_client=llm_client,
                log_callback=log_callback
            )

            if success:
                stats.successful_after_retry += 1
                if log_callback:
                    log_callback("placeholder_correction_success",
                        f"Correction succeeded after {correction_attempt + 1} attempt(s)")
                restored = restore_chunk_boundaries(
                    corrected, boundary_prefix, boundary_suffix,
                    inner_to_original, original_min_idx
                )
                return restore_global_indices(restored, global_indices)

            # Update translated for next correction attempt (use corrected even if validation failed)
            translated = corrected

        if log_callback:
            log_callback("placeholder_correction_failed",
                "All correction attempts failed, falling back to proportional insertion")

    # ==========================================================================
    # PHASE 3: Proportional fallback
    # ==========================================================================
    stats.fallback_used += 1

    if log_callback:
        log_callback("fallback_proportional_start",
            "Starting proportional reinsertion fallback")

    # 1. Extract pure text and positions from the stripped text (without boundaries)
    pure_text, positions = extract_text_and_positions(text_for_llm)

    if not pure_text.strip():
        # No actual text, just return original chunk as-is
        return restore_global_indices(chunk_text, global_indices)

    # 2. Translate pure text (without any placeholders)
    translated_pure = await generate_translation_request(
        pure_text,
        context_before="",
        context_after="",
        previous_translation_context="",
        source_language=source_language,
        target_language=target_language,
        model=model_name,
        llm_client=llm_client,
        log_callback=log_callback
    )

    if translated_pure is None:
        # Ultimate fallback: return original text
        if log_callback:
            log_callback("fallback_failed",
                "Fallback translation also failed, using original text")
        return restore_global_indices(chunk_text, global_indices)

    # 3. Reinsert inner placeholders at proportional positions
    result_with_inner = reinsert_placeholders(translated_pure, positions)

    # 4. Restore boundaries and renumber inner placeholders back to original
    result_with_boundaries = restore_chunk_boundaries(
        result_with_inner, boundary_prefix, boundary_suffix,
        inner_to_original, original_min_idx
    )

    # 5. Restore global indices
    final_result = restore_global_indices(result_with_boundaries, global_indices)

    if log_callback:
        log_callback("fallback_result", f"Proportional fallback completed")

    return final_result


async def translate_xhtml_simplified(
    doc_root: etree._Element,
    source_language: str,
    target_language: str,
    model_name: str,
    llm_client: Any,
    max_tokens_per_chunk: int = 450,
    log_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None
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

    # Count actual placeholders (excluding boundary keys)
    internal_placeholder_count = len([k for k in global_tag_map.keys() if not k.startswith("__")])
    has_boundaries = tag_preserver.boundary_prefix or tag_preserver.boundary_suffix

    if log_callback:
        boundary_info = " (+ boundary tags stripped)" if has_boundaries else ""
        log_callback("tags_preserved", f"Preserved {internal_placeholder_count} internal tag groups{boundary_info}")

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
            log_callback=log_callback
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
