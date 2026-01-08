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
    ) -> List[int]:
        """
        Find positions where we can safely split without breaking an HTML block.

        A safe point is after a block closing placeholder (</p>, </div>, etc.)
        followed by a block opening placeholder (<p>, <div>, etc.)
        """
        safe_points = []

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
                        # Safe split point after this placeholder
                        safe_points.append(end)

        return safe_points

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

    def _split_at_points(self, text: str, points: List[int]) -> List[str]:
        """Split the text at the specified points"""
        if not points:
            return [text]

        segments = []
        prev = 0
        for point in points:
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
        Renumber placeholders locally for each chunk.
        """
        if not segments:
            return []

        chunks = []
        current_segments = []
        current_tokens = 0
        global_offset = 0

        for segment in segments:
            segment_tokens = self.token_chunker.count_tokens(segment)

            if current_tokens + segment_tokens > self.max_tokens and current_segments:
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

        # Find all global placeholders in this chunk
        global_placeholders = re.findall(r'\[\[\d+\]\]', merged_text)
        global_placeholders = list(dict.fromkeys(global_placeholders))  # Unique, order preserved

        # Create local mapping
        local_tag_map = {}
        global_indices = []
        renumbered_text = merged_text

        for local_idx, global_placeholder in enumerate(global_placeholders):
            local_placeholder = f"[[{local_idx}]]"
            local_tag_map[local_placeholder] = global_tag_map.get(global_placeholder, "")

            # Extract global index
            global_idx = int(global_placeholder[2:-2])
            global_indices.append(global_idx)

            # Renumber in text
            renumbered_text = renumbered_text.replace(global_placeholder, local_placeholder)

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
