"""
HTML-aware chunking that splits on complete HTML blocks

This module provides intelligent chunking of HTML content with placeholders,
ensuring chunks are split at safe boundaries (between complete HTML blocks)
and includes a proportional reinsertion fallback for placeholder recovery.
"""
from typing import List, Dict, Tuple

from src.core.chunking.token_chunker import TokenChunker
from src.common.placeholder_format import PlaceholderFormat
from .text_splitter import TextSplitter
from .tag_classifier import TagClassifier
from .placeholder_renumberer import PlaceholderRenumberer


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
        self.text_splitter = TextSplitter(max_tokens, self.token_chunker)
        self.tag_classifier = TagClassifier()
        self.renumberer = PlaceholderRenumberer()

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
            if self.tag_classifier.is_block_closing_tag(tag):
                # Check if next placeholder is a block opening tag
                if i + 1 < len(placeholder_positions):
                    next_placeholder = placeholder_positions[i + 1][2]
                    next_tag = tag_map.get(next_placeholder, "")
                    if self.tag_classifier.is_block_opening_tag(next_tag):
                        # Determine priority based on tag type
                        priority = self.tag_classifier.get_split_priority(tag)
                        split_points.append((end, priority))

        return split_points

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
        merged_text = "".join(segments)
        return self.renumberer.create_chunk_with_local_placeholders(
            merged_text, global_tag_map, global_offset
        )

    def _split_oversized_segment(
        self,
        segment: str,
        global_tag_map: Dict[str, str]
    ) -> List[str]:
        """
        Split an oversized segment hierarchically using TextSplitter.

        Args:
            segment: Oversized segment to split
            global_tag_map: Global tag map for context

        Returns:
            List of smaller segments
        """
        return self.text_splitter.split_oversized_segment(segment)


# Utility functions moved to html_utils.py
# Translation statistics classes moved to translation_metrics.py
# Placeholder renumbering logic moved to placeholder_renumberer.py
