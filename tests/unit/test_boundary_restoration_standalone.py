"""
Standalone test for boundary tag restoration logic.

This test validates the boundary restoration logic without relying on
external imports to avoid circular dependency issues.
"""

import pytest
import re


def detect_placeholder_format_in_text(text: str) -> tuple:
    """Detect placeholder format from text."""
    if re.search(r'\[\[\d+\]\]', text):
        return ("[[", "]]")
    elif re.search(r'(?<!\[)\[\d+\](?!\])', text):
        return ("[", "]")
    else:
        return ("[[", "]]")  # Default


def restore_to_global(translated_text: str, global_indices: list) -> str:
    """Convert local placeholder indices to global indices."""
    if not global_indices:
        return translated_text

    result = translated_text
    prefix, suffix = detect_placeholder_format_in_text(result)

    # Renumber from local to global using temp markers
    for local_idx in range(len(global_indices)):
        local_ph = f"{prefix}{local_idx}{suffix}"
        if local_ph in result:
            result = result.replace(local_ph, f"__RESTORE_{local_idx}__")

    for local_idx, global_idx in enumerate(global_indices):
        result = result.replace(f"__RESTORE_{local_idx}__", f"{prefix}{global_idx}{suffix}")

    return result


def apply_boundary_restoration(chunk_text: str, global_indices: list, local_tag_map: dict) -> str:
    """
    Apply the boundary restoration logic from Phase 3 fallback.

    This replicates the exact logic from simplified_translator.py lines 482-492.
    """
    # Restore global indices for internal placeholders
    result_with_globals = restore_to_global(chunk_text, global_indices)

    # Restore boundary tags if present
    boundary_prefix = local_tag_map.get("__boundary_prefix__", "")
    boundary_suffix = local_tag_map.get("__boundary_suffix__", "")

    if boundary_prefix or boundary_suffix:
        result_with_globals = boundary_prefix + result_with_globals + boundary_suffix

    return result_with_globals


