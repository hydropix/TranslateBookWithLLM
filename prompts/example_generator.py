"""
Dynamic example generator for missing language pairs.

DEPRECATED: This module is superseded by prompts/examples/technical_generator.py
which provides a unified generator for both placeholder and image examples.
This file is kept for backwards compatibility with existing cache files.

This module generates placeholder preservation examples on-demand using the
configured LLM provider, with persistent file-based caching.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

from src.config import create_placeholder

# Generate placeholders using actual config
TAG0 = create_placeholder(0)
TAG1 = create_placeholder(1)

# Cache file location (same directory as this module)
CACHE_FILE = Path(__file__).parent / "examples_cache.json"

# Source sentence template (English) - simple and universal
SOURCE_TEMPLATE = f"This is {TAG0}very important{TAG1} information"


def _load_cache() -> Dict[str, Dict[str, str]]:
    """Load cached examples from file."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_cache(cache: Dict[str, Dict[str, str]]) -> None:
    """Save examples cache to file."""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"[WARNING] Could not save examples cache: {e}")


def _get_cache_key(source_lang: str, target_lang: str) -> str:
    """Generate cache key for a language pair."""
    return f"{source_lang.lower()}:{target_lang.lower()}"


def get_cached_example(
    source_lang: str,
    target_lang: str
) -> Optional[Dict[str, str]]:
    """
    Get a cached example for a language pair.

    Returns:
        Dict with "source", "correct", "wrong" or None if not cached.
    """
    cache = _load_cache()
    key = _get_cache_key(source_lang, target_lang)
    return cache.get(key)


def save_generated_example(
    source_lang: str,
    target_lang: str,
    example: Dict[str, str]
) -> None:
    """Save a generated example to the cache."""
    cache = _load_cache()
    key = _get_cache_key(source_lang, target_lang)
    cache[key] = example
    _save_cache(cache)


def build_generation_prompt(source_lang: str, target_lang: str) -> str:
    """
    Build a simple prompt to generate a translation example.

    The prompt is designed to be simple enough for any LLM to handle correctly.
    """
    return f"""Translate this sentence from {source_lang} to {target_lang}.

CRITICAL: Keep {TAG0} and {TAG1} EXACTLY as they are. Do NOT remove or modify them.

Sentence: {SOURCE_TEMPLATE}

Reply with ONLY the translated sentence, nothing else."""


async def generate_example_async(
    source_lang: str,
    target_lang: str,
    provider: Any  # LLMProvider instance
) -> Optional[Dict[str, str]]:
    """
    Generate a placeholder example using the LLM provider.

    Args:
        source_lang: Source language name
        target_lang: Target language name
        provider: An LLMProvider instance (OllamaProvider, GeminiProvider, etc.)

    Returns:
        Dict with "source", "correct", "wrong" examples, or None if generation failed.
    """
    prompt = build_generation_prompt(source_lang, target_lang)

    try:
        # Use a short timeout for this simple task
        response = await provider.generate(prompt, timeout=30)

        if not response:
            return None

        # Clean up the response
        translated = response.strip()

        # Remove any quotes if the LLM wrapped the response
        if translated.startswith('"') and translated.endswith('"'):
            translated = translated[1:-1]
        if translated.startswith("'") and translated.endswith("'"):
            translated = translated[1:-1]

        # Validate that placeholders are preserved
        if TAG0 not in translated or TAG1 not in translated:
            print(f"[WARNING] LLM did not preserve placeholders for {source_lang}->{target_lang}")
            return None

        # Create the "wrong" example by removing placeholders
        wrong = translated.replace(TAG0, "").replace(TAG1, "")
        # Clean up any double spaces
        wrong = " ".join(wrong.split())

        example = {
            "source": SOURCE_TEMPLATE,
            "correct": translated,
            "wrong": wrong
        }

        # Cache the result
        save_generated_example(source_lang, target_lang, example)

        return example

    except Exception as e:
        print(f"[WARNING] Failed to generate example for {source_lang}->{target_lang}: {e}")
        return None


def generate_example_sync(
    source_lang: str,
    target_lang: str,
    provider: Any
) -> Optional[Dict[str, str]]:
    """
    Synchronous wrapper for generate_example_async.

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
                    generate_example_async(source_lang, target_lang, provider)
                )
                return future.result(timeout=60)
        else:
            return loop.run_until_complete(
                generate_example_async(source_lang, target_lang, provider)
            )
    except Exception as e:
        print(f"[WARNING] Sync generation failed for {source_lang}->{target_lang}: {e}")
        return None


async def ensure_example_exists(
    source_lang: str,
    target_lang: str,
    provider: Any,
    static_examples: Dict[Tuple[str, str], Dict[str, str]]
) -> Tuple[Dict[str, str], str, str]:
    """
    Ensure an example exists for the language pair.

    Checks in order:
    1. Static examples (from examples.py)
    2. Cached generated examples
    3. Generate new example with LLM
    4. Fallback to English->Chinese

    Args:
        source_lang: Source language name
        target_lang: Target language name
        provider: LLMProvider instance
        static_examples: PLACEHOLDER_EXAMPLES dict from examples.py

    Returns:
        Tuple of (example_dict, actual_source_lang, actual_target_lang)
    """
    key = (source_lang.lower(), target_lang.lower())

    # 1. Check static examples
    if key in static_examples:
        return static_examples[key], source_lang, target_lang

    # 2. Check cache
    cached = get_cached_example(source_lang, target_lang)
    if cached:
        return cached, source_lang, target_lang

    # 3. Try to generate with LLM
    if provider:
        generated = await generate_example_async(source_lang, target_lang, provider)
        if generated:
            print(f"[INFO] Generated placeholder example for {source_lang}->{target_lang}")
            return generated, source_lang, target_lang

    # 4. Fallback chain: try English as source, then source to English
    fallback_key = ("english", target_lang.lower())
    if fallback_key in static_examples:
        return static_examples[fallback_key], "English", target_lang

    fallback_key = (source_lang.lower(), "english")
    if fallback_key in static_examples:
        return static_examples[fallback_key], source_lang, "English"

    # 5. Ultimate fallback
    return static_examples[("english", "chinese")], "English", "Chinese"
