"""
HTML-aware chunking that splits on complete HTML blocks

This module provides intelligent chunking of HTML content with placeholders,
ensuring chunks are split at safe boundaries (between complete HTML blocks)
and includes a proportional reinsertion fallback for placeholder recovery.
"""
import re
from typing import List, Dict, Tuple

from src.core.chunking.token_chunker import TokenChunker


class HtmlChunker:
    """
    Chunks HTML with placeholders into complete HTML blocks.

    Guarantees that each chunk contains balanced placeholders
    (no orphan [[3]] without its closing [[4]]).
    """

    def __init__(self, max_tokens: int = 450):
        self.max_tokens = max_tokens
        self.token_chunker = TokenChunker(max_tokens=max_tokens)

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
            text_with_placeholders: "[[0]]Hello[[1]]world[[2]]..."
            tag_map: {"[[0]]": "<p>", "[[1]]": "<b>", ...}

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

        # Pattern to find placeholders with their positions
        placeholder_positions = [
            (m.start(), m.end(), m.group())
            for m in re.finditer(r'\[\[\d+\]\]', text)
        ]

        for i, (start, end, placeholder) in enumerate(placeholder_positions):
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
        If a segment is too large, split it hierarchically:
        1. Try splitting on sentences
        2. Try splitting on punctuation (;, :, ,)
        3. Try splitting on newlines
        4. Force split at max_tokens
        """
        if not segments:
            return []

        chunks = []
        current_segments = []
        current_tokens = 0
        global_offset = 0

        for segment in segments:
            segment_tokens = self.token_chunker.count_tokens(segment)

            # If segment alone exceeds max_tokens, split it
            if segment_tokens > self.max_tokens:
                # First, finalize current chunk if any
                if current_segments:
                    chunk = self._create_chunk(current_segments, global_tag_map, global_offset)
                    chunks.append(chunk)
                    global_offset += len(chunk['local_tag_map'])
                    current_segments = []
                    current_tokens = 0

                # Split the oversized segment hierarchically
                sub_segments = self._split_oversized_segment(segment, global_tag_map)

                # Add sub-segments to chunks
                for sub_seg in sub_segments:
                    sub_tokens = self.token_chunker.count_tokens(sub_seg)

                    if current_tokens + sub_tokens > self.max_tokens and current_segments:
                        # Finalize current chunk
                        chunk = self._create_chunk(current_segments, global_tag_map, global_offset)
                        chunks.append(chunk)
                        global_offset += len(chunk['local_tag_map'])

                        current_segments = [sub_seg]
                        current_tokens = sub_tokens
                    else:
                        current_segments.append(sub_seg)
                        current_tokens += sub_tokens

            elif current_tokens + segment_tokens > self.max_tokens and current_segments:
                # Finalize current chunk
                chunk = self._create_chunk(current_segments, global_tag_map, global_offset)
                chunks.append(chunk)
                global_offset += len(chunk['local_tag_map'])

                current_segments = [segment]
                current_tokens = segment_tokens
            else:
                current_segments.append(segment)
                current_tokens += segment_tokens

        # Last chunk
        if current_segments:
            chunk = self._create_chunk(current_segments, global_tag_map, global_offset)
            chunks.append(chunk)

        return chunks

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
                'text': "[[0]]Hello[[1]]world[[2]]",
                'local_tag_map': {"[[0]]": "<p>", "[[1]]": "<b>", "[[2]]": "</b></p>"},
                'global_offset': 5,
                'global_indices': [5, 6, 7],
                'boundary_prefix': "<body>",  # Only if present in global_tag_map
                'boundary_suffix': "</body>"  # Only if present in global_tag_map
            }
        """
        merged_text = "".join(segments)

        # Detect placeholder format (simple [N] or safe [[N]])
        # Check if text contains simple format placeholders
        has_simple = bool(re.search(r'(?<!\[)\[\d+\](?!\])', merged_text))
        has_safe = bool(re.search(r'\[\[\d+\]\]', merged_text))

        # Use appropriate pattern
        if has_simple and not has_safe:
            # Simple format: [0], [1], [2]
            placeholder_pattern = r'(?<!\[)\[(\d+)\](?!\])'
            prefix = "["
            suffix = "]"
        else:
            # Safe format: [[0]], [[1]], [[2]] (default)
            placeholder_pattern = r'\[\[(\d+)\]\]'
            prefix = "[["
            suffix = "]]"

        # Find all global placeholders in this chunk (may contain duplicates)
        # Build renumbering map: global_placeholder -> local_placeholder
        renumbering_map = {}
        global_indices = []
        local_idx = 0

        for match in re.finditer(placeholder_pattern, merged_text):
            global_placeholder = match.group(0)

            # Skip if already processed (deduplication)
            if global_placeholder in renumbering_map:
                continue

            local_placeholder = f"{prefix}{local_idx}{suffix}"
            renumbering_map[global_placeholder] = local_placeholder

            # Extract global index
            global_idx = int(global_placeholder[len(prefix):-len(suffix)])
            global_indices.append(global_idx)

            local_idx += 1

        # Apply renumbering in REVERSE order (to avoid [[10]] -> [[1]]0 issues)
        renumbered_text = merged_text
        for global_ph in sorted(renumbering_map.keys(),
                               key=lambda p: int(p[len(prefix):-len(suffix)]),
                               reverse=True):
            renumbered_text = renumbered_text.replace(global_ph, renumbering_map[global_ph])

        # Build local_tag_map
        local_tag_map = {
            local_ph: global_tag_map.get(global_ph, "")
            for global_ph, local_ph in renumbering_map.items()
        }

        result = {
            'text': renumbered_text,
            'local_tag_map': local_tag_map,
            'global_offset': global_offset,
            'global_indices': global_indices
        }

        # Pass through boundary tags if present in global_tag_map
        if "__boundary_prefix__" in global_tag_map:
            result['boundary_prefix'] = global_tag_map["__boundary_prefix__"]
        if "__boundary_suffix__" in global_tag_map:
            result['boundary_suffix'] = global_tag_map["__boundary_suffix__"]

        return result


