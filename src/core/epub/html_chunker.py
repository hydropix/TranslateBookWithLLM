"""
HTML-aware chunking that splits on complete HTML blocks

This module provides intelligent chunking of HTML content with placeholders,
ensuring chunks are split at safe boundaries (between complete HTML blocks)
and includes a proportional reinsertion fallback for placeholder recovery.
"""
import re
from typing import List, Dict, Tuple, Optional

from src.core.chunking.token_chunker import TokenChunker
from src.common.placeholder_format import PlaceholderFormat


class HtmlChunker:
    """
    Chunks HTML with placeholders into complete HTML blocks.

    Guarantees that each chunk contains balanced placeholders
    (no orphan [id3] without its closing [id4]).
    """

    def __init__(self, max_tokens: int = 450):
        self.max_tokens = max_tokens
        self.token_chunker = TokenChunker(max_tokens=max_tokens)
        self.placeholder_format = PlaceholderFormat.from_config()

    def chunk_html_with_placeholders(
        self,
        text_with_placeholders: str,
        tag_map: Dict[str, str]
    ) -> List[Dict]:
        """
        Chunk text with placeholders into appropriately sized chunks.

        Each returned chunk contains:
        - text: text with locally renumbered placeholders (0, 1, 2...)
        - local_tag_map: local mapping {placeholder: tag}
        - global_offset: offset to reconstruct global indices
        - global_indices: list of global indices for reconstruction

        Args:
            text_with_placeholders: "[id0]Hello[id1]world[id2]..."
            tag_map: {"[id0]": "<p>", "[id1]": "<b>", ...}

        Returns:
            List of chunks with local renumbering
        """
        # Handle empty text
        if not text_with_placeholders or not text_with_placeholders.strip():
            return []

        # Find safe split points (between complete blocks)
        split_points = self._find_safe_split_points(text_with_placeholders, tag_map)

        # Split into segments
        segments = self._split_at_points(text_with_placeholders, split_points)

        # Merge segments into appropriately sized chunks
        chunks = self._merge_segments_into_chunks(segments, tag_map)

        return chunks

    def _find_safe_split_points(
        self,
        text: str,
        tag_map: Dict[str, str]
    ) -> List[Tuple[int, int]]:
        """
        Find positions where we can safely split without breaking an HTML block.

        Returns split points with priority levels:
        - Priority 1: After chapter headings (h1, h2, h3)
        - Priority 2: After other block elements (p, div, etc.)

        Returns:
            List of tuples (position, priority) where lower priority = higher preference
        """
        split_points = []

        # Find placeholders with their positions
        placeholder_positions = [
            (start, end, placeholder, idx)
            for start, end, placeholder, idx in self.placeholder_format.find_all(text)
        ]

        for i, (start, end, placeholder, idx) in enumerate(placeholder_positions):
            tag = tag_map.get(placeholder, "")

            # If this is a block closing tag
            if self._is_block_closing_tag(tag):
                # Check if next placeholder is a block opening tag
                if i + 1 < len(placeholder_positions):
                    next_placeholder = placeholder_positions[i + 1][2]
                    next_tag = tag_map.get(next_placeholder, "")
                    if self._is_block_opening_tag(next_tag):
                        # Determine priority based on tag type
                        priority = self._get_split_priority(tag)
                        split_points.append((end, priority))

        return split_points

    def _get_split_priority(self, tag: str) -> int:
        """
        Get priority for splitting at this tag.
        Lower number = higher priority (preferred split point).

        Priority levels:
        1: Chapter headings (h1, h2, h3)
        2: Major sections (h4, h5, h6, section, article)
        3: Paragraphs and divs (p, div, blockquote)
        4: Other blocks (li, tr, td, th)
        """
        tag_lower = tag.lower()

        # Priority 1: Chapter headings
        if any(f'</{ht}>' in tag_lower for ht in ['h1', 'h2', 'h3']):
            return 1

        # Priority 2: Major sections
        if any(f'</{ht}>' in tag_lower for ht in ['h4', 'h5', 'h6', 'section', 'article']):
            return 2

        # Priority 3: Paragraphs and divs
        if any(f'</{ht}>' in tag_lower for ht in ['p', 'div', 'blockquote']):
            return 3

        # Priority 4: Other blocks
        return 4

    def _is_chapter_heading_tag(self, tag: str) -> bool:
        """Check if tag is a chapter heading (h1, h2, h3)"""
        tag_lower = tag.lower()
        return any(f'</{ht}>' in tag_lower for ht in ['h1', 'h2', 'h3'])

    def _is_block_closing_tag(self, tag: str) -> bool:
        """Check if the tag is a block closing tag (</p>, </div>, etc.)"""
        block_tags = {'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                      'blockquote', 'section', 'article', 'li', 'tr', 'td', 'th'}
        tag_lower = tag.lower()
        for bt in block_tags:
            if f'</{bt}>' in tag_lower or f'</{bt} ' in tag_lower:
                return True
        return False

    def _is_block_opening_tag(self, tag: str) -> bool:
        """Check if the tag is a block opening tag (<p>, <div>, etc.)"""
        block_tags = {'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                      'blockquote', 'section', 'article', 'li', 'tr', 'td', 'th'}
        tag_lower = tag.lower()
        for bt in block_tags:
            if f'<{bt}>' in tag_lower or f'<{bt} ' in tag_lower:
                return True
        return False

    def _split_at_points(self, text: str, points: List[Tuple[int, int]]) -> List[str]:
        """
        Split the text at the specified points.

        Args:
            text: Text to split
            points: List of (position, priority) tuples

        Returns:
            List of text segments
        """
        if not points:
            return [text]

        # Extract just the positions (ignore priority for now, it's used in merging)
        positions = [pos for pos, _ in points]

        segments = []
        prev = 0
        for point in positions:
            if point > prev:
                segments.append(text[prev:point])
            prev = point
        if prev < len(text):
            segments.append(text[prev:])

        return [s for s in segments if s.strip()]

    def _merge_segments_into_chunks(
        self,
        segments: List[str],
        global_tag_map: Dict[str, str]
    ) -> List[Dict]:
        """
        Merge segments into chunks respecting token limit.

        Simplified to call focused helper functions for better readability.
        """
        if not segments:
            return []

        chunks = []
        current_segments = []
        current_tokens = 0
        global_offset = 0

        for segment in segments:
            segment_tokens = self._count_segment_tokens(segment)

            # Check if segment is oversized and needs splitting
            if segment_tokens > self.max_tokens:
                # Finalize current chunk before processing oversized segment
                if current_segments:
                    chunk = self._finalize_chunk(current_segments, global_tag_map, global_offset)
                    chunks.append(chunk)
                    global_offset += len(chunk['local_tag_map'])
                    current_segments = []
                    current_tokens = 0

                # Split and process oversized segment
                sub_segments = self._split_oversized_segment(segment, global_tag_map)

                for sub_seg in sub_segments:
                    sub_tokens = self._count_segment_tokens(sub_seg)

                    if self._would_exceed_limit(current_tokens, sub_tokens) and current_segments:
                        # Finalize current chunk
                        chunk = self._finalize_chunk(current_segments, global_tag_map, global_offset)
                        chunks.append(chunk)
                        global_offset += len(chunk['local_tag_map'])

                        current_segments = [sub_seg]
                        current_tokens = sub_tokens
                    else:
                        current_segments.append(sub_seg)
                        current_tokens += sub_tokens

            elif self._would_exceed_limit(current_tokens, segment_tokens) and current_segments:
                # Finalize current chunk
                chunk = self._finalize_chunk(current_segments, global_tag_map, global_offset)
                chunks.append(chunk)
                global_offset += len(chunk['local_tag_map'])

                current_segments = [segment]
                current_tokens = segment_tokens
            else:
                current_segments.append(segment)
                current_tokens += segment_tokens

        # Finalize last chunk
        if current_segments:
            chunk = self._finalize_chunk(current_segments, global_tag_map, global_offset)
            chunks.append(chunk)

        return chunks

    def _count_segment_tokens(self, segment: str) -> int:
        """Count tokens in a segment.

        Args:
            segment: Text segment to count

        Returns:
            Number of tokens in the segment
        """
        return self.token_chunker.count_tokens(segment)

    def _would_exceed_limit(self, current_tokens: int, new_tokens: int) -> bool:
        """Check if adding new tokens would exceed limit.

        Args:
            current_tokens: Current token count
            new_tokens: Tokens to add

        Returns:
            True if adding new_tokens would exceed max_tokens
        """
        return (current_tokens + new_tokens) > self.max_tokens

    def _finalize_chunk(
        self,
        segments: List[str],
        global_tag_map: Dict[str, str],
        global_offset: int
    ) -> Dict:
        """Finalize a chunk by merging segments and renumbering placeholders.

        Args:
            segments: List of segment strings
            global_tag_map: Global tag mapping
            global_offset: Current global offset

        Returns:
            Chunk dictionary with local renumbering
        """
        return self._create_chunk(segments, global_tag_map, global_offset)

    def _split_oversized_segment(
        self,
        segment: str,
        global_tag_map: Dict[str, str]
    ) -> List[str]:
        """
        Split an oversized segment hierarchically:
        1. Extract placeholders from start/end (they belong to the segment boundaries)
        2. Split the inner text content on sentences
        3. If sentences are still too large, split on punctuation
        4. If still too large, split on newlines
        5. If still too large, force split at max_tokens

        Args:
            segment: Oversized segment to split
            global_tag_map: Global tag map for context

        Returns:
            List of smaller segments
        """
        # Try sentence splitting first
        sentence_segments = self._split_on_sentences(segment)

        result_segments = []
        for sent_seg in sentence_segments:
            sent_tokens = self.token_chunker.count_tokens(sent_seg)

            if sent_tokens <= self.max_tokens:
                result_segments.append(sent_seg)
            else:
                # Sentence is still too large, try punctuation split
                punct_segments = self._split_on_punctuation(sent_seg)

                for punct_seg in punct_segments:
                    punct_tokens = self.token_chunker.count_tokens(punct_seg)

                    if punct_tokens <= self.max_tokens:
                        result_segments.append(punct_seg)
                    else:
                        # Still too large, try newline split
                        newline_segments = self._split_on_newlines(punct_seg)

                        for nl_seg in newline_segments:
                            nl_tokens = self.token_chunker.count_tokens(nl_seg)

                            if nl_tokens <= self.max_tokens:
                                result_segments.append(nl_seg)
                            else:
                                # Last resort: force split at max_tokens
                                force_segments = self._force_split_at_tokens(nl_seg)
                                result_segments.extend(force_segments)

        return result_segments

    def _split_on_sentences(self, text: str) -> List[str]:
        """
        Split text on sentence boundaries (. ! ?) while preserving placeholders.

        Returns:
            List of sentence segments
        """
        # Find sentence boundaries (. ! ? followed by space or placeholder or end)
        # But don't split on abbreviations like "Mr.", "Dr.", etc.
        sentence_pattern = r'(?<=[.!?])\s+(?=\S)|(?<=[.!?])(?=\[\[)'

        parts = re.split(sentence_pattern, text)
        segments = []
        current = ""

        for part in parts:
            if not part.strip():
                continue

            # Check if adding this part would exceed max_tokens
            test_text = current + part
            if current and self.token_chunker.count_tokens(test_text) > self.max_tokens:
                # Save current and start new
                if current.strip():
                    segments.append(current)
                current = part
            else:
                current = test_text

        if current.strip():
            segments.append(current)

        return segments if segments else [text]

    def _split_on_punctuation(self, text: str) -> List[str]:
        """
        Split text on strong punctuation (; : ,) while preserving placeholders.

        Returns:
            List of punctuation-split segments
        """
        # Split on ; : , but keep the punctuation with the preceding text
        punct_pattern = r'(?<=[;:,])\s+(?=\S)|(?<=[;:,])(?=\[\[)'

        parts = re.split(punct_pattern, text)
        segments = []
        current = ""

        for part in parts:
            if not part.strip():
                continue

            test_text = current + part
            if current and self.token_chunker.count_tokens(test_text) > self.max_tokens:
                if current.strip():
                    segments.append(current)
                current = part
            else:
                current = test_text

        if current.strip():
            segments.append(current)

        return segments if segments else [text]

    def _split_on_newlines(self, text: str) -> List[str]:
        """
        Split text on newlines while preserving placeholders.

        Returns:
            List of newline-split segments
        """
        parts = text.split('\n')
        segments = []
        current = ""

        for part in parts:
            if not part.strip():
                continue

            test_text = current + '\n' + part if current else part
            if current and self.token_chunker.count_tokens(test_text) > self.max_tokens:
                if current.strip():
                    segments.append(current)
                current = part
            else:
                current = test_text

        if current.strip():
            segments.append(current)

        return segments if segments else [text]

    def _force_split_at_tokens(self, text: str) -> List[str]:
        """
        Force split text at max_tokens boundary as last resort.
        Tries to split at word boundaries when possible.

        Returns:
            List of force-split segments
        """
        segments = []
        remaining = text

        while remaining:
            # If remaining text fits, we're done
            if self.token_chunker.count_tokens(remaining) <= self.max_tokens:
                segments.append(remaining)
                break

            # Binary search for the largest prefix that fits
            left, right = 0, len(remaining)
            best_pos = left

            while left <= right:
                mid = (left + right) // 2
                prefix = remaining[:mid]
                token_count = self.token_chunker.count_tokens(prefix)

                if token_count <= self.max_tokens:
                    best_pos = mid
                    left = mid + 1
                else:
                    right = mid - 1

            # Find word boundary near best_pos
            split_pos = self._find_word_boundary_near(remaining, best_pos)

            # Avoid infinite loop - ensure we make progress
            if split_pos == 0:
                split_pos = max(1, best_pos)

            segments.append(remaining[:split_pos])
            remaining = remaining[split_pos:].lstrip()

        return segments

    def _find_word_boundary_near(self, text: str, pos: int) -> int:
        """
        Find a word boundary (space) near the given position.
        Looks backward first to avoid cutting words.
        """
        if pos >= len(text):
            return len(text)

        # Look backward for a space
        for i in range(pos, max(0, pos - 50), -1):
            if text[i] in ' \n\t':
                return i + 1

        # If no space found backward, look forward
        for i in range(pos, min(len(text), pos + 50)):
            if text[i] in ' \n\t':
                return i + 1

        # No word boundary found, split at pos
        return pos

    def _create_chunk(
        self,
        segments: List[str],
        global_tag_map: Dict[str, str],
        global_offset: int
    ) -> Dict:
        """
        Create a chunk with locally renumbered placeholders.

        Returns:
            {
                'text': "[id0]Hello[id1]world[id2]",
                'local_tag_map': {"[id0]": "<p>", "[id1]": "<b>", "[id2]": "</b></p>"},
                'global_offset': 5,
                'global_indices': [5, 6, 7]
            }
        """
        merged_text = "".join(segments)

        # Find all global placeholders in this chunk (including duplicates as separate entries)
        # Each occurrence will get a unique local index
        placeholder_occurrences = []

        for start, end, global_placeholder, global_idx in self.placeholder_format.find_all(merged_text):
            placeholder_occurrences.append((start, end, global_placeholder, global_idx))

        # Step 1: Replace each occurrence with a unique temporary marker
        # This prevents issues with overlapping replacements
        temp_markers = []
        for i, (start, end, global_placeholder, global_idx) in enumerate(placeholder_occurrences):
            temp_marker = f"__TEMP_PH_{i}__"
            temp_markers.append(temp_marker)

        # Apply temp markers in REVERSE order to avoid position shifts
        temp_text = merged_text
        for i in range(len(placeholder_occurrences) - 1, -1, -1):
            start, end, _, _ = placeholder_occurrences[i]
            temp_text = temp_text[:start] + temp_markers[i] + temp_text[end:]

        # Step 2: Replace temp markers with local placeholders (0, 1, 2, ...)
        renumbered_text = temp_text
        local_tag_map = {}
        global_indices = []

        for local_idx, (_, _, global_placeholder, global_idx) in enumerate(placeholder_occurrences):
            local_placeholder = self.placeholder_format.create(local_idx)
            temp_marker = temp_markers[local_idx]

            # Replace temp marker with local placeholder
            renumbered_text = renumbered_text.replace(temp_marker, local_placeholder, 1)

            # Build mapping
            local_tag_map[local_placeholder] = global_tag_map.get(global_placeholder, "")
            global_indices.append(global_idx)

        return {
            'text': renumbered_text,
            'local_tag_map': local_tag_map,
            'global_offset': global_offset,
            'global_indices': global_indices
        }


def extract_text_and_positions(text_with_placeholders: str) -> Tuple[str, Dict[int, float]]:
    """
    Extract pure text and calculate relative positions of placeholders.

    Uses unified placeholder format: [idN]

    Args:
        text_with_placeholders: "[id0]Hello [id1]world[id2]"

    Returns:
        ("Hello world", {0: 0.0, 1: 0.46, 2: 1.0})
    """
    # Use centralized placeholder format
    fmt = PlaceholderFormat.from_config()

    # Text without placeholders
    pure_text = fmt.remove_all(text_with_placeholders)
    pure_length = len(pure_text)

    if pure_length == 0:
        # Edge case: only placeholders, no text
        placeholders = fmt.find_all(text_with_placeholders)
        return "", {idx: i / max(1, len(placeholders))
                    for i, (_, _, _, idx) in enumerate(placeholders)}

    # Calculate relative position of each placeholder
    positions = {}

    for start, end, placeholder, idx in fmt.find_all(text_with_placeholders):
        # Text before this placeholder (without previous placeholders)
        text_before = fmt.remove_all(text_with_placeholders[:start])
        relative_pos = len(text_before) / pure_length
        positions[idx] = relative_pos

    return pure_text, positions


def reinsert_placeholders(
    translated_text: str,
    positions: Dict[int, float],
    placeholder_format: Optional[Tuple[str, str]] = None
) -> str:
    """
    Reinsert placeholders at proportional positions.

    Args:
        translated_text: "Bonjour monde"
        positions: {0: 0.0, 1: 0.5, 2: 1.0}
        placeholder_format: Optional (prefix, suffix) tuple.
                          If None, uses unified format [idN]
                          Examples: ("[id", "]")

    Returns:
        "[id0]Bonjour [id1]monde[id2]"
    """
    if not positions:
        return translated_text

    # Use centralized PlaceholderFormat
    if placeholder_format is None:
        fmt = PlaceholderFormat.from_config()
    else:
        # Support legacy tuple format for backward compatibility
        prefix, suffix = placeholder_format
        # Create pattern from prefix/suffix (simplified - assumes [idN] format)
        pattern = r'\[id(\d+)\]'
        fmt = PlaceholderFormat(prefix, suffix, pattern)

    text_length = len(translated_text)

    # Convert relative positions to absolute positions
    insertions = []
    for idx, rel_pos in positions.items():
        abs_pos = int(rel_pos * text_length)
        # Adjust to not cut a word (find nearest word boundary)
        abs_pos = find_nearest_word_boundary(translated_text, abs_pos)
        insertions.append((abs_pos, idx))

    # CRITICAL: Sort by position (descending) then by index (ASCENDING to preserve order)
    # When multiple placeholders have the same position, we must preserve their
    # sequential order (0, 1, 2...) to avoid tag mismatches.
    # We insert from end to start (reverse position) to avoid position shifting,
    # but within the same position, we insert in sequential order.
    insertions.sort(key=lambda x: (-x[0], x[1]))

    result = translated_text
    for abs_pos, idx in insertions:
        placeholder = fmt.create(idx)
        result = result[:abs_pos] + placeholder + result[abs_pos:]

    return result


def find_nearest_word_boundary(text: str, pos: int) -> int:
    """
    Find the nearest word boundary to the given position.
    Avoids cutting in the middle of a word.

    Handles multi-byte Unicode characters and various whitespace types.
    """
    if pos <= 0:
        return 0
    if pos >= len(text):
        return len(text)

    # Word boundary characters (spaces, punctuation, etc.)
    # Includes various Unicode whitespace and CJK punctuation
    def is_boundary(char: str) -> bool:
        return char in ' \t\n\r\u00A0\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200A\u202F\u205F\u3000.,;:!?\u3001\u3002\uff0c\uff1a\uff1b\uff1f\uff01'

    # If we're already on a boundary, perfect
    if is_boundary(text[pos]):
        return pos

    # Find the nearest boundary (before or after)
    left = pos
    right = pos

    while left > 0 and not is_boundary(text[left]):
        left -= 1
    while right < len(text) and not is_boundary(text[right]):
        right += 1

    # Return the closest one
    if pos - left <= right - pos:
        return left
    return right


class TranslationStats:
    """Track statistics for translation attempts and fallbacks.

    Translation flow:
    1. Phase 1: Normal translation (with retry attempts)
    2. Phase 2: Token alignment fallback (translate without placeholders, reinsert proportionally)
    3. Phase 3: Untranslated fallback (if all retries fail, returns original text)
    """

    def __init__(self):
        self.total_chunks = 0
        self.successful_first_try = 0
        self.successful_after_retry = 0  # Success on 2nd+ retry attempt (Phase 1)
        self.retry_attempts = 0  # Total number of retry attempts made
        self.token_alignment_used = 0  # Phase 2: Token alignment fallback used
        self.token_alignment_success = 0  # Phase 2: Token alignment succeeded
        self.fallback_used = 0  # Phase 3: Chunks returned untranslated after all phases failed
        self.placeholder_errors = 0  # Total placeholder validation errors encountered
        self.correction_attempts = 0  # Total LLM correction attempts made
        self.correction_success = 0  # Successful LLM corrections

    def log_summary(self, log_callback=None):
        """Log a summary of translation statistics."""
        summary_lines = [
            "=== Translation Summary ===",
            f"Total chunks: {self.total_chunks}",
            f"Success 1st try: {self.successful_first_try} ({self._pct(self.successful_first_try)}%)",
            f"Success after retry: {self.successful_after_retry} ({self._pct(self.successful_after_retry)}%)",
            f"Total retry attempts: {self.retry_attempts}",
        ]

        # Phase 2 stats (token alignment)
        if self.token_alignment_used > 0:
            summary_lines.extend([
                f"Token alignment fallback used: {self.token_alignment_used} ({self._pct(self.token_alignment_used)}%)",
                f"Token alignment success: {self.token_alignment_success}/{self.token_alignment_used} ({self._pct_of(self.token_alignment_success, self.token_alignment_used)}%)",
            ])

        # Phase 3 stats (untranslated fallback)
        if self.fallback_used > 0:
            summary_lines.append(f"Untranslated chunks (Phase 3 fallback): {self.fallback_used} ({self._pct(self.fallback_used)}%)")

        # Placeholder error tracking
        if self.placeholder_errors > 0:
            summary_lines.extend([
                "",
                "=== Placeholder Issues ===",
                f"Placeholder validation errors: {self.placeholder_errors}",
            ])
            if self.correction_attempts > 0:
                summary_lines.append(f"LLM correction attempts: {self.correction_attempts} (success: {self.correction_success})")

        # Recommendations
        if self.token_alignment_used > 0 or self.fallback_used > 0:
            summary_lines.extend([
                "",
                "=== Recommendations ===",
            ])

            if self.token_alignment_used > 0:
                summary_lines.append(
                    f"⚠️ {self.token_alignment_used} chunks used token alignment fallback (Phase 2)."
                )
                summary_lines.append(
                    "   This can cause minor layout imperfections due to proportional tag repositioning."
                )

            if self.fallback_used > 0:
                summary_lines.append(
                    f"⚠️ {self.fallback_used} chunks could not be translated (Phase 3 fallback)."
                )
                summary_lines.append(
                    "   These chunks remain in the source language."
                )

            summary_lines.extend([
                "",
                "To improve translation quality, consider:",
                "  • Using a more capable LLM model",
                "  • Reducing MAX_TOKENS_PER_CHUNK in .env (e.g., from 400 to 150)",
            ])

        summary = "\n".join(summary_lines)

        if log_callback:
            log_callback("translation_stats", summary)
        return summary

    def _pct(self, value):
        """Calculate percentage of total chunks."""
        if self.total_chunks == 0:
            return 0
        return round(value / self.total_chunks * 100, 1)

    def _pct_of(self, value, total):
        """Calculate percentage of a specific total."""
        if total == 0:
            return 0
        return round(value / total * 100, 1)

    def merge(self, other: 'TranslationStats') -> None:
        """Merge statistics from another TranslationStats instance.

        Args:
            other: Another TranslationStats instance to merge
        """
        self.total_chunks += other.total_chunks
        self.successful_first_try += other.successful_first_try
        self.successful_after_retry += other.successful_after_retry
        self.retry_attempts += other.retry_attempts
        self.token_alignment_used += other.token_alignment_used
        self.token_alignment_success += other.token_alignment_success
        self.fallback_used += other.fallback_used
        self.placeholder_errors += other.placeholder_errors
        self.correction_attempts += other.correction_attempts
        self.correction_success += other.correction_success


# === Enhanced Metrics (Phase 3) ===

import time
from dataclasses import dataclass, field


@dataclass
class TranslationMetrics:
    """Comprehensive translation metrics.

    Tracks counts, timing, token usage, and retry distribution.
    This is an enhanced version of TranslationStats for Phase 3 refactoring.
    """
    # === Counts ===
    total_chunks: int = 0
    successful_first_try: int = 0
    successful_after_retry: int = 0
    fallback_used: int = 0  # Chunks returned untranslated after all retries failed
    failed_chunks: int = 0

    # === Timing ===
    total_time_seconds: float = 0.0
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0

    # === Token Usage ===
    total_tokens_processed: int = 0
    total_tokens_generated: int = 0

    # === Retry Distribution ===
    retry_distribution: Dict[int, int] = field(default_factory=dict)
    """Map of retry_count -> number_of_chunks. Example: {0: 85, 1: 10, 2: 5}"""

    # === Chunk Size Stats ===
    min_chunk_size: int = field(default_factory=lambda: float('inf'))
    max_chunk_size: int = 0
    total_chunk_size: int = 0

    def record_success(self, attempt: int, chunk_size: int) -> None:
        """Record successful translation.

        Args:
            attempt: Attempt number (0 = first try)
            chunk_size: Size of chunk in tokens
        """
        self.total_chunks += 1

        if attempt == 0:
            self.successful_first_try += 1
        else:
            self.successful_after_retry += 1

        # Update retry distribution
        self.retry_distribution[attempt] = self.retry_distribution.get(attempt, 0) + 1

        # Update chunk size stats
        self._update_chunk_stats(chunk_size)

    def record_fallback(self, chunk_size: int) -> None:
        """Record fallback usage (untranslated chunk returned).

        Args:
            chunk_size: Size of chunk in tokens
        """
        self.total_chunks += 1
        self.fallback_used += 1
        self._update_chunk_stats(chunk_size)

    def record_failure(self, chunk_size: int) -> None:
        """Record failed translation.

        Args:
            chunk_size: Size of chunk in tokens
        """
        self.total_chunks += 1
        self.failed_chunks += 1
        self._update_chunk_stats(chunk_size)

    def _update_chunk_stats(self, chunk_size: int) -> None:
        """Update chunk size statistics."""
        self.min_chunk_size = min(self.min_chunk_size, chunk_size)
        self.max_chunk_size = max(self.max_chunk_size, chunk_size)
        self.total_chunk_size += chunk_size

    def finalize(self) -> None:
        """Finalize metrics (call when translation completes)."""
        self.end_time = time.time()
        self.total_time_seconds = self.end_time - self.start_time

    @property
    def avg_time_per_chunk(self) -> float:
        """Average time per chunk in seconds."""
        if self.total_chunks == 0:
            return 0.0
        return self.total_time_seconds / self.total_chunks

    @property
    def avg_chunk_size(self) -> float:
        """Average chunk size in tokens."""
        if self.total_chunks == 0:
            return 0.0
        return self.total_chunk_size / self.total_chunks

    @property
    def success_rate(self) -> float:
        """Success rate (excludes fallbacks)."""
        if self.total_chunks == 0:
            return 0.0
        successful = self.successful_first_try + self.successful_after_retry
        return successful / self.total_chunks

    @property
    def first_try_rate(self) -> float:
        """First-try success rate."""
        if self.total_chunks == 0:
            return 0.0
        return self.successful_first_try / self.total_chunks

    def to_dict(self) -> Dict:
        """Convert metrics to dictionary for serialization."""
        return {
            "total_chunks": self.total_chunks,
            "successful_first_try": self.successful_first_try,
            "successful_after_retry": self.successful_after_retry,
            "fallback_used": self.fallback_used,
            "failed_chunks": self.failed_chunks,
            "total_time_seconds": self.total_time_seconds,
            "avg_time_per_chunk": self.avg_time_per_chunk,
            "total_tokens_processed": self.total_tokens_processed,
            "total_tokens_generated": self.total_tokens_generated,
            "avg_chunk_size": self.avg_chunk_size,
            "min_chunk_size": self.min_chunk_size if self.min_chunk_size != float('inf') else 0,
            "max_chunk_size": self.max_chunk_size,
            "success_rate": self.success_rate,
            "first_try_rate": self.first_try_rate,
            "retry_distribution": self.retry_distribution
        }

    def log_summary(self, log_callback=None) -> None:
        """Log comprehensive summary.

        Args:
            log_callback: Optional callback for logging
        """
        summary = f"""
=== Translation Metrics Summary ===
Total Chunks: {self.total_chunks}
Success (first try): {self.successful_first_try} ({self.first_try_rate:.1%})
Success (after retry): {self.successful_after_retry}
Untranslated (fallback): {self.fallback_used}
Failed: {self.failed_chunks}

Overall Success Rate: {self.success_rate:.1%}

Timing:
  Total Time: {self.total_time_seconds:.2f}s
  Avg per Chunk: {self.avg_time_per_chunk:.2f}s

Tokens:
  Processed: {self.total_tokens_processed:,}
  Generated: {self.total_tokens_generated:,}

Chunk Sizes:
  Min: {self.min_chunk_size if self.min_chunk_size != float('inf') else 0} tokens
  Max: {self.max_chunk_size} tokens
  Avg: {self.avg_chunk_size:.1f} tokens

Retry Distribution:
"""
        for attempt, count in sorted(self.retry_distribution.items()):
            percentage = (count / self.total_chunks * 100) if self.total_chunks > 0 else 0
            summary += f"  {attempt} retries: {count} chunks ({percentage:.1f}%)\n"

        if log_callback:
            log_callback("translation_metrics", summary)
        else:
            print(summary)
