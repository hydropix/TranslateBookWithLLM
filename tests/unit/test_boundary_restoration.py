"""
Test boundary tag restoration in fallback scenarios.

This test ensures that when the translation fallback is triggered,
the boundary tags (first and last HTML tags) are correctly restored
to prevent invalid HTML output.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, List

# Import directly to avoid circular imports
import importlib.util
spec = importlib.util.spec_from_file_location(
    "simplified_translator",
    project_root / "src" / "core" / "epub" / "simplified_translator.py"
)
simplified_translator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(simplified_translator)

translate_chunk_with_fallback = simplified_translator.translate_chunk_with_fallback
TranslationStats = simplified_translator.TranslationStats


class MockLLMClient:
    """Mock LLM client that returns None to force fallback"""

    def __init__(self, return_value=None):
        self.return_value = return_value
        self.call_count = 0

    async def send_message(self, *args, **kwargs):
        """Always return None to force fallback"""
        self.call_count += 1
        return self.return_value


@pytest.mark.asyncio
async def test_fallback_preserves_boundaries_with_placeholders():
    """
    Test that fallback restores boundary tags when chunk has internal placeholders.

    Scenario:
    - Chunk has internal content with placeholders: "Hello [[0]]world[[1]]"
    - Boundary tags: <body><p> ... </p></body>
    - LLM returns None (forces fallback)
    - Expected: Original text with boundaries restored
    """
    # Arrange
    chunk_text = "Hello [[0]]world[[1]]"
    local_tag_map = {
        "[[0]]": "<b>",
        "[[1]]": "</b>",
        "__boundary_prefix__": "<body><p>",
        "__boundary_suffix__": "</p></body>"
    }
    global_indices = [5, 6]  # These are global indices for [[0]] and [[1]]

    mock_llm = MockLLMClient(return_value=None)
    stats = TranslationStats()

    # Act
    result = await translate_chunk_with_fallback(
        chunk_text=chunk_text,
        local_tag_map=local_tag_map,
        global_indices=global_indices,
        source_language="English",
        target_language="French",
        model_name="test-model",
        llm_client=mock_llm,
        stats=stats,
        placeholder_format=("[[", "]]")
    )

    # Assert
    assert result.startswith("<body><p>"), f"Expected result to start with boundary prefix, got: {result[:20]}"
    assert result.endswith("</p></body>"), f"Expected result to end with boundary suffix, got: {result[-20:]}"
    assert "Hello" in result, "Expected original text to be preserved"
    assert "[[5]]" in result, "Expected global placeholders to be restored (local [[0]] -> global [[5]])"
    assert "[[6]]" in result, "Expected global placeholders to be restored (local [[1]] -> global [[6]])"
    assert stats.fallback_used == 1, "Expected fallback to be triggered once"


@pytest.mark.asyncio
async def test_fallback_preserves_boundaries_without_placeholders():
    """
    Test boundary restoration when chunk has NO internal placeholders.

    Scenario:
    - Chunk: "Hello world" (no placeholders)
    - Boundary tags: <div> ... </div>
    - LLM returns None (forces fallback)
    - Expected: Original text with boundaries
    """
    # Arrange
    chunk_text = "Hello world"
    local_tag_map = {
        "__boundary_prefix__": "<div>",
        "__boundary_suffix__": "</div>"
    }
    global_indices = []  # No placeholders in this chunk

    mock_llm = MockLLMClient(return_value=None)
    stats = TranslationStats()

    # Act
    result = await translate_chunk_with_fallback(
        chunk_text=chunk_text,
        local_tag_map=local_tag_map,
        global_indices=global_indices,
        source_language="English",
        target_language="Spanish",
        model_name="test-model",
        llm_client=mock_llm,
        stats=stats,
        placeholder_format=("[[", "]]")
    )

    # Assert
    assert result == "<div>Hello world</div>", f"Expected '<div>Hello world</div>', got: {result}"
    assert stats.fallback_used == 1


@pytest.mark.asyncio
async def test_fallback_without_boundaries():
    """
    Test that fallback works correctly when NO boundaries are present.

    This can happen when strip_boundaries=False or when there are < 2 placeholders.
    """
    # Arrange
    chunk_text = "Bonjour [[0]]le monde[[1]]"
    local_tag_map = {
        "[[0]]": "<em>",
        "[[1]]": "</em>"
        # No boundary keys
    }
    global_indices = [10, 11]

    mock_llm = MockLLMClient(return_value=None)
    stats = TranslationStats()

    # Act
    result = await translate_chunk_with_fallback(
        chunk_text=chunk_text,
        local_tag_map=local_tag_map,
        global_indices=global_indices,
        source_language="French",
        target_language="English",
        model_name="test-model",
        llm_client=mock_llm,
        stats=stats,
        placeholder_format=("[[", "]]")
    )

    # Assert
    # Should just restore global indices without boundaries
    assert result == "Bonjour [[10]]le monde[[11]]", f"Expected global indices restored, got: {result}"
    assert not result.startswith("<"), "Should not have boundary prefix"
    assert stats.fallback_used == 1


@pytest.mark.asyncio
async def test_fallback_with_simple_format():
    """
    Test boundary restoration with simple placeholder format [N].
    """
    # Arrange
    chunk_text = "Text with [0]tags[1] inside"
    local_tag_map = {
        "[0]": "<strong>",
        "[1]": "</strong>",
        "__boundary_prefix__": "<section>",
        "__boundary_suffix__": "</section>"
    }
    global_indices = [2, 3]

    mock_llm = MockLLMClient(return_value=None)
    stats = TranslationStats()

    # Act
    result = await translate_chunk_with_fallback(
        chunk_text=chunk_text,
        local_tag_map=local_tag_map,
        global_indices=global_indices,
        source_language="English",
        target_language="German",
        model_name="test-model",
        llm_client=mock_llm,
        stats=stats,
        placeholder_format=("[", "]")
    )

    # Assert
    assert result.startswith("<section>"), f"Expected boundary prefix, got: {result[:20]}"
    assert result.endswith("</section>"), f"Expected boundary suffix, got: {result[-20:]}"
    assert "[2]" in result, "Expected global placeholder [2]"
    assert "[3]" in result, "Expected global placeholder [3]"


@pytest.mark.asyncio
async def test_fallback_with_only_boundary_prefix():
    """
    Test edge case where only boundary_prefix is present.
    """
    # Arrange
    chunk_text = "Content here"
    local_tag_map = {
        "__boundary_prefix__": "<header>",
        # No suffix
    }
    global_indices = []

    mock_llm = MockLLMClient(return_value=None)
    stats = TranslationStats()

    # Act
    result = await translate_chunk_with_fallback(
        chunk_text=chunk_text,
        local_tag_map=local_tag_map,
        global_indices=global_indices,
        source_language="English",
        target_language="Italian",
        model_name="test-model",
        llm_client=mock_llm,
        stats=stats,
        placeholder_format=("[[", "]]")
    )

    # Assert
    assert result == "<header>Content here", f"Expected prefix only, got: {result}"


@pytest.mark.asyncio
async def test_fallback_with_only_boundary_suffix():
    """
    Test edge case where only boundary_suffix is present.
    """
    # Arrange
    chunk_text = "Footer content"
    local_tag_map = {
        "__boundary_suffix__": "</footer>",
        # No prefix
    }
    global_indices = []

    mock_llm = MockLLMClient(return_value=None)
    stats = TranslationStats()

    # Act
    result = await translate_chunk_with_fallback(
        chunk_text=chunk_text,
        local_tag_map=local_tag_map,
        global_indices=global_indices,
        source_language="English",
        target_language="Portuguese",
        model_name="test-model",
        llm_client=mock_llm,
        stats=stats,
        placeholder_format=("[[", "]]")
    )

    # Assert
    assert result == "Footer content</footer>", f"Expected suffix only, got: {result}"


@pytest.mark.asyncio
async def test_boundary_restoration_preserves_html_structure():
    """
    Integration test: Verify that complete HTML structure is preserved.

    This simulates a real-world scenario where a chunk from an EPUB
    contains nested HTML that must remain valid after fallback.
    """
    # Arrange
    chunk_text = "The [[0]]quick brown[[1]] fox [[2]]jumps[[3]] over the lazy dog."
    local_tag_map = {
        "[[0]]": "<em>",
        "[[1]]": "</em>",
        "[[2]]": "<strong>",
        "[[3]]": "</strong>",
        "__boundary_prefix__": "<body><div class='chapter'><p>",
        "__boundary_suffix__": "</p></div></body>"
    }
    global_indices = [100, 101, 102, 103]

    mock_llm = MockLLMClient(return_value=None)
    stats = TranslationStats()

    # Act
    result = await translate_chunk_with_fallback(
        chunk_text=chunk_text,
        local_tag_map=local_tag_map,
        global_indices=global_indices,
        source_language="English",
        target_language="Chinese",
        model_name="test-model",
        llm_client=mock_llm,
        stats=stats,
        placeholder_format=("[[", "]]")
    )

    # Assert - Verify structure integrity
    assert result.startswith("<body><div class='chapter'><p>"), "Expected full boundary prefix"
    assert result.endswith("</p></div></body>"), "Expected full boundary suffix"

    # Verify global placeholders
    assert "[[100]]" in result
    assert "[[101]]" in result
    assert "[[102]]" in result
    assert "[[103]]" in result

    # Verify no local placeholders remain
    assert "[[0]]" not in result, "Local placeholder [[0]] should be converted to global [[100]]"
    assert "[[1]]" not in result
    assert "[[2]]" not in result
    assert "[[3]]" not in result

    # Verify content preserved
    assert "The" in result and "quick brown" in result and "fox" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
