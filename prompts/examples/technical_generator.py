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
    Get a cached technical example for the language pair.

    Returns None to allow fallback to language-specific examples
    in placeholder_examples.py which have properly translated content.

    Returns:
        None - defers to static examples in placeholder_examples.py
    """
    # Return None to use the properly translated examples from placeholder_examples.py
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
    provider: Optional[Any] = None
) -> bool:
    """
    Check if technical examples are ready.

    Always returns True since we use static examples.

    Args:
        source_lang: Source language name (ignored)
        target_lang: Target language name (ignored)
        provider: Optional LLMProvider instance (ignored)

    Returns:
        True always (static examples are always available).
    """
    return True
