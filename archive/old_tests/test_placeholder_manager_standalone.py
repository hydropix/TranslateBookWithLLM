"""
Standalone test for simplified PlaceholderManager
"""
from typing import List, Dict


class PlaceholderManager:
    """Simplified PlaceholderManager - only restores global indices."""

    @staticmethod
    def restore_to_global(translated_text: str, global_indices: List[int]) -> str:
        """
        Convert local placeholder indices (0, 1, 2...) to global indices.

        Args:
            translated_text: Text with local placeholders (0, 1, 2...)
            global_indices: List of global indices to restore

        Returns:
            Text with global placeholder indices
        """
        if not global_indices:
            return translated_text

        result = translated_text

        # Renumber from local to global using temp markers to avoid conflicts
        for local_idx in range(len(global_indices)):
            result = result.replace(f"[[{local_idx}]]", f"__RESTORE_{local_idx}__")

        for local_idx, global_idx in enumerate(global_indices):
            result = result.replace(f"__RESTORE_{local_idx}__", f"[[{global_idx}]]")

        return result


# =============================================================================
# TESTS
# =============================================================================

def test_basic_restoration():
    """Test basic local to global restoration"""
    print("\n" + "="*80)
    print("TEST 1: Basic restoration")
    print("="*80)

    chunk_text = "[[0]]Hello [[1]]world[[2]][[3]]"
    global_indices = [5, 6, 7, 8]

    print(f"Chunk text (local): {chunk_text}")
    print(f"Global indices: {global_indices}")

    # Simulate translation
    translated = "[[0]]Bonjour [[1]]monde[[2]][[3]]"
    print(f"Translated (LLM): {translated}")

    # Restore to global
    manager = PlaceholderManager()
    restored = manager.restore_to_global(translated, global_indices)

    print(f"Restored (global): {restored}")

    expected = "[[5]]Bonjour [[6]]monde[[7]][[8]]"
    assert restored == expected, f"Expected '{expected}', got '{restored}'"

    print("\nTest 1 PASSED")


def test_no_placeholders():
    """Test with no placeholders"""
    print("\n" + "="*80)
    print("TEST 2: No placeholders")
    print("="*80)

    text = "Just plain text"
    global_indices = []

    manager = PlaceholderManager()
    restored = manager.restore_to_global(text, global_indices)

    assert restored == text, f"Expected '{text}', got '{restored}'"

    print(f"Input:  {text}")
    print(f"Output: {restored}")
    print("\nTest 2 PASSED")


def test_text_before_placeholder():
    """Test chunk that starts with text (not placeholder)"""
    print("\n" + "="*80)
    print("TEST 3: Chunk starting with text (problematic case)")
    print("="*80)

    # This is the case that FAILED with boundary stripping
    chunk_text = "Hello [[0]]<b>[[1]]world[[2]]</b>[[3]]"
    global_indices = [4, 5, 6, 7]

    print(f"Chunk text (local): {chunk_text}")
    print(f"Global indices: {global_indices}")
    print(f"Note: Chunk starts with 'Hello', NOT with [[0]]")

    translated = "Bonjour [[0]]<b>[[1]]monde[[2]]</b>[[3]]"
    print(f"Translated (LLM): {translated}")

    manager = PlaceholderManager()
    restored = manager.restore_to_global(translated, global_indices)

    print(f"Restored (global): {restored}")

    expected = "Bonjour [[4]]<b>[[5]]monde[[6]]</b>[[7]]"
    assert restored == expected, f"Expected '{expected}', got '{restored}'"

    print("\nTest 3 PASSED - This case previously FAILED with boundary stripping!")


def test_non_sequential_global():
    """Test with non-sequential global indices"""
    print("\n" + "="*80)
    print("TEST 4: Non-sequential global indices")
    print("="*80)

    chunk_text = "[[0]]Text [[1]]here[[2]]"
    global_indices = [10, 25, 30]  # Non-sequential

    print(f"Chunk text (local): {chunk_text}")
    print(f"Global indices: {global_indices}")

    translated = "[[0]]Texte [[1]]ici[[2]]"

    manager = PlaceholderManager()
    restored = manager.restore_to_global(translated, global_indices)

    print(f"Restored (global): {restored}")

    expected = "[[10]]Texte [[25]]ici[[30]]"
    assert restored == expected, f"Expected '{expected}', got '{restored}'"

    print("\nTest 4 PASSED")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("SIMPLIFIED PLACEHOLDER MANAGER TESTS")
    print("="*80)

    try:
        test_basic_restoration()
        test_no_placeholders()
        test_text_before_placeholder()
        test_non_sequential_global()

        print("\n" + "="*80)
        print("ALL TESTS PASSED!")
        print("="*80)
        print("\nThe simplified PlaceholderManager correctly handles:")
        print("  - Basic restoration from local to global indices")
        print("  - Empty chunks (no placeholders)")
        print("  - Chunks starting with text (not placeholders)")
        print("  - Non-sequential global indices")

    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
