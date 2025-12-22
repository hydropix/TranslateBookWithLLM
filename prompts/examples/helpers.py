"""
Helper functions for translation examples.

This module provides unified access to all example types:
- Technical examples: placeholder/image preservation (generated dynamically)
- Cultural examples: idiomatic translation (hand-curated high quality)
"""

from typing import Any, Dict, List, Optional, Tuple

from .constants import TAG0, TAG1, TAG2, IMG_MARKER
from .placeholder_examples import PLACEHOLDER_EXAMPLES
from .image_examples import IMAGE_EXAMPLES
from .subtitle_examples import SUBTITLE_EXAMPLES
from .output_examples import OUTPUT_FORMAT_EXAMPLES
from .cultural_examples import (
    get_cultural_examples,
    has_cultural_examples,
    format_cultural_examples_for_prompt,
)


def get_placeholder_example(
    source_lang: str,
    target_lang: str
) -> Tuple[Dict[str, str], str, str]:
    """
    Get placeholder preservation example for a language pair.

    Priority:
    1. Dynamically generated cache (technical_generator)
    2. Static fallback examples
    3. English→target or source→English fallback

    Returns:
        Tuple of (example_dict, actual_source_lang, actual_target_lang).
    """
    key = (source_lang.lower(), target_lang.lower())

    # 1. Check dynamic cache first
    try:
        from .technical_generator import get_cached_technical_example
        cached = get_cached_technical_example(source_lang, target_lang, "placeholder")
        if cached:
            return cached, source_lang, target_lang
    except ImportError:
        pass

    # 2. Static fallback examples
    if key in PLACEHOLDER_EXAMPLES:
        return PLACEHOLDER_EXAMPLES[key], source_lang, target_lang

    # 3. Check legacy generator cache
    try:
        from prompts.example_generator import get_cached_example
        cached = get_cached_example(source_lang, target_lang)
        if cached:
            return cached, source_lang, target_lang
    except ImportError:
        pass

    # 4. Fallback: English as source
    fallback_key = ("english", target_lang.lower())
    if fallback_key in PLACEHOLDER_EXAMPLES:
        return PLACEHOLDER_EXAMPLES[fallback_key], "English", target_lang

    # 5. Fallback: target is English
    fallback_key = (source_lang.lower(), "english")
    if fallback_key in PLACEHOLDER_EXAMPLES:
        return PLACEHOLDER_EXAMPLES[fallback_key], source_lang, "English"

    # 6. Ultimate fallback
    return PLACEHOLDER_EXAMPLES[("english", "chinese")], "English", "Chinese"


def get_image_example(
    source_lang: str,
    target_lang: str
) -> Tuple[Dict[str, str], str, str]:
    """
    Get image placeholder example for a language pair.

    Priority:
    1. Dynamically generated cache (technical_generator)
    2. Static fallback examples
    3. English→target or source→English fallback

    Returns:
        Tuple of (example_dict, actual_source_lang, actual_target_lang).
    """
    key = (source_lang.lower(), target_lang.lower())

    # 1. Check dynamic cache first
    try:
        from .technical_generator import get_cached_technical_example
        cached = get_cached_technical_example(source_lang, target_lang, "image")
        if cached:
            return cached, source_lang, target_lang
    except ImportError:
        pass

    # 2. Static fallback examples
    if key in IMAGE_EXAMPLES:
        return IMAGE_EXAMPLES[key], source_lang, target_lang

    # 3. Check legacy image generator cache
    try:
        from .image_generator import get_cached_image_example
        cached = get_cached_image_example(source_lang, target_lang)
        if cached:
            return cached, source_lang, target_lang
    except ImportError:
        pass

    # 4. Fallback: English as source
    fallback_key = ("english", target_lang.lower())
    if fallback_key in IMAGE_EXAMPLES:
        return IMAGE_EXAMPLES[fallback_key], "English", target_lang

    # 5. Fallback: target is English
    fallback_key = (source_lang.lower(), "english")
    if fallback_key in IMAGE_EXAMPLES:
        return IMAGE_EXAMPLES[fallback_key], source_lang, "English"

    # 6. Ultimate fallback
    return IMAGE_EXAMPLES[("english", "chinese")], "English", "Chinese"


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

**Example ({actual_source.title()} -> {actual_target.title()}):**

{actual_source.title()}: "{example['source']}"
Correct: "{example['correct']}"
WRONG: "{example['wrong']}" (placeholders removed)
"""


def build_image_placeholder_section(
    source_lang: str,
    target_lang: str
) -> str:
    """
    Build the image placeholder preservation section.

    Returns formatted instructions for preserving image markers.
    """
    example, actual_source, actual_target = get_image_example(source_lang, target_lang)

    return f"""# IMAGE MARKERS - PRESERVE EXACTLY

