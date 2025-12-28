"""
Static technical example for translation prompts.

This module provides a simple, static English example demonstrating
placeholder preservation. No LLM generation is used to avoid random errors.

For examples showing HOW to translate idiomatically (cultural adaptation,
avoiding literal translation), see cultural_examples.py.
"""

from typing import Dict, Optional, Any

from .constants import TAG0, TAG1


# Static English example for placeholder preservation
STATIC_PLACEHOLDER_EXAMPLE = {
    "source": f"This is {TAG0}important{TAG1} text.",
    "correct": f"This is {TAG0}important{TAG1} text.",
    "wrong": "This is important text."
}


def get_cached_technical_example(
    source_lang: str,
    target_lang: str,
    example_type: str  # "placeholder"
) -> Optional[Dict[str, str]]:
    """
    Get the static technical example.

    Always returns the same English example regardless of language pair.

    Returns:
        Dict with "source", "correct", "wrong".
    """
    if example_type == "placeholder":
        return STATIC_PLACEHOLDER_EXAMPLE
    return None


def get_placeholder_example() -> Dict[str, str]:
    """
    Get the static placeholder preservation example.

    Returns:
        Dict with "source", "correct", "wrong" keys.
    """
    return STATIC_PLACEHOLDER_EXAMPLE


async def ensure_technical_examples_ready(
    source_lang: str,
    target_lang: str,
    provider: Optional[Any] = None,
    fast_mode: bool = False
) -> bool:
    """
    Check if technical examples are ready.

    Always returns True since we use static examples.

    Args:
        source_lang: Source language name (ignored)
        target_lang: Target language name (ignored)
        provider: Optional LLMProvider instance (ignored)
        fast_mode: If True, skips placeholder examples (not needed)

    Returns:
        True always (static examples are always available).
    """
    return True
