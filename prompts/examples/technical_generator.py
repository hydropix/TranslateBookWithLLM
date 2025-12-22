"""
Dynamic technical example generator for translation prompts.

This module generates simple, technical examples on-demand using the LLM.
These examples demonstrate WHAT to preserve (placeholders, image markers)
with simple sentences that present no translation difficulty.

For examples showing HOW to translate idiomatically (cultural adaptation,
avoiding literal translation), see cultural_examples.py.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Optional, Any

from .constants import TAG0, TAG1, IMG_MARKER


# Cache file location
CACHE_FILE = Path(__file__).parent / "technical_cache.json"

# Simple source templates - easy to translate, focus on technical preservation
PLACEHOLDER_TEMPLATE_EN = f"This is {TAG0}important{TAG1} text."
IMAGE_TEMPLATE_EN = f"The sun rose.\n\n{IMG_MARKER}\n\nBirds sang."


def _load_cache() -> Dict[str, Dict[str, Any]]:
    """Load cached examples from file."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_cache(cache: Dict[str, Dict[str, Any]]) -> None:
    """Save cache to file."""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"[WARNING] Could not save technical cache: {e}")


def _get_cache_key(source_lang: str, target_lang: str, example_type: str) -> str:
    """Generate cache key for a language pair and type."""
    return f"{source_lang.lower()}:{target_lang.lower()}:{example_type}"


def get_cached_technical_example(
    source_lang: str,
    target_lang: str,
    example_type: str  # "placeholder" or "image"
) -> Optional[Dict[str, str]]:
    """
    Get a cached technical example.

    Returns:
        Dict with "source", "correct", "wrong" or None if not cached.
    """
    cache = _load_cache()
    key = _get_cache_key(source_lang, target_lang, example_type)
    return cache.get(key)


def save_technical_example(
    source_lang: str,
    target_lang: str,
    example_type: str,
    example: Dict[str, str]
) -> None:
    """Save a generated example to the cache."""
    cache = _load_cache()
    key = _get_cache_key(source_lang, target_lang, example_type)
    cache[key] = example
    _save_cache(cache)


def _build_placeholder_prompt(source_lang: str, target_lang: str) -> str:
    """Build prompt to generate a placeholder preservation example."""
    return f"""Translate this simple sentence from {source_lang} to {target_lang}.

CRITICAL: Keep {TAG0} and {TAG1} EXACTLY as they appear. Do NOT modify them.

Sentence: {PLACEHOLDER_TEMPLATE_EN}

Reply with ONLY the translated sentence, nothing else."""


def _build_image_prompt(source_lang: str, target_lang: str) -> str:
    """Build prompt to generate an image marker preservation example."""
    return f"""Translate these two simple sentences from {source_lang} to {target_lang}.

CRITICAL: The marker {IMG_MARKER} represents an image. Keep it EXACTLY as-is, in the SAME position (between the two sentences).

Text:
The sun rose.

{IMG_MARKER}

Birds sang.

Reply with ONLY the translated text (two sentences with {IMG_MARKER} between them), nothing else."""


def _build_source_sentences_prompt(source_lang: str) -> str:
    """Build prompt to get source sentences in a non-English language."""
    return f"""Translate these phrases to {source_lang}:
1. "This is important text."
2. "The sun rose."
3. "Birds sang."

Reply with ONLY the three translations, one per line, numbered."""


async def generate_placeholder_example_async(
    source_lang: str,
    target_lang: str,
    provider: Any
) -> Optional[Dict[str, str]]:
    """
    Generate a placeholder preservation example using the LLM.

    Args:
        source_lang: Source language name
        target_lang: Target language name
        provider: An LLMProvider instance

    Returns:
        Dict with "source", "correct", "wrong" or None if failed.
    """
    try:
        # Get source sentence if not English
        if source_lang.lower() == "english":
            source_text = PLACEHOLDER_TEMPLATE_EN
        else:
            # First get the source sentence in the source language
            source_prompt = f'Translate to {source_lang}: "This is important text."\nReply with ONLY the translation.'
            source_response = await provider.generate(source_prompt, timeout=30)
            if not source_response:
                return None
            base_source = source_response.strip().strip('"\'')
            # Insert tags around "important" equivalent
            # For simplicity, just wrap the whole middle section
            source_text = f"{TAG0}{base_source}{TAG1}"

        # Generate target translation
        if target_lang.lower() == "english":
            translated = PLACEHOLDER_TEMPLATE_EN
        else:
            prompt = _build_placeholder_prompt(source_lang, target_lang)
            response = await provider.generate(prompt, timeout=30)
            if not response:
                return None
            translated = response.strip().strip('"\'')

        # Validate placeholders preserved
        if TAG0 not in translated or TAG1 not in translated:
            print(f"[WARNING] LLM did not preserve placeholders for {source_lang}->{target_lang}")
            return None

        # Build wrong example (placeholders removed)
        wrong = translated.replace(TAG0, "").replace(TAG1, "")
        wrong = " ".join(wrong.split())

        example = {
            "source": source_text,
            "correct": translated,
            "wrong": wrong
        }

        save_technical_example(source_lang, target_lang, "placeholder", example)
        return example

    except Exception as e:
        print(f"[WARNING] Failed to generate placeholder example: {e}")
        return None


