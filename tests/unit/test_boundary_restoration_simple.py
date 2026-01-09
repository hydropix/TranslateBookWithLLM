"""
Test boundary tag restoration logic in isolation.

This test focuses on the boundary restoration logic without importing
the full translation pipeline to avoid circular dependencies.
"""

import pytest


def restore_with_boundaries(chunk_text: str, global_indices: list, local_tag_map: dict, placeholder_format: tuple) -> str:
    """
    Simplified version of the fallback logic to test boundary restoration.

    This replicates the logic from translate_chunk_with_fallback() Phase 3.
    """
    from src.core.epub.placeholder_manager import PlaceholderManager

    placeholder_mgr = PlaceholderManager()

    # Restore global indices for internal placeholders
    result_with_globals = placeholder_mgr.restore_to_global(chunk_text, global_indices)

    # Restore boundary tags if present
    boundary_prefix = local_tag_map.get("__boundary_prefix__", "")
    boundary_suffix = local_tag_map.get("__boundary_suffix__", "")

    if boundary_prefix or boundary_suffix:
        result_with_globals = boundary_prefix + result_with_globals + boundary_suffix

    return result_with_globals


def test_boundary_restoration_with_placeholders():
    """Test boundary restoration with internal placeholders."""
    chunk_text = "Hello [[0]]world[[1]]"
    local_tag_map = {
        "[[0]]": "<b>",
        "[[1]]": "</b>",
        "__boundary_prefix__": "<body><p>",
        "__boundary_suffix__": "</p></body>"
    }
    global_indices = [5, 6]

    result = restore_with_boundaries(chunk_text, global_indices, local_tag_map, ("[[", "]]"))

    assert result.startswith("<body><p>"), f"Expected boundary prefix, got: {result[:20]}"
    assert result.endswith("</p></body>"), f"Expected boundary suffix, got: {result[-20:]}"
    assert "[[5]]" in result, "Expected global placeholder [[5]]"
    assert "[[6]]" in result, "Expected global placeholder [[6]]"


def test_boundary_restoration_without_placeholders():
    """Test boundary restoration without internal placeholders."""
    chunk_text = "Hello world"
    local_tag_map = {
        "__boundary_prefix__": "<div>",
        "__boundary_suffix__": "</div>"
    }
    global_indices = []

    result = restore_with_boundaries(chunk_text, global_indices, local_tag_map, ("[[", "]]"))

    assert result == "<div>Hello world</div>", f"Expected '<div>Hello world</div>', got: {result}"


def test_no_boundaries():
    """Test when no boundaries are present."""
    chunk_text = "Bonjour [[0]]monde[[1]]"
    local_tag_map = {
        "[[0]]": "<em>",
        "[[1]]": "</em>"
    }
    global_indices = [10, 11]

    result = restore_with_boundaries(chunk_text, global_indices, local_tag_map, ("[[", "]]"))

    assert result == "Bonjour [[10]]monde[[11]]", f"Expected global indices only, got: {result}"
    assert not result.startswith("<"), "Should not have boundary prefix"


def test_simple_format_boundaries():
    """Test with simple placeholder format [N]."""
    chunk_text = "Text with [0]tags[1]"
    local_tag_map = {
        "[0]": "<strong>",
        "[1]": "</strong>",
        "__boundary_prefix__": "<section>",
        "__boundary_suffix__": "</section>"
    }
    global_indices = [2, 3]

    result = restore_with_boundaries(chunk_text, global_indices, local_tag_map, ("[", "]"))

    assert result.startswith("<section>"), f"Got: {result[:20]}"
    assert result.endswith("</section>"), f"Got: {result[-20:]}"
    assert "[2]" in result
    assert "[3]" in result


def test_only_prefix():
    """Test with only boundary prefix."""
    chunk_text = "Content"
    local_tag_map = {
        "__boundary_prefix__": "<header>"
    }
    global_indices = []

    result = restore_with_boundaries(chunk_text, global_indices, local_tag_map, ("[[", "]]"))

    assert result == "<header>Content", f"Expected '<header>Content', got: {result}"


def test_only_suffix():
    """Test with only boundary suffix."""
    chunk_text = "Footer"
    local_tag_map = {
        "__boundary_suffix__": "</footer>"
    }
    global_indices = []

    result = restore_with_boundaries(chunk_text, global_indices, local_tag_map, ("[[", "]]"))

    assert result == "Footer</footer>", f"Expected 'Footer</footer>', got: {result}"


def test_complex_html_structure():
    """Test with complex nested HTML structure."""
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

    result = restore_with_boundaries(chunk_text, global_indices, local_tag_map, ("[[", "]]"))

    # Verify structure
    assert result.startswith("<body><div class='chapter'><p>")
    assert result.endswith("</p></div></body>")

    # Verify global placeholders
    assert "[[100]]" in result
    assert "[[101]]" in result
    assert "[[102]]" in result
    assert "[[103]]" in result

    # Verify no local placeholders
    assert "[[0]]" not in result
    assert "[[1]]" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
