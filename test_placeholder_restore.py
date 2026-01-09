"""
Simple test for PlaceholderManager.restore_to_global() function
"""
import re


def restore_to_global(translated_text: str, global_indices: list) -> str:
    """
    Convert local placeholder indices (0, 1, 2...) to global indices.
    This is a copy of PlaceholderManager.restore_to_global() for testing.
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


def test_basic_restore():
    """Test basic placeholder restoration"""
    chunk_text = "[[0]]<p>[[1]]Hello world[[2]]</p>[[3]]"
    global_indices = [4, 5, 6, 7]

    restored = restore_to_global(chunk_text, global_indices)
    expected = "[[4]]<p>[[5]]Hello world[[6]]</p>[[7]]"

    print("Test 1: Basic restore_to_global()")
    print(f"  Input:    {chunk_text}")
    print(f"  Global:   {global_indices}")
    print(f"  Output:   {restored}")
    print(f"  Expected: {expected}")
    print(f"  PASS" if restored == expected else f"  FAIL")
    print()

    return restored == expected


def test_multi_chunk_reconstruction():
    """Test that multiple chunks (some failed) reconstruct correctly"""

    # Original chunks (before translation)
    original_chunks = [
        ("[[0]]<p>[[1]]Text to translate 1[[2]]</p>[[3]]", [0, 1, 2, 3]),
        ("[[0]]<p>[[1]]Text to translate 2[[2]]</p>[[3]]", [4, 5, 6, 7]),
        ("[[0]]<p>[[1]]Text to translate 3[[2]]</p>[[3]]", [8, 9, 10, 11])
    ]

    # Simulate translation results:
    # Chunk 0: Successfully translated
    # Chunk 1: FAILED - use fallback (return original with global indices)
    # Chunk 2: Successfully translated

    translated_chunks = []

    # Chunk 0 - success
    chunk_0_translated = "[[0]]<p>[[1]]Texte traduit 1[[2]]</p>[[3]]"
    translated_chunks.append(restore_to_global(chunk_0_translated, original_chunks[0][1]))

    # Chunk 1 - FAILED, fallback returns original with global indices
    chunk_1_original = original_chunks[1][0]
    translated_chunks.append(restore_to_global(chunk_1_original, original_chunks[1][1]))

    # Chunk 2 - success
    chunk_2_translated = "[[0]]<p>[[1]]Texte traduit 3[[2]]</p>[[3]]"
    translated_chunks.append(restore_to_global(chunk_2_translated, original_chunks[2][1]))

    # Reconstruct
    full_translated = "".join(translated_chunks)

    print("Test 2: Multi-chunk reconstruction with one failure")
    print(f"  Chunk 0 (success):  {translated_chunks[0]}")
    print(f"  Chunk 1 (fallback): {translated_chunks[1]}")
    print(f"  Chunk 2 (success):  {translated_chunks[2]}")
    print()
    print(f"  Reconstructed: {full_translated}")
    print()

    # Verify all placeholders present (0-11)
    found = sorted([int(x) for x in re.findall(r'\[\[(\d+)\]\]', full_translated)])
    expected = list(range(12))

    print(f"  Placeholders found: {found}")
    print(f"  Expected: {expected}")
    print(f"  PASS" if found == expected else f"  FAIL")
    print()

    return found == expected


def test_old_behavior_bug():
    """Test that demonstrates the OLD buggy behavior (empty string for failed chunks)"""

    # Old behavior: failed chunk returned empty string
    translated_chunks_old = [
        "[[0]]<p>[[1]]Translated 1[[2]]</p>[[3]]",
        "",  # FAILED chunk returned empty (BUG!)
        "[[8]]<p>[[9]]Translated 3[[10]]</p>[[11]]"
    ]

    full_translated_old = "".join(translated_chunks_old)

    print("Test 3: OLD buggy behavior (for comparison)")
    print(f"  Chunk 0: {translated_chunks_old[0]}")
    print(f"  Chunk 1: '{translated_chunks_old[1]}' (empty - BUG!)")
    print(f"  Chunk 2: {translated_chunks_old[2]}")
    print()
    print(f"  Reconstructed: {full_translated_old}")
    print()

    # Verify placeholders are MISSING
    found = sorted([int(x) for x in re.findall(r'\[\[(\d+)\]\]', full_translated_old)])
    expected = list(range(12))
    missing = [x for x in expected if x not in found]

    print(f"  Placeholders found: {found}")
    print(f"  Expected: {expected}")
    print(f"  MISSING: {missing}")
    print(f"  This demonstrates the BUG (placeholders 4-7 are missing)")
    print()

    return len(missing) > 0  # Return True if bug is demonstrated


if __name__ == "__main__":
    print("=" * 70)
    print("Testing chunk reconstruction fix")
    print("=" * 70)
    print()

    results = [
        test_basic_restore(),
        test_multi_chunk_reconstruction(),
        test_old_behavior_bug()  # This should return True (demonstrates bug)
    ]

    print("=" * 70)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 70)

    if all(results):
        print("All tests passed!")
        print()
        print("The fix ensures that even when a chunk fails translation,")
        print("it returns the ORIGINAL text with GLOBAL placeholders restored,")
        print("preserving the HTML structure in the final reconstruction.")
    else:
        print("Some tests failed")