async def generate_image_example_async(
    source_lang: str,
    target_lang: str,
    provider: Any
) -> Optional[Dict[str, str]]:
    """
    Generate an image marker preservation example using the LLM.

    Args:
        source_lang: Source language name
        target_lang: Target language name
        provider: An LLMProvider instance

    Returns:
        Dict with "source", "correct", "wrong" or None if failed.
    """
    try:
        # Get source sentences
        if source_lang.lower() == "english":
            source_s1 = "The sun rose."
            source_s2 = "Birds sang."
        else:
            prompt = _build_source_sentences_prompt(source_lang)
            response = await provider.generate(prompt, timeout=30)
            if not response:
                return None
            lines = [l.strip().lstrip('0123456789.-) ').strip('"\'')
                     for l in response.strip().split('\n') if l.strip()]
            if len(lines) < 3:
                return None
            source_s1 = lines[1]  # "The sun rose."
            source_s2 = lines[2]  # "Birds sang."

        # Get target translation
        if target_lang.lower() == "english":
            target_s1 = "The sun rose."
            target_s2 = "Birds sang."
        else:
            prompt = _build_image_prompt(source_lang, target_lang)
            response = await provider.generate(prompt, timeout=30)
            if not response or IMG_MARKER not in response:
                print(f"[WARNING] LLM did not preserve image marker for {source_lang}->{target_lang}")
                return None
            parts = response.split(IMG_MARKER)
            if len(parts) != 2:
                return None
            target_s1 = parts[0].strip()
            target_s2 = parts[1].strip()

        source_text = f"{source_s1}\n\n{IMG_MARKER}\n\n{source_s2}"
        correct_text = f"{target_s1}\n\n{IMG_MARKER}\n\n{target_s2}"
        wrong_text = f"{target_s1}\n{target_s2}\n{IMG_MARKER}"

        example = {
            "source": source_text,
            "correct": correct_text,
            "wrong": wrong_text
        }

        save_technical_example(source_lang, target_lang, "image", example)
        return example

    except Exception as e:
        print(f"[WARNING] Failed to generate image example: {e}")
        return None


def generate_placeholder_example_sync(
    source_lang: str,
    target_lang: str,
    provider: Any
) -> Optional[Dict[str, str]]:
    """Synchronous wrapper for placeholder example generation."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    generate_placeholder_example_async(source_lang, target_lang, provider)
                )
                return future.result(timeout=60)
        else:
            return loop.run_until_complete(
                generate_placeholder_example_async(source_lang, target_lang, provider)
            )
    except Exception as e:
        print(f"[WARNING] Sync placeholder generation failed: {e}")
        return None


def generate_image_example_sync(
    source_lang: str,
    target_lang: str,
    provider: Any
) -> Optional[Dict[str, str]]:
    """Synchronous wrapper for image example generation."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    generate_image_example_async(source_lang, target_lang, provider)
                )
                return future.result(timeout=60)
        else:
            return loop.run_until_complete(
                generate_image_example_async(source_lang, target_lang, provider)
            )
    except Exception as e:
        print(f"[WARNING] Sync image generation failed: {e}")
        return None


async def ensure_technical_examples_ready(
    source_lang: str,
    target_lang: str,
    provider: Optional[Any] = None,
    fast_mode: bool = False
) -> bool:
    """
    Ensure technical examples exist for the language pair.

    Generates missing examples using the LLM if a provider is given.

    Args:
        source_lang: Source language name
        target_lang: Target language name
        provider: Optional LLMProvider instance
        fast_mode: If True, only generates image examples

    Returns:
        True if all required examples exist or were generated.
    """
    results = []

    # Image examples always needed
    if not get_cached_technical_example(source_lang, target_lang, "image"):
        if provider:
            result = await generate_image_example_async(source_lang, target_lang, provider)
            results.append(result is not None)
        else:
            results.append(False)
    else:
        results.append(True)

    # Placeholder examples only for standard mode
    if not fast_mode:
        if not get_cached_technical_example(source_lang, target_lang, "placeholder"):
            if provider:
                result = await generate_placeholder_example_async(source_lang, target_lang, provider)
                results.append(result is not None)
            else:
                results.append(False)
        else:
            results.append(True)

    return all(results)
