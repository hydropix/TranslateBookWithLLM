"""Unit tests for HtmlChunker helper functions.

Tests the refactored helper methods extracted from _merge_segments_into_chunks.
"""

import pytest
from src.core.epub.html_chunker import HtmlChunker


class TestCountSegmentTokens:
    """Test _count_segment_tokens helper method."""

    def test_count_empty_segment(self):
        """Empty segment should return 0 tokens."""
        chunker = HtmlChunker(max_tokens=400)

        tokens = chunker._count_segment_tokens("")

        assert tokens == 0

    def test_count_simple_text(self):
        """Simple text should return correct token count."""
        chunker = HtmlChunker(max_tokens=400)

        tokens = chunker._count_segment_tokens("Hello world")

        assert tokens > 0
        assert isinstance(tokens, int)

    def test_count_text_with_placeholders(self):
        """Text with placeholders should count placeholders as tokens."""
        chunker = HtmlChunker(max_tokens=400)

        tokens = chunker._count_segment_tokens("[[0]]Hello world[[1]]")

        assert tokens > 0
        assert isinstance(tokens, int)


class TestWouldExceedLimit:
    """Test _would_exceed_limit helper method."""

    def test_within_limit(self):
        """Adding tokens within limit should return False."""
        chunker = HtmlChunker(max_tokens=400)

        result = chunker._would_exceed_limit(current_tokens=200, new_tokens=100)

        assert result is False

    def test_exactly_at_limit(self):
        """Adding tokens to exactly reach limit should return False."""
        chunker = HtmlChunker(max_tokens=400)

        result = chunker._would_exceed_limit(current_tokens=300, new_tokens=100)

        assert result is False

    def test_exceeds_limit(self):
        """Adding tokens that exceed limit should return True."""
        chunker = HtmlChunker(max_tokens=400)

        result = chunker._would_exceed_limit(current_tokens=300, new_tokens=101)

        assert result is True

    def test_far_exceeds_limit(self):
        """Adding tokens that far exceed limit should return True."""
        chunker = HtmlChunker(max_tokens=400)

        result = chunker._would_exceed_limit(current_tokens=350, new_tokens=200)

        assert result is True

    def test_zero_current_tokens(self):
        """Zero current tokens should work correctly."""
        chunker = HtmlChunker(max_tokens=400)

        result = chunker._would_exceed_limit(current_tokens=0, new_tokens=100)

        assert result is False

    def test_zero_new_tokens(self):
        """Zero new tokens should work correctly."""
        chunker = HtmlChunker(max_tokens=400)

        result = chunker._would_exceed_limit(current_tokens=200, new_tokens=0)

        assert result is False


class TestFinalizeChunk:
    """Test _finalize_chunk helper method."""

    def test_finalize_single_segment(self):
        """Finalizing a single segment should create valid chunk."""
        chunker = HtmlChunker(max_tokens=400)
        segments = ["[[0]]Hello world[[1]]"]
        global_tag_map = {"[[0]]": "<p>", "[[1]]": "</p>"}
        global_offset = 0

        chunk = chunker._finalize_chunk(segments, global_tag_map, global_offset)

        assert 'text' in chunk
        assert 'local_tag_map' in chunk
        assert 'global_offset' in chunk
        assert 'global_indices' in chunk
        assert chunk['global_offset'] == 0

    def test_finalize_multiple_segments(self):
        """Finalizing multiple segments should merge them correctly."""
        chunker = HtmlChunker(max_tokens=400)
        segments = ["[[0]]Hello[[1]]", "[[2]]world[[3]]"]
        global_tag_map = {
            "[[0]]": "<p>",
            "[[1]]": "</p>",
            "[[2]]": "<p>",
            "[[3]]": "</p>"
        }
        global_offset = 0

        chunk = chunker._finalize_chunk(segments, global_tag_map, global_offset)

        assert 'text' in chunk
        assert 'local_tag_map' in chunk
        # Should have merged both segments
        assert "Hello" in chunk['text']
        assert "world" in chunk['text']

    def test_finalize_with_offset(self):
        """Finalizing with non-zero offset should preserve offset."""
        chunker = HtmlChunker(max_tokens=400)
        segments = ["[[5]]Hello[[6]]"]
        global_tag_map = {"[[5]]": "<p>", "[[6]]": "</p>"}
        global_offset = 10

        chunk = chunker._finalize_chunk(segments, global_tag_map, global_offset)

        assert chunk['global_offset'] == 10

    def test_finalize_renumbers_placeholders(self):
        """Finalizing should renumber placeholders locally."""
        chunker = HtmlChunker(max_tokens=400)
        segments = ["[[5]]Hello[[6]]world[[7]]"]
        global_tag_map = {
            "[[5]]": "<p>",
            "[[6]]": "<b>",
            "[[7]]": "</b></p>"
        }
        global_offset = 0

        chunk = chunker._finalize_chunk(segments, global_tag_map, global_offset)

        # Should renumber to [[0]], [[1]], [[2]]
        assert "[[0]]" in chunk['text']
        assert "[[1]]" in chunk['text']
        assert "[[2]]" in chunk['text']
        # Original placeholders should not be in text
        assert "[[5]]" not in chunk['text']
        assert "[[6]]" not in chunk['text']
        assert "[[7]]" not in chunk['text']


