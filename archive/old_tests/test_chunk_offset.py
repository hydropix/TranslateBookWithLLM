"""Test chunk creation with global offset"""
import re

def test_chunk_creation_with_offset():
    """Test that simulates chunk creation for file 2 (with offset)"""

    # Simulate File 2, Chunk 1
    # The TagPreserver for file 2 created placeholders [[10]], [[11]], [[12]]
    # This chunk should be sent to LLM with local indices [[0]], [[1]], [[2]]

    merged_text = "[[10]]Hello [[11]]world [[12]]!"
    global_tag_map = {
        "[[10]]": "<p>",
        "[[11]]": "<b>",
        "[[12]]": "</b></p>"
    }

    # This is chunk 1 of file 2, which had 10 placeholders in file 1
    global_offset = 10

    print("=" * 60)
    print("SCENARIO: File 2, Chunk 1")
    print("=" * 60)
    print(f"Merged text (from segments): {merged_text}")
    print(f"Global offset: {global_offset}")
    print()

    # Current implementation in _create_chunk()
    global_placeholders = re.findall(r'\[\[\d+\]\]', merged_text)
    global_placeholders = list(dict.fromkeys(global_placeholders))

    print(f"Global placeholders found: {global_placeholders}")
    print()

    # Create local mapping
    local_tag_map = {}
    global_indices = []
    renumbered_text = merged_text

    print("Renumbering process:")
    for local_idx, global_placeholder in enumerate(global_placeholders):
        local_placeholder = f"[[{local_idx}]]"
        local_tag_map[local_placeholder] = global_tag_map.get(global_placeholder, "")

        # Extract global index
        global_idx = int(global_placeholder[2:-2])
        global_indices.append(global_idx)

        print(f"  {global_placeholder} -> {local_placeholder} (global_idx={global_idx})")

        # Renumber in text
        renumbered_text = renumbered_text.replace(global_placeholder, local_placeholder)

    print()
    print(f"Text sent to LLM: {renumbered_text}")
    print(f"Global indices stored: {global_indices}")
    print()

    # Check if this is correct
    if renumbered_text == "[[0]]Hello [[1]]world [[2]]!":
        print("✅ SUCCESS: Text sent to LLM has local indices (0, 1, 2)")
    else:
        print(f"❌ FAIL: Text sent to LLM should be '[[0]]Hello [[1]]world [[2]]!'")
        print(f"         but got: '{renumbered_text}'")

    print()
    print("=" * 60)
    print("After translation, restoring global indices:")
    print("=" * 60)

    # Simulate LLM translation
    translated_text = "[[0]]Bonjour [[1]]monde [[2]]!"
    print(f"Translated (from LLM): {translated_text}")

    # Restore global indices
    result = translated_text
    for local_idx in range(len(global_indices) - 1, -1, -1):
        global_idx = global_indices[local_idx]
        result = result.replace(f"[[{local_idx}]]", f"[[{global_idx}]]")

    print(f"After restoring global indices: {result}")

    if result == "[[10]]Bonjour [[11]]monde [[12]]!":
        print("✅ SUCCESS: Global indices correctly restored")
    else:
        print(f"❌ FAIL: Should be '[[10]]Bonjour [[11]]monde [[12]]!'")
        print(f"         but got: '{result}'")

if __name__ == "__main__":
    test_chunk_creation_with_offset()
