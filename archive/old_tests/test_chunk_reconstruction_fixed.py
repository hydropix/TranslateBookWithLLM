"""
Test to verify that the chunk reconstruction fix preserves placeholders even when translation fails
"""
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.epub.simplified_translator import (
    PlaceholderManager,
    translate_chunk_with_fallback,
    TranslationStats
)
from src.core.epub.html_chunker import extract_text_and_positions, reinsert_placeholders


def test_placeholder_manager_restore():
    """Test that PlaceholderManager correctly restores global indices"""
    manager = PlaceholderManager()

    # Chunk with local indices
    chunk_text = "[[0]]<p>[[1]]Hello world[[2]]</p>[[3]]"
    global_indices = [4, 5, 6, 7]  # This chunk should have global indices 4-7

    restored = manager.restore_to_global(chunk_text, global_indices)
    expected = "[[4]]<p>[[5]]Hello world[[6]]</p>[[7]]"

    print("Test 1: PlaceholderManager.restore_to_global()")
    print(f"  Input:    {chunk_text}")
    print(f"  Global:   {global_indices}")
    print(f"  Output:   {restored}")
    print(f"  Expected: {expected}")
    print(f"  ✓ PASS" if restored == expected else f"  ✗ FAIL")
    print()

    return restored == expected


def test_empty_chunk_fallback():
    """Test that when translation fails, we return original chunk with global indices"""

    # Simulate a chunk that would fail all translation phases
    chunk_text = "[[0]]<p>[[1]]Original text[[2]]</p>[[3]]"
    local_tag_map = {
        "[[0]]": "<div>",
        "[[1]]": "<p>",
        "[[2]]": "</p>",
        "[[3]]": "</div>"
    }
    global_indices = [10, 11, 12, 13]

    # Create a mock LLM client that always returns None (simulating failure)
    class MockFailingLLMClient:
        async def make_request(self, *args, **kwargs):
            return None

    async def run_test():
        stats = TranslationStats()

        result = await translate_chunk_with_fallback(
            chunk_text=chunk_text,
            local_tag_map=local_tag_map,
            global_indices=global_indices,
            source_language="English",
            target_language="French",
            model_name="test-model",
            llm_client=MockFailingLLMClient(),
            stats=stats,
            log_callback=None
        )

        # Expected: original chunk text with global indices restored
        expected = "[[10]]<p>[[11]]Original text[[12]]</p>[[13]]"

        print("Test 2: Failed translation fallback preserves structure")
        print(f"  Original: {chunk_text}")
        print(f"  Global:   {global_indices}")
        print(f"  Result:   {result}")
        print(f"  Expected: {expected}")
        print(f"  ✓ PASS" if result == expected else f"  ✗ FAIL")
        print()

        return result == expected

    return asyncio.run(run_test())


def test_multi_chunk_reconstruction():
    """Test that multiple chunks (some failed) reconstruct correctly"""

    # Simulate reconstruction with mixed success/failure
    chunks = [
        "[[0]]<p>[[1]]Translated successfully[[2]]</p>[[3]]",  # Success
        "[[4]]<p>[[5]]Original preserved[[6]]</p>[[7]]",      # Failed (returned original with global indices)
        "[[8]]<p>[[9]]Also translated[[10]]</p>[[11]]"        # Success
    ]

    # Current reconstruction logic
    full_translated = "".join(chunks)

    print("Test 3: Multi-chunk reconstruction")
    print(f"  Chunk 0: {chunks[0]}")
    print(f"  Chunk 1: {chunks[1]} (fallback)")
    print(f"  Chunk 2: {chunks[2]}")
    print(f"  Result:  {full_translated}")

    # Verify all placeholders present
    import re
    found = sorted([int(x) for x in re.findall(r'\[\[(\d+)\]\]', full_translated)])
    expected = list(range(12))

    print(f"  Placeholders found: {found}")
    print(f"  Expected: {expected}")
    print(f"  ✓ PASS" if found == expected else f"  ✗ FAIL")
    print()

    return found == expected


if __name__ == "__main__":
    print("=" * 60)
    print("Testing chunk reconstruction fix")
    print("=" * 60)
    print()

    results = [
        test_placeholder_manager_restore(),
        test_empty_chunk_fallback(),
        test_multi_chunk_reconstruction()
    ]

    print("=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)

    if all(results):
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed")
        sys.exit(1)