class TestBoundaryRestoration:
    """Test suite for boundary tag restoration in fallback scenarios."""

    def test_with_internal_placeholders_and_boundaries(self):
        """Test restoration with both internal placeholders and boundaries."""
        chunk_text = "Hello [[0]]world[[1]]"
        local_tag_map = {
            "[[0]]": "<b>",
            "[[1]]": "</b>",
            "__boundary_prefix__": "<body><p>",
            "__boundary_suffix__": "</p></body>"
        }
        global_indices = [5, 6]

        result = apply_boundary_restoration(chunk_text, global_indices, local_tag_map)

        assert result.startswith("<body><p>"), f"Missing boundary prefix in: {result[:30]}"
        assert result.endswith("</p></body>"), f"Missing boundary suffix in: {result[-30:]}"
        assert "[[5]]" in result, f"Missing [[5]] in: {result}"
        assert "[[6]]" in result, f"Missing [[6]] in: {result}"
        assert result == "<body><p>Hello [[5]]world[[6]]</p></body>"

    def test_without_internal_placeholders(self):
        """Test restoration with boundaries but no internal placeholders."""
        chunk_text = "Hello world"
        local_tag_map = {
            "__boundary_prefix__": "<div>",
            "__boundary_suffix__": "</div>"
        }
        global_indices = []

        result = apply_boundary_restoration(chunk_text, global_indices, local_tag_map)

        assert result == "<div>Hello world</div>"

    def test_no_boundaries(self):
        """Test when no boundaries are present (only internal placeholders)."""
        chunk_text = "Bonjour [[0]]monde[[1]]"
        local_tag_map = {
            "[[0]]": "<em>",
            "[[1]]": "</em>"
        }
        global_indices = [10, 11]

        result = apply_boundary_restoration(chunk_text, global_indices, local_tag_map)

        assert result == "Bonjour [[10]]monde[[11]]"
        assert not result.startswith("<")

    def test_simple_format_with_boundaries(self):
        """Test with simple placeholder format [N]."""
        chunk_text = "Text with [0]tags[1]"
        local_tag_map = {
            "[0]": "<strong>",
            "[1]": "</strong>",
            "__boundary_prefix__": "<section>",
            "__boundary_suffix__": "</section>"
        }
        global_indices = [2, 3]

        result = apply_boundary_restoration(chunk_text, global_indices, local_tag_map)

        assert result.startswith("<section>")
        assert result.endswith("</section>")
        assert "[2]" in result
        assert "[3]" in result
        assert result == "<section>Text with [2]tags[3]</section>"

    def test_only_prefix(self):
        """Test with only boundary prefix."""
        chunk_text = "Content"
        local_tag_map = {
            "__boundary_prefix__": "<header>"
        }
        global_indices = []

        result = apply_boundary_restoration(chunk_text, global_indices, local_tag_map)

        assert result == "<header>Content"

    def test_only_suffix(self):
        """Test with only boundary suffix."""
        chunk_text = "Footer"
        local_tag_map = {
            "__boundary_suffix__": "</footer>"
        }
        global_indices = []

        result = apply_boundary_restoration(chunk_text, global_indices, local_tag_map)

        assert result == "Footer</footer>"

    def test_complex_html_structure(self):
        """Test with complex nested HTML boundaries."""
        chunk_text = "The [[0]]quick[[1]] fox [[2]]jumps[[3]]."
        local_tag_map = {
            "[[0]]": "<em>",
            "[[1]]": "</em>",
            "[[2]]": "<strong>",
            "[[3]]": "</strong>",
            "__boundary_prefix__": "<body><div class='chapter'><p>",
            "__boundary_suffix__": "</p></div></body>"
        }
        global_indices = [100, 101, 102, 103]

        result = apply_boundary_restoration(chunk_text, global_indices, local_tag_map)

        # Verify structure
        assert result.startswith("<body><div class='chapter'><p>")
        assert result.endswith("</p></div></body>")

        # Verify global placeholders
        for idx in [100, 101, 102, 103]:
            assert f"[[{idx}]]" in result, f"Missing [[{idx}]] in result"

        # Verify no local placeholders remain
        for idx in [0, 1, 2, 3]:
            assert f"[[{idx}]]" not in result, f"Local [[{idx}]] should be converted to global"

    def test_empty_boundaries(self):
        """Test with empty string boundaries (should not add them)."""
        chunk_text = "Plain text"
        local_tag_map = {
            "__boundary_prefix__": "",
            "__boundary_suffix__": ""
        }
        global_indices = []

        result = apply_boundary_restoration(chunk_text, global_indices, local_tag_map)

        assert result == "Plain text"

    def test_multiple_placeholders_renumbering(self):
        """Test correct renumbering of multiple placeholders."""
        chunk_text = "A[[0]]B[[1]]C[[2]]D[[3]]E"
        local_tag_map = {
            "[[0]]": "<i>",
            "[[1]]": "</i>",
            "[[2]]": "<u>",
            "[[3]]": "</u>",
            "__boundary_prefix__": "<p>",
            "__boundary_suffix__": "</p>"
        }
        global_indices = [50, 51, 52, 53]

        result = apply_boundary_restoration(chunk_text, global_indices, local_tag_map)

        expected = "<p>A[[50]]B[[51]]C[[52]]D[[53]]E</p>"
        assert result == expected, f"Expected: {expected}, Got: {result}"

    def test_preservation_of_text_content(self):
        """Ensure text content is preserved exactly."""
        original_content = "This is important text with special chars: <>&\"'"
        chunk_text = f"{original_content}"
        local_tag_map = {
            "__boundary_prefix__": "<div>",
            "__boundary_suffix__": "</div>"
        }
        global_indices = []

        result = apply_boundary_restoration(chunk_text, global_indices, local_tag_map)

        # Text should be preserved exactly between boundaries
        assert original_content in result
        assert result == f"<div>{original_content}</div>"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
