"""Test to verify the simple format placeholder bug fix"""
import re

def test_simple_format_detection():
    """Test that we can detect and renumber simple format placeholders"""

    # Simulate text with SIMPLE format placeholders [0], [1], [2]
    # (This is what TagPreserver creates when text has no brackets)
    merged_text = "Breaking Laura[0]Laura watched the taxi[1]She shook her head[2]"

    print("=" * 70)
    print("TEST: Simple format placeholder detection and renumbering")
    print("=" * 70)
    print(f"Input text: {merged_text}")
    print()

    # OLD BUGGY CODE (hardcoded for [[N]])
    print("OLD CODE (BUGGY - hardcoded for [[N]]):")
    old_pattern = r'\[\[\d+\]\]'
    old_placeholders = re.findall(old_pattern, merged_text)
    print(f"  Pattern: {old_pattern}")
    print(f"  Found: {old_placeholders}")
    print(f"  Result: FAIL - Found {len(old_placeholders)} placeholders (expected 3)")
    print()

    # NEW FIXED CODE (adaptive detection)
    print("NEW CODE (FIXED - adaptive detection):")

    # Detect placeholder format
    has_simple = bool(re.search(r'(?<!\[)\[\d+\](?!\])', merged_text))
    has_safe = bool(re.search(r'\[\[\d+\]\]', merged_text))

    print(f"  has_simple: {has_simple}")
    print(f"  has_safe: {has_safe}")

    if has_simple and not has_safe:
        placeholder_pattern = r'(?<!\[)\[(\d+)\](?!\])'
        prefix = "["
        suffix = "]"
        format_name = "SIMPLE [N]"
    else:
        placeholder_pattern = r'\[\[(\d+)\]\]'
        prefix = "[["
        suffix = "]]"
        format_name = "SAFE [[N]]"

    print(f"  Detected format: {format_name}")
    print(f"  Pattern: {placeholder_pattern}")

    # Find placeholders
    global_placeholder_numbers = re.findall(placeholder_pattern, merged_text)
    global_placeholders = [f"{prefix}{num}{suffix}" for num in global_placeholder_numbers]

    print(f"  Found: {global_placeholders}")
    print(f"  Count: {len(global_placeholders)}")

    # Renumber to local indices (0, 1, 2)
    renumbered_text = merged_text
    for local_idx, global_placeholder in enumerate(global_placeholders):
        local_placeholder = f"{prefix}{local_idx}{suffix}"
        renumbered_text = renumbered_text.replace(global_placeholder, local_placeholder)

    print(f"  Renumbered: {renumbered_text}")

    # Check result
    expected = "Breaking Laura[0]Laura watched the taxi[1]She shook her head[2]"
    if renumbered_text == expected:
        print(f"  Result: SUCCESS - Text unchanged (already local indices)")
    else:
        print(f"  Result: CHANGED")
    print()

    # Test with higher indices (simulating chunk 2)
    print("=" * 70)
    print("TEST: Renumbering higher indices [12], [13], [14] -> [0], [1], [2]")
    print("=" * 70)

    merged_text2 = "Some text[12]more text[13]final text[14]"
    print(f"Input text: {merged_text2}")

    has_simple2 = bool(re.search(r'(?<!\[)\[\d+\](?!\])', merged_text2))
    has_safe2 = bool(re.search(r'\[\[\d+\]\]', merged_text2))

    if has_simple2 and not has_safe2:
        placeholder_pattern2 = r'(?<!\[)\[(\d+)\](?!\])'
        prefix2 = "["
        suffix2 = "]"
    else:
        placeholder_pattern2 = r'\[\[(\d+)\]\]'
        prefix2 = "[["
        suffix2 = "]]"

    global_placeholder_numbers2 = re.findall(placeholder_pattern2, merged_text2)
    global_placeholders2 = [f"{prefix2}{num}{suffix2}" for num in global_placeholder_numbers2]

    print(f"Found global placeholders: {global_placeholders2}")

    renumbered_text2 = merged_text2
    for local_idx, global_placeholder in enumerate(global_placeholders2):
        local_placeholder = f"{prefix2}{local_idx}{suffix2}"
        print(f"  Renumber: {global_placeholder} -> {local_placeholder}")
        renumbered_text2 = renumbered_text2.replace(global_placeholder, local_placeholder)

    print(f"Final text: {renumbered_text2}")

    expected2 = "Some text[0]more text[1]final text[2]"
    if renumbered_text2 == expected2:
        print("Result: SUCCESS - Correctly renumbered to local indices!")
    else:
        print(f"Result: FAIL - Expected: {expected2}")
        print(f"                Got:      {renumbered_text2}")

if __name__ == "__main__":
    test_simple_format_detection()
