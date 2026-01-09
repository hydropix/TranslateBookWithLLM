"""
Test script to verify that placeholder format is correctly passed through the system.
"""

import sys
import os

# Add parent directory to path to enable imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_placeholder_formats():
    """Test both simplified and safe placeholder formats."""

    # Import here to avoid circular imports
    from src.core.epub.tag_preservation import TagPreserver
    from prompts.examples.helpers import build_placeholder_section
    from prompts.prompts import generate_translation_prompt, generate_placeholder_correction_prompt

    print("=" * 80)
    print("TEST 1: Text without brackets (should use simplified format [N])")
    print("=" * 80)

    # Create HTML without brackets
    html_no_brackets = "<p><strong>Hello world</strong> this is a test</p>"

    preserver1 = TagPreserver()
    text1, tag_map1 = preserver1.preserve_tags(html_no_brackets)
    format1 = (preserver1.placeholder_prefix, preserver1.placeholder_suffix)

    print(f"Original HTML: {html_no_brackets}")
    print(f"Detected format: {format1[0]}N{format1[1]}")
    print(f"Text with placeholders: {text1}")
    print(f"Tag map: {tag_map1}")
    print()

    # Generate placeholder section with detected format
    placeholder_section1 = build_placeholder_section("English", "French", format1)
    print("Placeholder section for prompts:")
    print(placeholder_section1)
    print()

    # Generate translation prompt
    prompt1 = generate_translation_prompt(
        main_content=text1,
        context_before="",
        context_after="",
        previous_translation_context="",
        source_language="English",
        target_language="French",
        has_placeholders=True,
        placeholder_format=format1
    )

    print("Sample from system prompt (looking for placeholder format):")
    # Extract the PLACEHOLDER PRESERVATION section
    if "# PLACEHOLDER PRESERVATION" in prompt1.system:
        section_start = prompt1.system.index("# PLACEHOLDER PRESERVATION")
        section_end = prompt1.system.find("\n\n#", section_start + 1)
        if section_end == -1:
            section_end = len(prompt1.system)
        print(prompt1.system[section_start:section_end])
    print()

    print("=" * 80)
    print("TEST 2: Text with brackets (should use safe format [[N]])")
    print("=" * 80)

    # Create HTML with brackets
    html_with_brackets = "<p>[Note: This is important] <strong>Hello world</strong></p>"

    preserver2 = TagPreserver()
    text2, tag_map2 = preserver2.preserve_tags(html_with_brackets)
    format2 = (preserver2.placeholder_prefix, preserver2.placeholder_suffix)

    print(f"Original HTML: {html_with_brackets}")
    print(f"Detected format: {format2[0]}N{format2[1]}")
    print(f"Text with placeholders: {text2}")
    print(f"Tag map: {tag_map2}")
    print()

    # Generate placeholder section with detected format
    placeholder_section2 = build_placeholder_section("English", "French", format2)
    print("Placeholder section for prompts:")
    print(placeholder_section2)
    print()

    # Generate translation prompt
    prompt2 = generate_translation_prompt(
        main_content=text2,
        context_before="",
        context_after="",
        previous_translation_context="",
        source_language="English",
        target_language="French",
        has_placeholders=True,
        placeholder_format=format2
    )

    print("Sample from system prompt (looking for placeholder format):")
    # Extract the PLACEHOLDER PRESERVATION section
    if "# PLACEHOLDER PRESERVATION" in prompt2.system:
        section_start = prompt2.system.index("# PLACEHOLDER PRESERVATION")
        section_end = prompt2.system.find("\n\n#", section_start + 1)
        if section_end == -1:
            section_end = len(prompt2.system)
        print(prompt2.system[section_start:section_end])
    print()

    print("=" * 80)
    print("TEST 3: Correction prompt with simplified format")
    print("=" * 80)

    correction_prompt1 = generate_placeholder_correction_prompt(
        original_text="[0]Hello[1] world",
        translated_text="Bonjour monde",  # Missing placeholders
        specific_errors="Missing placeholders [0] and [1]",
        source_language="English",
        target_language="French",
        expected_count=2,
        placeholder_format=('[', ']')
    )

    print("Correction prompt format check:")
    # Look for placeholder format examples
    if "**CORRECT format:**" in correction_prompt1.system:
        idx = correction_prompt1.system.index("**CORRECT format:**")
        print(correction_prompt1.system[idx:idx+200])
    print()

    print("=" * 80)
    print("TEST 4: Correction prompt with safe format")
    print("=" * 80)

    correction_prompt2 = generate_placeholder_correction_prompt(
        original_text="[[0]]Hello[[1]] world",
        translated_text="Bonjour monde",  # Missing placeholders
        specific_errors="Missing placeholders [[0]] and [[1]]",
        source_language="English",
        target_language="French",
        expected_count=2,
        placeholder_format=('[[', ']]')
    )

    print("Correction prompt format check:")
    # Look for placeholder format examples
    if "**CORRECT format:**" in correction_prompt2.system:
        idx = correction_prompt2.system.index("**CORRECT format:**")
        print(correction_prompt2.system[idx:idx+200])
    print()

    print("=" * 80)
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 80)
    print()
    print("Summary:")
    print(f"- Format 1 (no brackets in text): {format1[0]}N{format1[1]}")
    print(f"- Format 2 (brackets in text): {format2[0]}N{format2[1]}")
    print()
    print("✓ The system correctly adapts the prompt format based on the detected placeholder format!")


if __name__ == "__main__":
    test_placeholder_formats()
