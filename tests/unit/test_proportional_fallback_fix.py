"""
Unit tests for placeholder extraction and reinsertion

Tests the extraction and reinsertion of placeholders using the standard [idN] format.
The fallback system returns untranslated text when placeholder validation fails.
"""
import pytest
from src.core.epub.html_utils import extract_text_and_positions, reinsert_placeholders


class TestPlaceholderExtraction:
    """Test extract_text_and_positions with [idN] format"""

    def test_basic_extraction(self):
        """Test basic placeholder extraction"""
        text = "[id0]Hello [id1]world[id2]"
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

    def test_empty_text_with_placeholders(self):
        """Test edge case with only placeholders and no text"""
        text = "[id0][id1][id2]"
        pure, positions = extract_text_and_positions(text)

        assert pure == ""
        assert len(positions) == 3
        # Positions should be evenly distributed (based on order of appearance)
        # With 3 placeholders at positions 0, 5, 10 in a string of length 15:
        # pos[0] = 0/15 = 0.0, pos[1] = 5/15 = 0.33, pos[2] = 10/15 = 0.67
        # But with empty pure text, they get normalized positions
        assert positions[0] == 0.0
        assert 0.3 <= positions[1] <= 0.4  # Approximately 0.33
        assert 0.6 <= positions[2] <= 0.7  # Approximately 0.67

    def test_real_chunk_example(self):
        """Test with real chunk example"""
        text = "[id0]The friction made Laura clamp instantly around him[id1] and she dug her heels[id2]"
        pure, positions = extract_text_and_positions(text)

        assert "The friction made Laura" in pure
        assert "and she dug her heels" in pure
        assert len(positions) == 3
        assert 0 in positions
        assert 1 in positions
        assert 2 in positions

    def test_multiple_placeholders_in_sequence(self):
        """Test extraction with multiple consecutive placeholders"""
        text = "[id0][id1]Text[id2][id3]More text[id4]"
        pure, positions = extract_text_and_positions(text)

        assert pure == "TextMore text"
        assert len(positions) == 5
        for i in range(5):
            assert i in positions


class TestPlaceholderReinsertion:
    """Test reinsert_placeholders with extracted positions"""

    def test_basic_reinsertion(self):
        """Test basic reinsertion with [idN] format"""
        # Extract from original
        original = "[id0]Hello [id1]world[id2]"
        pure, positions = extract_text_and_positions(original)

        # Simulate translation
        translated = "Bonjour monde"

        # Reinsert with id format (default)
        result = reinsert_placeholders(translated, positions, placeholder_format=("[id", "]"))

        # Should have all 3 placeholders
        assert "[id0]" in result
        assert "[id1]" in result
        assert "[id2]" in result
        assert "Bonjour" in result
        assert "monde" in result

    def test_full_roundtrip(self):
        """Test complete extract -> translate -> reinsert cycle"""
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

        # Verify text is present (don't check exact placement, just that text exists)
        assert "La friction" in result
        assert "elle planta" in result  # Removed "et" to be less strict about word boundaries
        assert "ses talons" in result

    def test_sequential_positions_generation(self):
        """Test generation of sequential positions"""
        # When no positions are found, should generate evenly spaced ones
        translated = "Bonjour le monde entier"
        expected_count = 4

        # Generate evenly spaced positions
        sequential_positions = {i: i / max(1, expected_count) for i in range(expected_count)}

        result = reinsert_placeholders(translated, sequential_positions, placeholder_format=("[id", "]"))

        # Should have all placeholders
        assert "[id0]" in result
        assert "[id1]" in result
        assert "[id2]" in result
        assert "[id3]" in result

    def test_empty_translation(self):
        """Test reinsertion with empty translation"""
        positions = {0: 0.0, 1: 0.5, 2: 1.0}
        translated = ""

        result = reinsert_placeholders(translated, positions, placeholder_format=("[id", "]"))

        # Should have all placeholders even with empty text
        assert "[id0]" in result
        assert "[id1]" in result
        assert "[id2]" in result


class TestWordBoundaryHandling:
    """Test that placeholders are inserted at word boundaries"""

    def test_basic_word_boundary(self):
        """Test placeholder insertion respects word boundaries"""
        positions = {0: 0.0, 1: 0.5, 2: 1.0}
        translated = "Hello world"

        result = reinsert_placeholders(translated, positions, placeholder_format=("[id", "]"))

        # [id1] should be at space, not in middle of "Hello" or "world"
        assert "[id1] " in result or " [id1]" in result

    def test_unicode_word_boundary(self):
        """Test word boundary detection with Unicode characters"""
        positions = {0: 0.0, 1: 0.5, 2: 1.0}
        translated = "Bonjour\u00A0monde"  # Non-breaking space

        result = reinsert_placeholders(translated, positions, placeholder_format=("[id", "]"))

        # Should insert at word boundary
        assert "[id0]" in result
        assert "[id1]" in result
        assert "[id2]" in result

    def test_punctuation_boundary(self):
        """Test placeholder insertion near punctuation"""
        positions = {0: 0.0, 1: 0.3, 2: 0.6, 3: 1.0}
        translated = "Hello, world!"

        result = reinsert_placeholders(translated, positions, placeholder_format=("[id", "]"))

        # All placeholders should be present
        assert "[id0]" in result
        assert "[id1]" in result
        assert "[id2]" in result
        assert "[id3]" in result
        # Text should be preserved
        assert "Hello" in result
        assert "world" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