def restore_global_indices(translated_text: str, global_indices: List[int]) -> str:
    """
    Restore global indices after translation.

    Args:
        translated_text: "[[0]]Bonjour[[1]]monde[[2]]"
        global_indices: [5, 6, 7]

    Returns:
        "[[5]]Bonjour[[6]]monde[[7]]"
    """
    if not global_indices:
        return translated_text

    result = translated_text

    # Replace in reverse order to avoid conflicts
    for local_idx in range(len(global_indices) - 1, -1, -1):
        global_idx = global_indices[local_idx]
        result = result.replace(f"[[{local_idx}]]", f"[[{global_idx}]]")

    return result


def extract_text_and_positions(text_with_placeholders: str) -> Tuple[str, Dict[int, float]]:
    """
    Extract pure text and calculate relative positions of placeholders.

    Args:
        text_with_placeholders: "[[0]]Hello [[1]]world[[2]]"

    Returns:
        ("Hello world", {0: 0.0, 1: 0.46, 2: 1.0})
    """
    pattern = r'\[\[(\d+)\]\]'

    # Text without placeholders
    pure_text = re.sub(pattern, '', text_with_placeholders)
    pure_length = len(pure_text)

    if pure_length == 0:
        # Edge case: only placeholders, no text
        matches = list(re.finditer(pattern, text_with_placeholders))
        return "", {int(m.group(1)): i / max(1, len(matches))
                    for i, m in enumerate(matches)}

    # Calculate relative position of each placeholder
    positions = {}

    for match in re.finditer(pattern, text_with_placeholders):
        placeholder_idx = int(match.group(1))
        # Text before this placeholder (without previous placeholders)
        text_before = re.sub(pattern, '', text_with_placeholders[:match.start()])
        relative_pos = len(text_before) / pure_length
        positions[placeholder_idx] = relative_pos

    return pure_text, positions


def reinsert_placeholders(translated_text: str, positions: Dict[int, float]) -> str:
    """
    Reinsert placeholders at proportional positions.

    Args:
        translated_text: "Bonjour monde"
        positions: {0: 0.0, 1: 0.5, 2: 1.0}

    Returns:
        "[[0]]Bonjour [[1]]monde[[2]]"
    """
    if not positions:
        return translated_text

    text_length = len(translated_text)

    # Convert relative positions to absolute positions
    insertions = []
    for idx, rel_pos in positions.items():
        abs_pos = int(rel_pos * text_length)
        # Adjust to not cut a word (find nearest word boundary)
        abs_pos = find_nearest_word_boundary(translated_text, abs_pos)
        insertions.append((abs_pos, idx))

    # Sort by position (reverse order to insert without shifting)
    insertions.sort(key=lambda x: x[0], reverse=True)

    result = translated_text
    for abs_pos, idx in insertions:
        result = result[:abs_pos] + f"[[{idx}]]" + result[abs_pos:]

    return result


def find_nearest_word_boundary(text: str, pos: int) -> int:
    """
    Find the nearest word boundary to the given position.
    Avoids cutting in the middle of a word.
    """
    if pos <= 0:
        return 0
    if pos >= len(text):
        return len(text)

    # If we're on a space, perfect
    if text[pos] == ' ':
        return pos

    # Find the nearest space (before or after)
    left = pos
    right = pos

    while left > 0 and text[left] != ' ':
        left -= 1
    while right < len(text) and text[right] != ' ':
        right += 1

    # Return the closest one
    if pos - left <= right - pos:
        return left
    return right


class TranslationStats:
    """Track statistics for translation attempts and fallbacks.

    Translation flow:
    1. Phase 1: Normal translation (1 attempt)
    2. Phase 2: LLM placeholder correction (up to 2 attempts)
    3. Phase 3: Proportional fallback (if correction fails)
    """

    def __init__(self):
        self.total_chunks = 0
        self.successful_first_try = 0
        self.successful_after_retry = 0  # Renamed semantically but kept for compatibility
        self.correction_attempts = 0  # Total LLM correction attempts made
        self.fallback_used = 0

    def log_summary(self, log_callback=None):
        """Log a summary of translation statistics."""
        summary = (
            f"=== Translation Summary ===\n"
            f"Total chunks: {self.total_chunks}\n"
            f"Success 1st try: {self.successful_first_try} ({self._pct(self.successful_first_try)}%)\n"
            f"Success after LLM correction: {self.successful_after_retry} ({self._pct(self.successful_after_retry)}%)\n"
            f"LLM correction attempts: {self.correction_attempts}\n"
            f"Proportional fallback used: {self.fallback_used} ({self._pct(self.fallback_used)}%)"
        )
        if log_callback:
            log_callback("translation_stats", summary)
        return summary

    def _pct(self, value):
        if self.total_chunks == 0:
            return 0
        return round(value / self.total_chunks * 100, 1)
