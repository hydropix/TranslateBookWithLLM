"""
Dynamic image example generator for missing language pairs.

DEPRECATED: This module is superseded by technical_generator.py which provides
a unified generator for both placeholder and image examples.
This file is kept for backwards compatibility with existing cache files.

This module generates image placeholder preservation examples on-demand using the
configured LLM provider, with persistent file-based caching.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Optional, Any

from .constants import IMG_MARKER

# Cache file location (same directory as this module)
IMAGE_CACHE_FILE = Path(__file__).parent / "image_examples_cache.json"

# Source template - simple two sentences with image marker between
SOURCE_TEMPLATE_EN = f"The sun rose.\n\n{IMG_MARKER}\n\nBirds sang."


def _load_image_cache() -> Dict[str, Dict[str, str]]:
    """Load cached image examples from file."""
    if IMAGE_CACHE_FILE.exists():
        try:
            with open(IMAGE_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_image_cache(cache: Dict[str, Dict[str, str]]) -> None:
    """Save image examples cache to file."""
    try:
        with open(IMAGE_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"[WARNING] Could not save image examples cache: {e}")


def _get_cache_key(source_lang: str, target_lang: str) -> str:
    """Generate cache key for a language pair."""
    return f"{source_lang.lower()}:{target_lang.lower()}"


def get_cached_image_example(
    source_lang: str,
    target_lang: str
) -> Optional[Dict[str, str]]:
    """
    Get a cached image example for a language pair.

    Returns:
        Dict with "source", "correct", "wrong" or None if not cached.
    """
    cache = _load_image_cache()
    key = _get_cache_key(source_lang, target_lang)
    return cache.get(key)


def save_generated_image_example(
    source_lang: str,
    target_lang: str,
    example: Dict[str, str]
) -> None:
    """Save a generated image example to the cache."""
    cache = _load_image_cache()
    key = _get_cache_key(source_lang, target_lang)
    cache[key] = example
    _save_image_cache(cache)


def build_image_generation_prompt(source_lang: str, target_lang: str) -> str:
    """
    Build a prompt to generate an image preservation example.

    The prompt asks the LLM to translate two simple sentences while
    preserving the image marker in its exact position.
    """
    return f"""Translate these two sentences from {source_lang} to {target_lang}.

CRITICAL: The marker {IMG_MARKER} represents an image. Keep it EXACTLY as-is, in the SAME position (between the two sentences, with blank lines around it).

Text to translate:
The sun rose.

{IMG_MARKER}

Birds sang.

Reply with ONLY the translated text (two sentences with {IMG_MARKER} between them), nothing else. Keep the same line structure."""


def build_source_sentence_prompt(source_lang: str) -> str:
    """
    Build a prompt to get the source sentences in the source language.

    When source is not English, we need to get "The sun rose" and "Birds sang"
    in the source language first.
    """
    return f"""Translate these two simple sentences to {source_lang}:
1. "The sun rose."
2. "Birds sang."

Reply with ONLY the two translated sentences, one per line, nothing else."""


async def generate_image_example_async(
    source_lang: str,
    target_lang: str,
    provider: Any  # LLMProvider instance
) -> Optional[Dict[str, str]]:
    """
    Generate an image placeholder example using the LLM provider.

    Args:
        source_lang: Source language name
        target_lang: Target language name
        provider: An LLMProvider instance (OllamaProvider, GeminiProvider, etc.)

    Returns:
        Dict with "source", "correct", "wrong" examples, or None if generation failed.
    """
    try:
        # Step 1: Get source sentences
        if source_lang.lower() == "english":
            source_sentence1 = "The sun rose."
            source_sentence2 = "Birds sang."
        else:
            # Generate source sentences in the source language
            source_prompt = build_source_sentence_prompt(source_lang)
            source_response = await provider.generate(source_prompt, timeout=30)

            if not source_response:
                return None

            # Parse the two sentences
            lines = [l.strip() for l in source_response.strip().split('\n') if l.strip()]
            if len(lines) < 2:
                print(f"[WARNING] Could not parse source sentences for {source_lang}")
                return None

            # Clean up numbering if present (e.g., "1. 해가 떠올랐다.")
            source_sentence1 = lines[0].lstrip('0123456789.-) ').strip('"\'')
            source_sentence2 = lines[1].lstrip('0123456789.-) ').strip('"\'')

        # Step 2: Get target translation
        if target_lang.lower() == "english":
            target_sentence1 = "The sun rose."
            target_sentence2 = "Birds sang."
        else:
            # Generate translation
            translate_prompt = build_image_generation_prompt(source_lang, target_lang)
            translate_response = await provider.generate(translate_prompt, timeout=30)

            if not translate_response:
                return None

            # Validate that image marker is preserved
            if IMG_MARKER not in translate_response:
                print(f"[WARNING] LLM did not preserve image marker for {source_lang}->{target_lang}")
                return None

            # Parse the response - split by image marker
            parts = translate_response.split(IMG_MARKER)
            if len(parts) != 2:
                print(f"[WARNING] Unexpected format in image example for {source_lang}->{target_lang}")
                return None

            target_sentence1 = parts[0].strip()
            target_sentence2 = parts[1].strip()

        # Build the example
        source_text = f"{source_sentence1}\n\n{IMG_MARKER}\n\n{source_sentence2}"
        correct_text = f"{target_sentence1}\n\n{IMG_MARKER}\n\n{target_sentence2}"
        # Wrong example: image marker moved to end
        wrong_text = f"{target_sentence1}\n{target_sentence2}\n{IMG_MARKER}"

        example = {
            "source": source_text,
            "correct": correct_text,
            "wrong": wrong_text
        }

        # Cache the result
        save_generated_image_example(source_lang, target_lang, example)

        return example

    except Exception as e:
        print(f"[WARNING] Failed to generate image example for {source_lang}->{target_lang}: {e}")
        return None


def generate_image_example_sync(
    source_lang: str,
    target_lang: str,
    provider: Any
) -> Optional[Dict[str, str]]:
    """
    Synchronous wrapper for generate_image_example_async.

    Use this when calling from synchronous code.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a new task
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
        print(f"[WARNING] Sync image generation failed for {source_lang}->{target_lang}: {e}")
        return None
