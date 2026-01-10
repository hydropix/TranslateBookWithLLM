"""
Unit tests for token alignment fallback system.

Tests the Phase 2 fallback mechanism that reinserts HTML placeholders
when the LLM fails to preserve them correctly.
"""
import pytest
import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent.parent / 'src'
sys.path.insert(0, str(src_path))

from src.core.epub.token_alignment_fallback import TokenAlignmentFallback


class TestTokenAlignmentFallback:
    """Test token alignment placeholder reinsertion."""

    @pytest.fixture
    def aligner(self):
        """Create aligner instance for tests."""
        return TokenAlignmentFallback()

    def test_simple_alignment_en_to_fr(self, aligner):
        """Test basic English to French alignment."""
        original = "[id0]Hello[id1] world[id2]"
        translated = "Bonjour monde"
        placeholders = ["[id0]", "[id1]", "[id2]"]

        result = aligner.align_and_insert_placeholders(
            original, translated, placeholders
        )

        # Should contain all placeholders in order
        assert "[id0]" in result
        assert "[id1]" in result
        assert "[id2]" in result
        assert result.index("[id0]") < result.index("[id1]") < result.index("[id2]")

        # Should preserve translated text
        clean = result.replace("[id0]", "").replace("[id1]", "").replace("[id2]", "")
        assert "Bonjour" in clean
        assert "monde" in clean

    def test_simple_alignment_en_to_zh(self, aligner):
        """Test English to Chinese alignment (no spaces)."""
        original = "[id0]Hello[id1] world[id2]"
        translated = "你好世界"
        placeholders = ["[id0]", "[id1]", "[id2]"]

        result = aligner.align_and_insert_placeholders(
            original, translated, placeholders
        )

        # Should contain all placeholders exactly once
        assert result.count("[id0]") == 1
        assert result.count("[id1]") == 1
        assert result.count("[id2]") == 1

    def test_order_preservation(self, aligner):
        """Verify placeholders always appear in sequential order."""
        original = "[id0]First[id1] second[id2] third[id3]"
        translated = "Premier deuxième troisième"
        placeholders = ["[id0]", "[id1]", "[id2]", "[id3]"]

        result = aligner.align_and_insert_placeholders(
            original, translated, placeholders
        )

        # Extract positions
        positions = [result.index(ph) for ph in placeholders]

        # Should be strictly increasing
        assert positions == sorted(positions)

    def test_no_duplicates(self, aligner):
        """Verify no placeholder appears more than once."""
        original = "[id0]Text[id1] here[id2]"
        translated = "Texte ici"
        placeholders = ["[id0]", "[id1]", "[id2]"]

        result = aligner.align_and_insert_placeholders(
            original, translated, placeholders
        )

        # Each placeholder should appear exactly once
        for ph in placeholders:
            assert result.count(ph) == 1

    def test_all_placeholders_present(self, aligner):
        """Verify all input placeholders are in output."""
        original = "[id0]A[id1]B[id2]C[id3]D[id4]E[id5]"
        translated = "ABCDE"
        placeholders = ["[id0]", "[id1]", "[id2]", "[id3]", "[id4]", "[id5]"]

        result = aligner.align_and_insert_placeholders(
            original, translated, placeholders
        )

        # All placeholders must be present
        for ph in placeholders:
            assert ph in result

    def test_long_text_alignment(self, aligner):
        """Test with realistic longer text (50+ tokens)."""
        original = (
            "[id0]Laura stared out the window[id1] as the train rumbled through "
            "the countryside[id2]. The landscape blurred past[id3], a watercolor "
            "of greens and browns[id4]."
        )
        translated = (
            "Laura regardait par la fenêtre pendant que le train traversait la "
            "campagne. Le paysage défilait, une aquarelle de verts et de bruns."
        )
        placeholders = ["[id0]", "[id1]", "[id2]", "[id3]", "[id4]"]

        result = aligner.align_and_insert_placeholders(
            original, translated, placeholders
        )

        # All placeholders present
        for ph in placeholders:
            assert ph in result

        # Sequential order
        positions = [result.index(ph) for ph in placeholders]
        assert positions == sorted(positions)

    def test_edge_case_empty_translation(self, aligner):
        """Handle edge case where translation is empty."""
        original = "[id0]Text[id1]"
        translated = ""
        placeholders = ["[id0]", "[id1]"]

        result = aligner.align_and_insert_placeholders(
            original, translated, placeholders
        )

        # Should still have placeholders
        assert "[id0]" in result
        assert "[id1]" in result

    def test_edge_case_single_word(self, aligner):
        """Handle edge case where translation is single word."""
        original = "[id0]Hello[id1]"
        translated = "Bonjour"
        placeholders = ["[id0]", "[id1]"]

        result = aligner.align_and_insert_placeholders(
            original, translated, placeholders
        )

        # Likely: "[id0]Bonjour[id1]"
        assert result.startswith("[id0]")
        assert result.endswith("[id1]")

    def test_validation_with_validator(self, aligner):
        """Verify result passes strict validation."""
        from src.core.epub.placeholder_validator import PlaceholderValidator

        original = "[id0]Hello[id1] world[id2]"
        translated = "Bonjour monde"
        placeholders = ["[id0]", "[id1]", "[id2]"]

        result = aligner.align_and_insert_placeholders(
            original, translated, placeholders
        )

        # Create tag map for validation
        tag_map = {ph: f"<tag{i}>" for i, ph in enumerate(placeholders)}

        # Should pass strict validation
        is_valid, error_msg = PlaceholderValidator.validate_strict(result, tag_map)
        assert is_valid, f"Validation failed: {error_msg}"

    def test_multiple_placeholders_same_position(self, aligner):
        """Test placeholders at boundaries (start/end of words)."""
        original = "[id0][id1]Hello[id2][id3]"
        translated = "Bonjour"
        placeholders = ["[id0]", "[id1]", "[id2]", "[id3]"]

        result = aligner.align_and_insert_placeholders(
            original, translated, placeholders
        )

        # All must be present in order
        for ph in placeholders:
            assert ph in result

        positions = [result.index(ph) for ph in placeholders]
        assert positions == sorted(positions)

    def test_punctuation_handling(self, aligner):
        """Test handling of punctuation marks."""
        original = "[id0]Hello[id1],[id2] world[id3]!"
        translated = "Bonjour, monde!"
        placeholders = ["[id0]", "[id1]", "[id2]", "[id3]"]

        result = aligner.align_and_insert_placeholders(
            original, translated, placeholders
        )

        # All placeholders present
        for ph in placeholders:
            assert ph in result

        # Sequential order
        positions = [result.index(ph) for ph in placeholders]
        assert positions == sorted(positions)

    def test_numbers_and_special_chars(self, aligner):
        """Test with numbers and special characters."""
        original = "[id0]Version 1.2.3[id1] - updated[id2]"
        translated = "Version 1.2.3 - mis à jour"
        placeholders = ["[id0]", "[id1]", "[id2]"]

        result = aligner.align_and_insert_placeholders(
            original, translated, placeholders
        )

        # All placeholders present and ordered
        for ph in placeholders:
            assert ph in result

        positions = [result.index(ph) for ph in placeholders]
        assert positions == sorted(positions)

    def test_cjk_punctuation(self, aligner):
        """Test with Chinese/Japanese punctuation."""
        original = "[id0]Hello[id1]world[id2]"
        translated = "你好\u3001世界\u3002"  # Chinese punctuation
        placeholders = ["[id0]", "[id1]", "[id2]"]

        result = aligner.align_and_insert_placeholders(
            original, translated, placeholders
        )

        # All placeholders present
        for ph in placeholders:
            assert ph in result

        # Sequential order
        positions = [result.index(ph) for ph in placeholders]
        assert positions == sorted(positions)

    def test_mixed_language_text(self, aligner):
        """Test with mixed language text (code, URLs)."""
        original = "[id0]Check out https://example.com[id1] for more[id2]"
        translated = "Visitez https://example.com pour en savoir plus"
        placeholders = ["[id0]", "[id1]", "[id2]"]

        result = aligner.align_and_insert_placeholders(
            original, translated, placeholders
        )

        # All placeholders present
        for ph in placeholders:
            assert ph in result

    def test_very_short_text(self, aligner):
        """Test with very short text."""
        original = "[id0]Hi[id1]"
        translated = "Salut"
        placeholders = ["[id0]", "[id1]"]

        result = aligner.align_and_insert_placeholders(
            original, translated, placeholders
        )

        # Both placeholders present
        assert "[id0]" in result
        assert "[id1]" in result

    def test_translation_expansion(self, aligner):
        """Test when translation is much longer than original."""
        original = "[id0]OK[id1]"
        translated = "D'accord, c'est parfait"
        placeholders = ["[id0]", "[id1]"]

        result = aligner.align_and_insert_placeholders(
            original, translated, placeholders
        )

        # Both placeholders present and ordered
        assert "[id0]" in result
        assert "[id1]" in result
        assert result.index("[id0]") < result.index("[id1]")

    def test_translation_compression(self, aligner):
        """Test when translation is much shorter than original."""
        original = "[id0]This is a very long sentence with many words[id1]"
        translated = "Court"
        placeholders = ["[id0]", "[id1]"]

        result = aligner.align_and_insert_placeholders(
            original, translated, placeholders
        )

        # Both placeholders present
        assert "[id0]" in result
        assert "[id1]" in result

    def test_no_placeholders(self, aligner):
        """Test with no placeholders (edge case)."""
        original = "Hello world"
        translated = "Bonjour monde"
        placeholders = []

        result = aligner.align_and_insert_placeholders(
            original, translated, placeholders
        )

        # Should return translated text as-is
        assert result == translated

    def test_single_placeholder(self, aligner):
        """Test with single placeholder."""
        original = "[id0]Hello"
        translated = "Bonjour"
        placeholders = ["[id0]"]

        result = aligner.align_and_insert_placeholders(
            original, translated, placeholders
        )

        # Single placeholder at start
        assert result.startswith("[id0]")
        assert "Bonjour" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
