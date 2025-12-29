"""
Helper functions for translation examples.

This module provides unified access to technical examples:
- Placeholder preservation (generated dynamically)
"""

from typing import Any, Dict, Optional, Tuple

from .constants import TAG0, TAG1, TAG2, IMG_MARKER
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


def get_output_format_example(target_lang: str, fast_mode: bool = False) -> str:
    """Get output format example for a target language."""
    lang_key = target_lang.lower()
    mode_key = "fast_mode" if fast_mode else "standard"

    if lang_key in OUTPUT_FORMAT_EXAMPLES:
        return OUTPUT_FORMAT_EXAMPLES[lang_key][mode_key]

    if fast_mode:
        return "Your translated text here"
    return f"Your translated text here, with all {TAG0} markers preserved exactly"


def build_placeholder_section(
    source_lang: str,
    target_lang: str
) -> str:
    """
    Build the placeholder preservation section with language-specific examples.

    Returns formatted instructions for preserving placeholders.
    """
    example, actual_source, actual_target = get_placeholder_example(source_lang, target_lang)

    return f"""# PLACEHOLDER PRESERVATION (CRITICAL)

You will encounter placeholders like: {TAG0}, {TAG1}, {TAG2}
These represent HTML/XML tags that have been temporarily replaced.

**MANDATORY RULES:**
1. Keep ALL placeholders EXACTLY as they appear
2. Do NOT translate, modify, remove, or explain them
3. Maintain their EXACT position in the sentence structure
4. Do NOT add spaces around them unless present in the source

**Example ({actual_source.title()} → {actual_target.title()}):**

Source: "{example['source']}"
✅ Correct: "{example['correct']}"
❌ WRONG: "{example['wrong']}" (placeholders removed)
"""


def build_image_placeholder_section(
    source_lang: str,
    target_lang: str
) -> str:
    """
    Build the image marker preservation section with generic instructions.

    Returns formatted instructions for preserving image markers.
    """
    return f"""# IMAGE MARKERS - PRESERVE EXACTLY

Markers like {IMG_MARKER} represent images in the text.

**MANDATORY RULES:**
1. Keep ALL image markers EXACTLY as they appear (e.g., [IMG001], [IMG002])
2. Do NOT translate, modify, or remove them
3. Maintain their EXACT position between paragraphs
"""


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
