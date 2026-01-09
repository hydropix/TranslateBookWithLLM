"""
Simple test for placeholder format detection and prompt generation.
"""

import re

# Simulate the detect_placeholder_mode function
def detect_placeholder_mode(text: str):
    """Detect which placeholder format to use based on text content."""
    PLACEHOLDER_PREFIX_SAFE = "[["
    PLACEHOLDER_SUFFIX_SAFE = "]]"
    PLACEHOLDER_PATTERN_SAFE = r'\[\[\d+\]\]'

    PLACEHOLDER_PREFIX_SIMPLE = "["
    PLACEHOLDER_SUFFIX_SIMPLE = "]"
    PLACEHOLDER_PATTERN_SIMPLE = r'(?<!\[)\[\d+\](?!\])'

    # Check if text contains [ or ] characters
    if '[' in text or ']' in text:
        return (PLACEHOLDER_PREFIX_SAFE, PLACEHOLDER_SUFFIX_SAFE, PLACEHOLDER_PATTERN_SAFE)
    else:
        return (PLACEHOLDER_PREFIX_SIMPLE, PLACEHOLDER_SUFFIX_SIMPLE, PLACEHOLDER_PATTERN_SIMPLE)


def test_format_detection():
    """Test placeholder format detection."""

    print("=" * 80)
    print("Testing placeholder format detection")
    print("=" * 80)
    print()

    # Test 1: Text without brackets
    text1 = "Hello world this is a test"
    prefix1, suffix1, pattern1 = detect_placeholder_mode(text1)
    print(f"Test 1 - Text: '{text1}'")
    print(f"  Detected format: {prefix1}N{suffix1}")
    print(f"  Expected: [N]")
    assert prefix1 == "[" and suffix1 == "]", "Should use simplified format"
    print("  ✓ PASS")
    print()

    # Test 2: Text with brackets
    text2 = "[Note: This is important] Hello world"
    prefix2, suffix2, pattern2 = detect_placeholder_mode(text2)
    print(f"Test 2 - Text: '{text2}'")
    print(f"  Detected format: {prefix2}N{suffix2}")
    print(f"  Expected: [[N]]")
    assert prefix2 == "[[" and suffix2 == "]]", "Should use safe format"
    print("  ✓ PASS")
    print()

    # Test 3: Example placeholder usage
    print("=" * 80)
    print("Example placeholder generation")
    print("=" * 80)
    print()

    # Simplified format
    print("Simplified format ([N]):")
    print(f"  Placeholder 0: {prefix1}0{suffix1}")
    print(f"  Placeholder 1: {prefix1}1{suffix1}")
    print(f"  Placeholder 2: {prefix1}2{suffix1}")
    print()

    # Safe format
    print("Safe format ([[N]]):")
    print(f"  Placeholder 0: {prefix2}0{suffix2}")
    print(f"  Placeholder 1: {prefix2}1{suffix2}")
    print(f"  Placeholder 2: {prefix2}2{suffix2}")
    print()

    print("=" * 80)
    print("ALL TESTS PASSED!")
    print("=" * 80)
    print()
    print("Summary:")
    print("✓ Format detection works correctly")
    print("✓ Simplified format [N] is used when text has no brackets")
    print("✓ Safe format [[N]] is used when text contains brackets")
    print()
    print("Next step: Verify that prompts use the correct format")


if __name__ == "__main__":
    test_format_detection()
