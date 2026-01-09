"""
Test to verify chunk reconstruction bug where empty chunks lose placeholders
"""

def test_chunk_reconstruction():
    """Simulate the bug where a failed chunk returns empty string"""

    # Simulate 3 chunks from a single HTML file
    # Each chunk has placeholders with global indices

    # Chunk 0: Successfully translated
    chunk_0 = "[[0]]<p>[[1]]Translated text 1[[2]]</p>[[3]]"

    # Chunk 1: FAILED - returns empty (this is the bug!)
    chunk_1 = ""  # Should have been "[[4]]<p>[[5]]Translated text 2[[6]]</p>[[7]]"

    # Chunk 2: Successfully translated
    chunk_2 = "[[8]]<p>[[9]]Translated text 3[[10]]</p>[[11]]"

    # Current reconstruction logic (simplified_translator.py:622)
    translated_chunks = [chunk_0, chunk_1, chunk_2]
    full_translated = "".join(translated_chunks)

    print("Reconstructed text:")
    print(full_translated)
    print()

    # Expected placeholders: [[0]] through [[11]]
    # Actual placeholders: [[0]], [[1]], [[2]], [[3]], [[8]], [[9]], [[10]], [[11]]
    # MISSING: [[4]], [[5]], [[6]], [[7]]

    import re
    found_placeholders = re.findall(r'\[\[(\d+)\]\]', full_translated)
    print(f"Found placeholders: {found_placeholders}")
    print(f"Expected 12 placeholders (0-11), found {len(found_placeholders)}")
    print()

    # When tag restoration happens, placeholders [[4]]-[[7]] are missing
    # This causes the HTML structure to break!

    # The fix: when a chunk fails, we should return the ORIGINAL chunk text
    # with its placeholders intact, not an empty string

if __name__ == "__main__":
    test_chunk_reconstruction()
