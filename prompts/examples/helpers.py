"""
Helper functions for translation examples.

This module provides unified access to technical examples:
- Placeholder preservation (generated dynamically)
"""

from typing import Any, Dict, Optional, Tuple

from .constants import TAG0, TAG1, TAG2
from .placeholder_examples import get_example_for_pair
from .subtitle_examples import SUBTITLE_EXAMPLES
from .output_examples import OUTPUT_FORMAT_EXAMPLES


def get_placeholder_example(
    source_lang: str,
    target_lang: str
) -> Tuple[Dict[str, str], str, str]:
    """
    Get placeholder preservation example for a language pair.

    Generates examples dynamically for any language pair using
    pre-translated sentences in each supported language.

    Returns:
        Tuple of (example_dict, actual_source_lang, actual_target_lang).
    """
    example = get_example_for_pair(source_lang, target_lang)
    return example, source_lang, target_lang


def get_subtitle_example(target_lang: str) -> str:
    """Get subtitle format example for a target language."""
    return SUBTITLE_EXAMPLES.get(
        target_lang.lower(),
        "[1]First translated line\n[2]Second translated line"
    )


def get_output_format_example(target_lang: str, has_placeholders: bool = True) -> str:
    """Get output format example for a target language."""
    lang_key = target_lang.lower()
    mode_key = "standard" if has_placeholders else "plain"

    if lang_key in OUTPUT_FORMAT_EXAMPLES:
        return OUTPUT_FORMAT_EXAMPLES[lang_key][mode_key]

    if has_placeholders:
        return f"Your translated text here, with all {TAG0} markers preserved exactly"
    return "Your translated text here"


def build_placeholder_section(
    source_lang: str,
    target_lang: str,
    placeholder_format: Optional[Tuple[str, str]] = None
) -> str:
    """
    Build the placeholder preservation section with language-specific examples.

    Args:
        source_lang: Source language name
        target_lang: Target language name
        placeholder_format: Optional tuple of (prefix, suffix) for placeholders
                          e.g., ('[', ']') for [0] or ('[[', ']]') for [[0]]
                          If None, uses default [[0]] format

    Returns formatted instructions for preserving placeholders.
    """
    # Use TAG0, TAG1, TAG2 constants (always [idN] format)
    tag0, tag1, tag2 = TAG0, TAG1, TAG2

    example, actual_source, actual_target = get_placeholder_example(source_lang, target_lang)

    # Use examples as-is (already using [idN] format)
    example_source = example['source']
    example_correct = example['correct']

    return f"""# PLACEHOLDER PRESERVATION (CRITICAL)

You will encounter placeholders like: {tag0}, {tag1}, {tag2}
These represent HTML/XML tags that have been temporarily replaced.

**UNIFIED FORMAT:**
All placeholders use the [idN] format: [id0], [id1], [id2]...
This semantic format provides the highest accuracy for preservation.

**MANDATORY RULES:**
1. Keep ALL placeholders EXACTLY as they appear
2. Do NOT translate, modify, remove, or explain them
3. Maintain their EXACT position in the sentence structure
4. Do NOT add spaces around them unless present in the source

**Example ({actual_source.title()} → {actual_target.title()}):**

Source: "{example_source}"
✅ Correct: "{example_correct}"
❌ WRONG: "{example['wrong']}" (placeholders removed)
"""


# Removed _extract_format_from_tag and _get_format_description
# These functions are no longer needed with unified [idN] format


def has_example_for_pair(source_lang: str, target_lang: str) -> bool:
    """Check if a placeholder example exists for the given language pair.

    Always returns True since examples are generated dynamically
    with fallback to English for unsupported languages.
    """
    return True


async def ensure_example_ready(
    source_lang: str,
    target_lang: str,
    provider: Optional[Any] = None
) -> bool:
    """
    Ensure a placeholder example exists for the language pair.

    Always returns True since examples are generated dynamically
    with fallback to English for unsupported languages.
    """
    return True