class TestMergeSegmentsIntegration:
    """Integration tests for _merge_segments_into_chunks using helper functions."""

    def test_merge_small_segments(self):
        """Small segments should be merged into single chunk."""
        chunker = HtmlChunker(max_tokens=400)
        segments = [
            "[[0]]Hello[[1]]",
            "[[2]]world[[3]]",
            "[[4]]test[[5]]"
        ]
        global_tag_map = {
            "[[0]]": "<p>", "[[1]]": "</p>",
            "[[2]]": "<p>", "[[3]]": "</p>",
            "[[4]]": "<p>", "[[5]]": "</p>"
        }

        chunks = chunker._merge_segments_into_chunks(segments, global_tag_map)

        # All small segments should fit in one chunk
        assert len(chunks) >= 1
        assert all('text' in chunk for chunk in chunks)
        assert all('local_tag_map' in chunk for chunk in chunks)

    def test_merge_creates_multiple_chunks(self):
        """Large segments should be split into multiple chunks."""
        chunker = HtmlChunker(max_tokens=50)  # Very small limit
        # Create segments with enough content to exceed limit
        long_text = " ".join(["word"] * 100)
        segments = [
            f"[[0]]{long_text}[[1]]",
            f"[[2]]{long_text}[[3]]"
        ]
        global_tag_map = {
            "[[0]]": "<p>", "[[1]]": "</p>",
            "[[2]]": "<p>", "[[3]]": "</p>"
        }

        chunks = chunker._merge_segments_into_chunks(segments, global_tag_map)

        # Should create multiple chunks due to token limit
        assert len(chunks) >= 2

    def test_merge_preserves_global_indices(self):
        """Merging should preserve global indices for reconstruction."""
        chunker = HtmlChunker(max_tokens=400)
        segments = ["[[0]]Hello[[1]]", "[[2]]world[[3]]"]
        global_tag_map = {
            "[[0]]": "<p>", "[[1]]": "</p>",
            "[[2]]": "<p>", "[[3]]": "</p>"
        }

        chunks = chunker._merge_segments_into_chunks(segments, global_tag_map)

        # Each chunk should have global_indices
        for chunk in chunks:
            assert 'global_indices' in chunk
            assert isinstance(chunk['global_indices'], list)


class TestHelperFunctionsWithDifferentMaxTokens:
    """Test helper functions with different max_tokens settings."""

    def test_would_exceed_with_small_limit(self):
        """Helper should respect small token limits."""
        chunker = HtmlChunker(max_tokens=10)

        assert chunker._would_exceed_limit(5, 6) is True
        assert chunker._would_exceed_limit(5, 5) is False
        assert chunker._would_exceed_limit(5, 4) is False

    def test_would_exceed_with_large_limit(self):
        """Helper should respect large token limits."""
        chunker = HtmlChunker(max_tokens=1000)

        assert chunker._would_exceed_limit(500, 501) is True
        assert chunker._would_exceed_limit(500, 500) is False
        assert chunker._would_exceed_limit(999, 2) is True
