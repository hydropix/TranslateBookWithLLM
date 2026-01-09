"""
Unit tests for placeholder format detection
"""
import pytest
from src.config import detect_placeholder_format_in_text


class TestPlaceholderFormatDetection:
    """Test automatic detection of placeholder format"""

    def test_detect_simple_format(self):
        """Should detect simple format [N]"""
        text = "Hello [0] world [1] test [2]"
        prefix, suffix = detect_placeholder_format_in_text(text)
        assert prefix == "["
        assert suffix == "]"

    def test_detect_safe_format(self):
        """Should detect safe format [[N]]"""
        text = "Hello [[0]] world [[1]] test [[2]]"
        prefix, suffix = detect_placeholder_format_in_text(text)
        assert prefix == "[["
        assert suffix == "]]"

    def test_default_to_safe_when_no_placeholders(self):
        """Should default to safe format when no placeholders found"""
        text = "Hello world with no placeholders"
        prefix, suffix = detect_placeholder_format_in_text(text)
        assert prefix == "[["
        assert suffix == "]]"

    def test_prefer_safe_when_both_present(self):
        """Should use safe format when both formats present (ambiguous)"""
        text = "Hello [0] and also [[1]] mixed"
        prefix, suffix = detect_placeholder_format_in_text(text)
        assert prefix == "[["
        assert suffix == "]]"

    def test_simple_format_not_confused_with_safe(self):
        """Should not confuse [0] inside [[0]] as simple format"""
        text = "Only safe format: [[0]] [[1]] [[2]]"
        prefix, suffix = detect_placeholder_format_in_text(text)
        assert prefix == "[["
        assert suffix == "]]"

    def test_with_real_translation_text(self):
        """Test with realistic translation content"""
        text_simple = "Laura [0]Laura regardait[1] par la fenêtre."
        prefix, suffix = detect_placeholder_format_in_text(text_simple)
        assert prefix == "["
        assert suffix == "]"

        text_safe = "Laura [[0]]Laura regardait[[1]] par la fenêtre."
        prefix, suffix = detect_placeholder_format_in_text(text_safe)
        assert prefix == "[["
        assert suffix == "]]"

    def test_edge_cases(self):
        """Test edge cases"""
        # Empty string
        prefix, suffix = detect_placeholder_format_in_text("")
        assert prefix == "[["
        assert suffix == "]]"

        # Only brackets
        prefix, suffix = detect_placeholder_format_in_text("[]")
        assert prefix == "[["
        assert suffix == "]]"

        # Malformed placeholders
        prefix, suffix = detect_placeholder_format_in_text("[0 missing bracket")
        assert prefix == "[["
        assert suffix == "]]"
