"""
Token-based text chunking with natural boundary preservation.

This module provides intelligent text chunking based on token counts
using tiktoken, while respecting natural text boundaries (paragraphs and sentences).
"""
import re
from typing import List, Dict
import tiktoken

from src.config import SENTENCE_TERMINATORS


class TokenChunker:
    """
    Token-based text chunker that respects natural boundaries.

    Uses a soft limit approach: accumulates content until reaching ~80% of max tokens,
    then completes at the next natural boundary (paragraph or sentence).
    """

    def __init__(self, max_tokens: int = 800, soft_limit_ratio: float = 0.8):
        """
        Initialize the TokenChunker.

        Args:
            max_tokens: Maximum tokens per chunk (hard limit)
            soft_limit_ratio: Ratio at which to start looking for boundaries (default 0.8 = 80%)
        """
        self.max_tokens = max_tokens
        self.soft_limit = int(max_tokens * soft_limit_ratio)
        self.encoder = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in a text string.

        Args:
            text: Input text

        Returns:
            Number of tokens
        """
        if not text:
            return 0
        return len(self.encoder.encode(text))

    def split_into_paragraphs(self, text: str) -> List[str]:
        """
        Split text into paragraphs using double newlines.

        Args:
            text: Input text

        Returns:
            List of paragraphs (preserving single newlines within)
        """
        # Split on double newlines (or more)
        paragraphs = re.split(r'\n\s*\n', text)
        # Filter out empty paragraphs but preserve whitespace-only ones as empty markers
        return [p for p in paragraphs if p.strip()]

    def split_paragraph_into_sentences(self, paragraph: str) -> List[str]:
        """
        Split a paragraph into sentences for finer-grained chunking.

        Used when a single paragraph exceeds max_tokens.

        Args:
            paragraph: Input paragraph text

        Returns:
            List of sentences
        """
        # Create regex pattern from sentence terminators
        sorted_terminators = sorted(list(SENTENCE_TERMINATORS), key=len, reverse=True)
        escaped_terminators = [re.escape(t) for t in sorted_terminators]
        pattern = '|'.join(escaped_terminators)

        sentences = []
        last_end = 0

        for match in re.finditer(pattern, paragraph):
            end = match.end()
            sentence = paragraph[last_end:end].strip()
            if sentence:
                sentences.append(sentence)
            last_end = end

        # Add remaining text if any
        remaining = paragraph[last_end:].strip()
        if remaining:
            sentences.append(remaining)

        # If no sentences found (no terminators), return the whole paragraph
        if not sentences and paragraph.strip():
            sentences = [paragraph.strip()]

        return sentences

    def _chunk_units(self, units: List[str], separator: str = "\n\n") -> List[str]:
        """
        Chunk a list of text units (paragraphs or sentences) into appropriately sized chunks.

        Args:
            units: List of text units to chunk
            separator: Separator to use when joining units

        Returns:
            List of chunk strings
        """
        chunks = []
        current_units = []
        current_tokens = 0

        for unit in units:
            unit_tokens = self.count_tokens(unit)

            # If single unit exceeds max, we need to handle it specially
            if unit_tokens > self.max_tokens:
                # First, save current chunk if not empty
                if current_units:
                    chunks.append(separator.join(current_units))
                    current_units = []
                    current_tokens = 0

                # If it's a paragraph, try splitting into sentences
                sentences = self.split_paragraph_into_sentences(unit)
                if len(sentences) > 1:
                    # Recursively chunk sentences
                    sentence_chunks = self._chunk_units(sentences, separator=" ")
                    chunks.extend(sentence_chunks)
                else:
                    # Can't split further, just add it as-is (will exceed limit)
                    chunks.append(unit)
                continue

            # Check if adding this unit would exceed limits
            potential_tokens = current_tokens + unit_tokens
            if current_units:
                # Account for separator
                potential_tokens += self.count_tokens(separator)

            # If we're past soft limit, check if we should start a new chunk
            if current_tokens >= self.soft_limit and potential_tokens > self.max_tokens:
                # Save current chunk and start new one
                chunks.append(separator.join(current_units))
                current_units = [unit]
                current_tokens = unit_tokens
            elif potential_tokens > self.max_tokens:
                # Would exceed hard limit, start new chunk
                if current_units:
                    chunks.append(separator.join(current_units))
                current_units = [unit]
                current_tokens = unit_tokens
            else:
                # Add to current chunk
                current_units.append(unit)
                current_tokens = potential_tokens

        # Don't forget the last chunk
        if current_units:
            chunks.append(separator.join(current_units))

        return chunks

    def chunk_text(self, text: str) -> List[Dict[str, str]]:
        """
        Split text into chunks with context preservation.

        Main algorithm:
        1. Split into paragraphs
        2. Accumulate until soft_limit (~80%)
        3. If next paragraph would exceed max_tokens, finalize chunk
        4. If single paragraph > max_tokens, split into sentences
        5. Return chunks with context_before/main_content/context_after

        Args:
            text: Input text to chunk

        Returns:
            List of chunk dictionaries with keys:
            - context_before: Last paragraph of previous chunk (for context)
            - main_content: Main content to translate
            - context_after: First paragraph of next chunk (for context)
        """
        if not text or not text.strip():
            return []

        # Split into paragraphs
        paragraphs = self.split_into_paragraphs(text)

        if not paragraphs:
            return []

        # Chunk paragraphs
        raw_chunks = self._chunk_units(paragraphs, separator="\n\n")

        if not raw_chunks:
            return []

        # Build structured chunks with context
        structured_chunks = []

        for i, chunk_content in enumerate(raw_chunks):
            # Context before: last part of previous chunk
            if i > 0:
                prev_paragraphs = self.split_into_paragraphs(raw_chunks[i - 1])
                context_before = prev_paragraphs[-1] if prev_paragraphs else ""
            else:
                context_before = ""

            # Context after: first part of next chunk
            if i < len(raw_chunks) - 1:
                next_paragraphs = self.split_into_paragraphs(raw_chunks[i + 1])
                context_after = next_paragraphs[0] if next_paragraphs else ""
            else:
                context_after = ""

            structured_chunks.append({
                "context_before": context_before,
                "main_content": chunk_content,
                "context_after": context_after
            })

        return structured_chunks

    def get_stats(self, chunks: List[Dict[str, str]]) -> Dict:
        """
        Get statistics about the chunked text.

        Args:
            chunks: List of chunk dictionaries from chunk_text()

        Returns:
            Dictionary with statistics
        """
        if not chunks:
            return {
                "total_chunks": 0,
                "avg_tokens": 0,
                "min_tokens": 0,
                "max_tokens": 0,
                "chunks_in_range": 0,
                "compliance_rate": 0.0
            }

        token_counts = [self.count_tokens(c["main_content"]) for c in chunks]

        # Calculate how many are within acceptable range (soft_limit to max_tokens)
        in_range = sum(1 for t in token_counts if t <= self.max_tokens)

        return {
            "total_chunks": len(chunks),
            "avg_tokens": sum(token_counts) / len(token_counts),
            "min_tokens": min(token_counts),
            "max_tokens": max(token_counts),
            "chunks_in_range": in_range,
            "compliance_rate": in_range / len(chunks) * 100
        }