Markers like {IMG_MARKER} represent images. Keep them at their EXACT position.

**Example ({actual_source.title()} -> {actual_target.title()}):**
Source: {example['source']}
✅ {example['correct']}
❌ {example['wrong']}
"""


def build_cultural_section(
    source_lang: str,
    target_lang: str,
    count: int = 2
) -> str:
    """
    Build the cultural adaptation section with idiomatic examples.

    These examples show HOW to translate (avoid literal translation,
    adapt to target culture).

    Returns:
        Formatted cultural examples section, or empty string if none available.
    """
    return format_cultural_examples_for_prompt(source_lang, target_lang, count)


def has_example_for_pair(source_lang: str, target_lang: str) -> bool:
    """Check if a placeholder example exists for the given language pair."""
    key = (source_lang.lower(), target_lang.lower())

    # Check static examples
    if key in PLACEHOLDER_EXAMPLES:
        return True

    # Check dynamic cache
    try:
        from .technical_generator import get_cached_technical_example
        if get_cached_technical_example(source_lang, target_lang, "placeholder"):
            return True
    except ImportError:
        pass

    # Check legacy cache
    try:
        from prompts.example_generator import get_cached_example
        if get_cached_example(source_lang, target_lang):
            return True
    except ImportError:
        pass

    return False


def has_image_example_for_pair(source_lang: str, target_lang: str) -> bool:
    """Check if an image example exists for the given language pair."""
    key = (source_lang.lower(), target_lang.lower())

    if key in IMAGE_EXAMPLES:
        return True

    # Check dynamic cache
    try:
        from .technical_generator import get_cached_technical_example
        if get_cached_technical_example(source_lang, target_lang, "image"):
            return True
    except ImportError:
        pass

    # Check legacy cache
    try:
        from .image_generator import get_cached_image_example
        if get_cached_image_example(source_lang, target_lang):
            return True
    except ImportError:
        pass

    return False


async def ensure_example_ready(
    source_lang: str,
    target_lang: str,
    provider: Optional[Any] = None
) -> bool:
    """
    Ensure a placeholder example exists for the language pair.

    If no example exists and a provider is given, generates one dynamically.

    Returns:
        True if an example exists or was generated successfully.
    """
    if has_example_for_pair(source_lang, target_lang):
        return True

    if provider is None:
        return False

    try:
        from .technical_generator import generate_placeholder_example_async
        result = await generate_placeholder_example_async(source_lang, target_lang, provider)
        return result is not None
    except ImportError:
        pass

    # Fallback to legacy generator
    try:
        from prompts.example_generator import generate_example_async
        result = await generate_example_async(source_lang, target_lang, provider)
        return result is not None
    except ImportError:
        return False
    except Exception as e:
        print(f"[WARNING] Failed to generate example: {e}")
        return False


async def ensure_image_example_ready(
    source_lang: str,
    target_lang: str,
    provider: Optional[Any] = None
) -> bool:
    """
    Ensure an image example exists for the language pair.

    If no example exists and a provider is given, generates one dynamically.

    Returns:
        True if an example exists or was generated successfully.
    """
    if has_image_example_for_pair(source_lang, target_lang):
        return True

    if provider is None:
        return False

    try:
        from .technical_generator import generate_image_example_async
        result = await generate_image_example_async(source_lang, target_lang, provider)
        return result is not None
    except ImportError:
        pass

    # Fallback to legacy generator
    try:
        from .image_generator import generate_image_example_async
        result = await generate_image_example_async(source_lang, target_lang, provider)
        return result is not None
    except ImportError:
        return False
    except Exception as e:
        print(f"[WARNING] Failed to generate image example: {e}")
        return False


async def ensure_all_examples_ready(
    source_lang: str,
    target_lang: str,
    provider: Optional[Any] = None,
    fast_mode: bool = False
) -> bool:
    """
    Ensure all required examples exist for the language pair.

    Generates missing examples using the LLM if a provider is given.

    Args:
        source_lang: Source language name
        target_lang: Target language name
        provider: Optional LLMProvider instance
        fast_mode: If True, only generates image examples (no placeholders in fast mode)

    Returns:
        True if all required examples exist or were generated.
    """
    if fast_mode:
        return await ensure_image_example_ready(source_lang, target_lang, provider)
    else:
        placeholder_ready = await ensure_example_ready(source_lang, target_lang, provider)
        image_ready = await ensure_image_example_ready(source_lang, target_lang, provider)
        return placeholder_ready and image_ready
