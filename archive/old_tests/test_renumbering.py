"""Test to verify chunk renumbering behavior"""
import re

def test_renumbering_collision():
    """Test that demonstrates the placeholder renumbering issue"""

    # Simulate a chunk with placeholders [[5]], [[6]], [[7]]
    merged_text = "[[5]]Hello [[6]]world [[7]]!"
    global_tag_map = {
        "[[5]]": "<p>",
        "[[6]]": "<b>",
        "[[7]]": "</b></p>"
    }

    # Find all global placeholders in this chunk
    global_placeholders = re.findall(r'\[\[\d+\]\]', merged_text)
    global_placeholders = list(dict.fromkeys(global_placeholders))  # Unique, order preserved

    print(f"Original text: {merged_text}")
    print(f"Global placeholders found: {global_placeholders}")
    print()

    # Current implementation (buggy)
    renumbered_text_buggy = merged_text
    for local_idx, global_placeholder in enumerate(global_placeholders):
        local_placeholder = f"[[{local_idx}]]"
        print(f"Step {local_idx}: Replace {global_placeholder} -> {local_placeholder}")
        renumbered_text_buggy = renumbered_text_buggy.replace(global_placeholder, local_placeholder)
        print(f"  Result: {renumbered_text_buggy}")

    print(f"\nFinal (buggy): {renumbered_text_buggy}")
    print()

    # Fixed implementation using temp markers
    renumbered_text_fixed = merged_text

    # Step 1: Replace with temp markers
    for local_idx, global_placeholder in enumerate(global_placeholders):
        temp_marker = f"__TEMP_{local_idx}__"
        renumbered_text_fixed = renumbered_text_fixed.replace(global_placeholder, temp_marker)

    print(f"After temp markers: {renumbered_text_fixed}")

    # Step 2: Replace temp markers with local placeholders
    for local_idx in range(len(global_placeholders)):
        temp_marker = f"__TEMP_{local_idx}__"
        local_placeholder = f"[[{local_idx}]]"
        renumbered_text_fixed = renumbered_text_fixed.replace(temp_marker, local_placeholder)

    print(f"Final (fixed): {renumbered_text_fixed}")
    print()

    # Test case with potential collision: [[1]], [[10]], [[11]]
    print("=" * 60)
    print("TEST CASE 2: Placeholders with potential collision")
    print("=" * 60)
    merged_text2 = "[[1]]Start [[10]]middle [[11]]end"
    global_placeholders2 = re.findall(r'\[\[\d+\]\]', merged_text2)
    global_placeholders2 = list(dict.fromkeys(global_placeholders2))

    print(f"Original text: {merged_text2}")
    print(f"Global placeholders found: {global_placeholders2}")
    print()

    # Current implementation
    renumbered_buggy2 = merged_text2
    for local_idx, global_placeholder in enumerate(global_placeholders2):
        local_placeholder = f"[[{local_idx}]]"
        print(f"Step {local_idx}: Replace {global_placeholder} -> {local_placeholder}")
        old_text = renumbered_buggy2
        renumbered_buggy2 = renumbered_buggy2.replace(global_placeholder, local_placeholder)
        if old_text == renumbered_buggy2:
            print(f"  ⚠️ NO CHANGE - Already has {local_placeholder}!")
        else:
            print(f"  Result: {renumbered_buggy2}")

    print(f"\nFinal (buggy): {renumbered_buggy2}")
    print(f"❌ PROBLEM: [[1]] stayed as [[1]], but should be [[0]]!")

if __name__ == "__main__":
    test_renumbering_collision()
