"""
Benchmark translation wrapper.

Provides a simplified interface for translating reference texts
using Ollama models for benchmark testing.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Optional, Callable

from benchmark.config import BenchmarkConfig
from benchmark.models import ReferenceText, TranslationResult
from src.core.llm_providers import OllamaProvider
from src.config import TRANSLATE_TAG_IN, TRANSLATE_TAG_OUT


@dataclass
class TranslationRequest:
    """Request for a single translation."""

    text: ReferenceText
    target_language: str
    target_language_name: str
    model: str


class BenchmarkTranslator:
    """
    Wrapper for Ollama translation in benchmark context.

    Simplified interface focusing on:
    - Single text translation
    - Timing measurement
    - Error handling for benchmark purposes
    """

    def __init__(
        self,
        config: BenchmarkConfig,
        log_callback: Optional[Callable[[str, str], None]] = None
    ):
        """
        Initialize the benchmark translator.

        Args:
            config: Benchmark configuration
            log_callback: Optional callback for logging (level, message)
        """
        self.config = config
        self.log_callback = log_callback
        self._providers: dict[str, OllamaProvider] = {}

    def _log(self, level: str, message: str) -> None:
        """Log a message using the callback if available."""
        if self.log_callback:
            self.log_callback(level, message)
        else:
            print(f"[{level.upper()}] {message}")

    def _get_provider(self, model: str) -> OllamaProvider:
        """Get or create an Ollama provider for the given model."""
        if model not in self._providers:
            self._providers[model] = OllamaProvider(
                api_endpoint=self.config.ollama.endpoint,
                model=model,
                context_window=self.config.ollama.num_ctx,
                log_callback=lambda level, msg: self._log(level, msg)
            )
        return self._providers[model]

    def _build_prompt(
        self,
        text: str,
        source_language: str,
        target_language: str
    ) -> tuple[str, str]:
        """
        Build system and user prompts for literary translation.

        Similar to the main app's prompts but focused on literary texts
        without technical elements (no placeholders, HTML, code, etc.).

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        system_prompt = f"""You are a professional {target_language} translator and writer.

# CRITICAL: TARGET LANGUAGE IS {target_language.upper()}

**YOUR TRANSLATION MUST BE WRITTEN ENTIRELY IN {target_language.upper()}.**

You are translating FROM {source_language} TO {target_language}.
Your output must be in {target_language} ONLY - do NOT use any other language.

# TRANSLATION PRINCIPLES

**Quality Standards:**
- Translate faithfully while preserving the author's literary style, tone, and voice
- Maintain the original meaning
- Restructure sentences naturally in {target_language} (avoid word-by-word translation)
- Adapt cultural references, idioms, and expressions to {target_language} context
- Keep period-appropriate language when translating historical or classical texts
- Preserve the emotional impact and atmosphere of the original
- **WRITE YOUR TRANSLATION IN {target_language.upper()} - THIS IS MANDATORY**

# FINAL REMINDER: YOUR OUTPUT LANGUAGE

**YOU MUST TRANSLATE INTO {target_language.upper()}.**
Your entire translation output must be written in {target_language}.
Do NOT write in {source_language} or any other language - ONLY {target_language.upper()}.

# OUTPUT FORMAT

**CRITICAL OUTPUT RULES:**
1. Your response MUST start with {TRANSLATE_TAG_IN} (first characters, no text before)
2. Your response MUST end with {TRANSLATE_TAG_OUT} (last characters, no text after)
3. Include NOTHING before {TRANSLATE_TAG_IN} and NOTHING after {TRANSLATE_TAG_OUT}
4. Do NOT add explanations, comments, notes, or greetings

**INCORRECT examples (DO NOT do this):**
- "Here is the translation: {TRANSLATE_TAG_IN}Text...{TRANSLATE_TAG_OUT}"
- "{TRANSLATE_TAG_IN}Text...{TRANSLATE_TAG_OUT} (Additional comment)"
- "Sure! {TRANSLATE_TAG_IN}Text...{TRANSLATE_TAG_OUT}"

**CORRECT format (ONLY this):**
{TRANSLATE_TAG_IN}
Your translated text here
{TRANSLATE_TAG_OUT}"""

        user_prompt = f"""# TEXT TO TRANSLATE

{text}

REMINDER: Output ONLY your translation in this exact format:
{TRANSLATE_TAG_IN}
your translation here
{TRANSLATE_TAG_OUT}

Start with {TRANSLATE_TAG_IN} and end with {TRANSLATE_TAG_OUT}. Nothing before or after.

Provide your translation now:"""

        return system_prompt, user_prompt

    async def translate(self, request: TranslationRequest) -> TranslationResult:
        """
        Translate a single reference text.

        Args:
            request: Translation request details

        Returns:
            TranslationResult with translation or error
        """
        start_time = time.perf_counter()

        try:
            provider = self._get_provider(request.model)

            system_prompt, user_prompt = self._build_prompt(
                text=request.text.content,
                source_language=self.config.source_language,
                target_language=request.target_language_name
            )

            # Make the translation request
            response = await provider.generate(
                prompt=user_prompt,
                timeout=self.config.ollama.timeout,
                system_prompt=system_prompt
            )

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            if not response:
                return TranslationResult(
                    source_text_id=request.text.id,
                    target_language=request.target_language,
                    model=request.model,
                    translated_text="",
                    translation_time_ms=elapsed_ms,
                    error="No response from Ollama"
                )

            # Extract translation from response
            translated_text = provider.extract_translation(response)

            if not translated_text:
                # Fallback: use the raw response if extraction fails
                self._log("warning", f"Could not extract translation tags, using raw response")
                translated_text = response.strip()

            return TranslationResult(
                source_text_id=request.text.id,
                target_language=request.target_language,
                model=request.model,
                translated_text=translated_text,
                translation_time_ms=elapsed_ms
            )

        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            self._log("error", f"Translation failed: {e}")

            return TranslationResult(
                source_text_id=request.text.id,
                target_language=request.target_language,
                model=request.model,
                translated_text="",
                translation_time_ms=elapsed_ms,
                error=str(e)
            )

    async def translate_batch(
        self,
        requests: list[TranslationRequest],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> list[TranslationResult]:
        """
        Translate multiple texts sequentially.

        Args:
            requests: List of translation requests
            progress_callback: Optional callback (completed, total)

        Returns:
            List of TranslationResults
        """
        results = []
        total = len(requests)

        for i, request in enumerate(requests):
            self._log("info", f"Translating {request.text.id} to {request.target_language_name} with {request.model}")

            result = await self.translate(request)
            results.append(result)

            if progress_callback:
                progress_callback(i + 1, total)

            # Small delay to avoid overwhelming the Ollama server
            if i < total - 1:
                await asyncio.sleep(0.5)

        return results

    async def close(self) -> None:
        """Close all provider connections."""
        for provider in self._providers.values():
            await provider.close()
        self._providers.clear()


async def test_ollama_connection(config: BenchmarkConfig) -> tuple[bool, str]:
    """
    Test if Ollama is accessible and the default model is available.

    Args:
        config: Benchmark configuration

    Returns:
        Tuple of (success, message)
    """
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Test Ollama API endpoint
            response = await client.get(
                config.ollama.endpoint.replace("/api/generate", "/api/tags")
            )
            response.raise_for_status()

            data = response.json()
            models = [m["name"] for m in data.get("models", [])]

            if not models:
                return False, "No models found in Ollama. Run 'ollama pull <model>' first."

            return True, f"Ollama connected. Available models: {', '.join(models[:5])}..."

    except httpx.ConnectError:
        return False, f"Cannot connect to Ollama at {config.ollama.endpoint}. Is Ollama running?"
    except Exception as e:
        return False, f"Ollama connection test failed: {e}"


async def get_available_ollama_models(config: BenchmarkConfig) -> list[str]:
    """
    Get list of available Ollama models.

    Args:
        config: Benchmark configuration

    Returns:
        List of model names
    """
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                config.ollama.endpoint.replace("/api/generate", "/api/tags")
            )
            response.raise_for_status()

            data = response.json()
            return [m["name"] for m in data.get("models", [])]

    except Exception:
        return []
