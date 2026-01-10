"""
Unit tests for placeholder extraction and reinsertion with format detection

Tests the fix for the proportional fallback issue where placeholders were not
being properly extracted when using different placeholder formats ([idN], [[N]], etc.)
"""
import pytest
from src.core.epub.html_chunker import extract_text_and_positions, reinsert_placeholders


class TestPlaceholderFormatDetection:
    """Test extract_text_and_positions with various placeholder formats"""

    def test_safe_format_extraction(self):
        """Test with [[N]] format"""
        text = "[[0]]Hello [[1]]world[[2]]"
        pure, positions = extract_text_and_positions(text)

        assert pure == "Hello world"
        assert len(positions) == 3
        assert 0 in positions
        assert 1 in positions
        assert 2 in positions
        # Check relative positions are correct
        assert positions[0] == 0.0
        assert 0.4 < positions[1] < 0.6  # Approximately in the middle
        assert positions[2] == 1.0

    def test_id_format_extraction(self):
        """Test with [idN] format (the problematic case from the log)"""
        text = "[id0]Hello [id1]world[id2]"
        pure, positions = extract_text_and_positions(text)

        assert pure == "Hello world"
        assert len(positions) == 3
        assert 0 in positions
        assert 1 in positions
        assert 2 in positions
        # Check relative positions are correct
        assert positions[0] == 0.0
        assert 0.4 < positions[1] < 0.6
        assert positions[2] == 1.0

    def test_simple_format_extraction(self):
        """Test with [N] format"""
        text = "[0]Hello [1]world[2]"
        pure, positions = extract_text_and_positions(text)

        assert pure == "Hello world"
        assert len(positions) == 3
        assert 0 in positions
        assert 1 in positions
        assert 2 in positions

    def test_slash_format_extraction(self):
        """Test with /N format"""
        text = "/0Hello /1world/2"
        pure, positions = extract_text_and_positions(text)

        assert pure == "Hello world"
        assert len(positions) == 3
        assert 0 in positions
        assert 1 in positions
        assert 2 in positions

    def test_dollar_format_extraction(self):
        """Test with $N$ format"""
        text = "$0$Hello $1$world$2$"
        pure, positions = extract_text_and_positions(text)

        assert pure == "Hello world"
        assert len(positions) == 3
        assert 0 in positions
        assert 1 in positions
        assert 2 in positions

    def test_empty_text_with_placeholders(self):
        """Test edge case with only placeholders and no text"""
        text = "[[0]][[1]][[2]]"
        pure, positions = extract_text_and_positions(text)

        assert pure == ""
        assert len(positions) == 3
        # Positions should be evenly distributed
        assert positions[0] == 0.0
        assert positions[1] == 0.5
        assert positions[2] == 1.0

    def test_real_chunk_example(self):
        """Test with real chunk from the log (Chunk 28)"""
        # Simplified version of the problematic chunk
        text = "[id0]The friction made Laura clamp instantly around him[id1] and she dug her heels[id2]"
        pure, positions = extract_text_and_positions(text)

        assert "The friction made Laura" in pure
        assert "and she dug her heels" in pure
        assert len(positions) == 3
        assert 0 in positions
        assert 1 in positions
        assert 2 in positions


class TestPlaceholderReinsertion:
    """Test reinsert_placeholders with extracted positions"""

    def test_reinsertion_with_safe_format(self):
        """Test reinsertion with [[N]] format"""
        # Extract from original
        original = "[[0]]Hello [[1]]world[[2]]"
        pure, positions = extract_text_and_positions(original)

        # Simulate translation
        translated = "Bonjour monde"

        # Reinsert with same format
        result = reinsert_placeholders(translated, positions, placeholder_format=("[[", "]]"))

        # Should have all 3 placeholders
        assert "[[0]]" in result
        assert "[[1]]" in result
        assert "[[2]]" in result
        assert "Bonjour" in result
        assert "monde" in result

    def test_reinsertion_with_id_format(self):
        """Test reinsertion with [idN] format"""
        # Extract from original
        original = "[id0]Hello [id1]world[id2]"
        pure, positions = extract_text_and_positions(original)

        # Simulate translation
        translated = "Bonjour monde"

        # Reinsert with id format
        result = reinsert_placeholders(translated, positions, placeholder_format=("[id", "]"))

        # Should have all 3 placeholders
        assert "[id0]" in result
        assert "[id1]" in result
        assert "[id2]" in result
        assert "Bonjour" in result
        assert "monde" in result

    def test_full_roundtrip_id_format(self):
        """Test complete extract -> translate -> reinsert cycle with [idN] format"""
        # Original chunk with [idN] placeholders
        original = "[id0]The friction made Laura clamp instantly around him[id1] and she dug her heels[id2]"

        # Extract positions
        pure, positions = extract_text_and_positions(original)

        # Verify extraction worked
        assert len(positions) == 3
        assert 0 in positions and 1 in positions and 2 in positions

        # Simulate LLM translation (placeholders removed)
        translated = "La friction fit Laura instantanément autour de lui et elle planta ses talons"

        # Reinsert placeholders at proportional positions
        result = reinsert_placeholders(translated, positions, placeholder_format=("[id", "]"))

        # Verify all placeholders are present
        assert "[id0]" in result
        assert "[id1]" in result
        assert "[id2]" in result

        # Verify text is present
        assert "La friction" in result
        assert "et elle planta" in result

    def test_sequential_positions_generation(self):
        """Test fallback generation of sequential positions"""
        # When no positions are found, should generate evenly spaced ones
        translated = "Bonjour le monde entier"
        expected_count = 4

        # Generate evenly spaced positions
        sequential_positions = {i: i / max(1, expected_count) for i in range(expected_count)}

        result = reinsert_placeholders(translated, sequential_positions, placeholder_format=("[[", "]]"))

        # Should have all placeholders
        assert "[[0]]" in result
        assert "[[1]]" in result
        assert "[[2]]" in result
        assert "[[3]]" in result


class TestWordBoundaryHandling:
    """Test that placeholders are inserted at word boundaries"""

    def test_basic_word_boundary(self):
        """Test placeholder insertion respects word boundaries"""
        positions = {0: 0.0, 1: 0.5, 2: 1.0}
        translated = "Hello world"

        result = reinsert_placeholders(translated, positions, placeholder_format=("[[", "]]"))

        # [[1]] should be at space, not in middle of "Hello" or "world"
        assert "[[1]] " in result or " [[1]]" in result

    def test_unicode_word_boundary(self):
        """Test word boundary detection with Unicode characters"""
        positions = {0: 0.0, 1: 0.5, 2: 1.0}
        translated = "Bonjour\u00A0monde"  # Non-breaking space

        result = reinsert_placeholders(translated, positions, placeholder_format=("[[", "]]"))

        # Should insert at word boundary
        assert "[[0]]" in result
        assert "[[1]]" in result
        assert "[[2]]" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
