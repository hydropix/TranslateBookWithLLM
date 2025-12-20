"""
LLM-based translation quality evaluator.

Uses OpenRouter to evaluate translations with models like:
- anthropic/claude-3.5-sonnet
- openai/gpt-4o
- google/gemini-pro-1.5
"""

import asyncio
import json
import re
import time
from typing import Optional, Callable

import httpx

from benchmark.config import BenchmarkConfig
from benchmark.models import EvaluationScores, ReferenceText


class TranslationEvaluator:
    """
    Evaluates translation quality using LLMs via OpenRouter.

    Criteria:
    - Accuracy (1-10): Preservation of meaning
    - Fluency (1-10): Natural expression in target language
    - Style (1-10): Preservation of literary style/tone
    - Overall (1-10): Global quality score
    """

    def __init__(
        self,
        config: BenchmarkConfig,
        log_callback: Optional[Callable[[str, str], None]] = None
    ):
        """
        Initialize the evaluator.

        Args:
            config: Benchmark configuration with OpenRouter settings
            log_callback: Optional callback for logging (level, message)
        """
        self.config = config
        self.log_callback = log_callback
        self._client: Optional[httpx.AsyncClient] = None

        # Cost tracking
        self.total_cost: float = 0.0
        self.total_evaluations: int = 0

    def _log(self, level: str, message: str) -> None:
        """Log a message using the callback if available."""
        if self.log_callback:
            self.log_callback(level, message)
        else:
            print(f"[{level.upper()}] {message}")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.openrouter.timeout)
            )
        return self._client

    def _build_evaluation_prompt(
        self,
        source_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
        text_style: str,
        text_title: str,
        text_author: str
    ) -> tuple[str, str]:
        """
        Build the evaluation prompt.

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        system_prompt = """You are an expert literary translation evaluator with deep knowledge of multiple languages and translation theory.

Your task is to evaluate the quality of a translation objectively and precisely.

# EVALUATION CRITERIA

Score each criterion from 1-10:

1. **Accuracy (1-10)**: How faithfully does the translation preserve the meaning?
   - 10: Perfect meaning preservation, all nuances captured
   - 7-9: Minor omissions or slight meaning shifts
   - 4-6: Some meaning lost or distorted
   - 1-3: Significant meaning errors or omissions

2. **Fluency (1-10)**: How natural does the translation read in the target language?
   - 10: Reads like original prose written by a native speaker
   - 7-9: Natural with minor awkward phrasings
   - 4-6: Understandable but clearly translated
   - 1-3: Unnatural, difficult to read

3. **Style (1-10)**: How well is the literary style/tone preserved?
   - 10: Perfect style match (irony, formality, era, voice)
   - 7-9: Style mostly preserved with minor deviations
   - 4-6: Noticeable style changes
   - 1-3: Style completely different from original

4. **Overall (1-10)**: Your holistic quality assessment.
   - Consider all factors and give an overall grade

# OUTPUT FORMAT

You MUST respond with ONLY a valid JSON object. No text before or after.

{
  "accuracy": <number 1-10>,
  "fluency": <number 1-10>,
  "style": <number 1-10>,
  "overall": <number 1-10>,
  "feedback": "<brief feedback explaining scores, 1-2 sentences>"
}"""

        user_prompt = f"""# TRANSLATION EVALUATION REQUEST

**Source Language**: {source_language}
**Target Language**: {target_language}
**Source Text**: "{text_title}" by {text_author}
**Style**: {text_style}

## Original Text ({source_language}):

{source_text}

## Translation ({target_language}):

{translated_text}

---

Evaluate this translation. Respond with ONLY the JSON object:"""

        return system_prompt, user_prompt

    def _parse_evaluation_response(self, response: str) -> Optional[EvaluationScores]:
        """
        Parse the JSON evaluation response.

        Args:
            response: Raw response from the LLM

        Returns:
            EvaluationScores or None if parsing fails
        """
        try:
            # Clean up the response - remove markdown code blocks if present
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            # Try to find JSON object in response
            json_match = re.search(r'\{[^{}]*\}', cleaned, re.DOTALL)
            if json_match:
                cleaned = json_match.group(0)

            data = json.loads(cleaned)

            # Validate and clamp scores to 1-10 range
            def clamp_score(value: any) -> float:
                try:
                    score = float(value)
                    return max(1.0, min(10.0, score))
                except (TypeError, ValueError):
                    return 5.0  # Default to middle score

            return EvaluationScores(
                accuracy=clamp_score(data.get("accuracy", 5)),
                fluency=clamp_score(data.get("fluency", 5)),
                style=clamp_score(data.get("style", 5)),
                overall=clamp_score(data.get("overall", 5)),
                feedback=str(data.get("feedback", ""))[:500]  # Limit feedback length
            )

        except json.JSONDecodeError as e:
            self._log("warning", f"Failed to parse evaluation JSON: {e}")
            self._log("debug", f"Raw response: {response[:500]}")
            return None
        except Exception as e:
            self._log("error", f"Evaluation parsing error: {e}")
            return None

    async def evaluate(
        self,
        source_text: ReferenceText,
        translated_text: str,
        target_language: str,
        target_language_name: str
    ) -> tuple[EvaluationScores, int]:
        """
        Evaluate a single translation.

        Args:
            source_text: Original reference text
            translated_text: The translation to evaluate
            target_language: Language code (e.g., "fr")
            target_language_name: Full language name (e.g., "French")

        Returns:
            Tuple of (EvaluationScores, evaluation_time_ms)
        """
        if not self.config.openrouter.api_key:
            return EvaluationScores.failed("OpenRouter API key not configured"), 0

        if not translated_text or not translated_text.strip():
            return EvaluationScores.failed("Empty translation"), 0

        start_time = time.perf_counter()

        try:
            client = await self._get_client()

            system_prompt, user_prompt = self._build_evaluation_prompt(
                source_text=source_text.content,
                translated_text=translated_text,
                source_language=self.config.source_language,
                target_language=target_language_name,
                text_style=source_text.style,
                text_title=source_text.title,
                text_author=source_text.author
            )

            headers = {
                "Authorization": f"Bearer {self.config.openrouter.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": self.config.openrouter.site_url,
                "X-Title": self.config.openrouter.site_name,
            }

            payload = {
                "model": self.config.openrouter.default_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,  # Lower temperature for consistent scoring
                "max_tokens": 500,
            }

            response = await client.post(
                self.config.openrouter.endpoint,
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            result = response.json()
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            # Track cost
            if "usage" in result:
                usage = result["usage"]
                # Estimate cost (rough approximation)
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                # Use OpenRouter's cost if available
                cost = float(result.get("cost", 0))
                if cost == 0:
                    # Fallback estimate
                    cost = (prompt_tokens * 0.50 / 1_000_000) + (completion_tokens * 1.50 / 1_000_000)
                self.total_cost += cost
                self.total_evaluations += 1
                self._log("debug", f"Evaluation cost: ${cost:.6f} (total: ${self.total_cost:.4f})")

            # Extract response content
            if "choices" not in result or len(result["choices"]) == 0:
                return EvaluationScores.failed("No response from OpenRouter"), elapsed_ms

            response_text = result["choices"][0].get("message", {}).get("content", "")

            if not response_text:
                return EvaluationScores.failed("Empty response from OpenRouter"), elapsed_ms

            # Parse the evaluation
            scores = self._parse_evaluation_response(response_text)

            if scores is None:
                return EvaluationScores.failed("Failed to parse evaluation response"), elapsed_ms

            return scores, elapsed_ms

        except httpx.HTTPStatusError as e:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            error_msg = f"OpenRouter HTTP error: {e.response.status_code}"

            if e.response.status_code == 401:
                error_msg = "Invalid OpenRouter API key"
            elif e.response.status_code == 402:
                error_msg = "Insufficient OpenRouter credits"
            elif e.response.status_code == 404:
                error_msg = f"Model not found: {self.config.openrouter.default_model}"

            self._log("error", error_msg)
            return EvaluationScores.failed(error_msg), elapsed_ms

        except httpx.TimeoutException:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            self._log("error", "OpenRouter request timed out")
            return EvaluationScores.failed("Evaluation request timed out"), elapsed_ms

        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            self._log("error", f"Evaluation failed: {e}")
            return EvaluationScores.failed(str(e)), elapsed_ms

    async def evaluate_batch(
        self,
        evaluations: list[tuple[ReferenceText, str, str, str]],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> list[tuple[EvaluationScores, int]]:
        """
        Evaluate multiple translations.

        Args:
            evaluations: List of (source_text, translated_text, lang_code, lang_name)
            progress_callback: Optional callback (completed, total)

        Returns:
            List of (EvaluationScores, evaluation_time_ms)
        """
        results = []
        total = len(evaluations)

        for i, (source_text, translated_text, lang_code, lang_name) in enumerate(evaluations):
            self._log("info", f"Evaluating {source_text.id} -> {lang_name}")

            scores, elapsed_ms = await self.evaluate(
                source_text=source_text,
                translated_text=translated_text,
                target_language=lang_code,
                target_language_name=lang_name
            )
            results.append((scores, elapsed_ms))

            if progress_callback:
                progress_callback(i + 1, total)

            # Rate limiting - OpenRouter has limits
            if i < total - 1:
                await asyncio.sleep(0.5)

        return results

    def get_cost_summary(self) -> dict:
        """Get summary of evaluation costs."""
        return {
            "total_cost_usd": self.total_cost,
            "total_evaluations": self.total_evaluations,
            "avg_cost_per_evaluation": (
                self.total_cost / self.total_evaluations
                if self.total_evaluations > 0 else 0
            ),
        }

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


async def test_openrouter_connection(config: BenchmarkConfig) -> tuple[bool, str]:
    """
    Test if OpenRouter is accessible and the API key is valid.

    Args:
        config: Benchmark configuration

    Returns:
        Tuple of (success, message)
    """
    if not config.openrouter.api_key:
        return False, "OpenRouter API key not configured"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Test with a simple request
            headers = {
                "Authorization": f"Bearer {config.openrouter.api_key}",
                "Content-Type": "application/json",
            }

            # Use the models endpoint to verify API key
            response = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers=headers
            )
            response.raise_for_status()

            data = response.json()
            model_count = len(data.get("data", []))

            # Check if the configured model exists
            model_ids = [m["id"] for m in data.get("data", [])]
            evaluator_model = config.openrouter.default_model

            if evaluator_model in model_ids:
                return True, f"OpenRouter connected. Evaluator model: {evaluator_model}"
            else:
                # Model not found, suggest alternatives
                return False, f"Model '{evaluator_model}' not found. Available: {model_count} models"

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return False, "Invalid OpenRouter API key"
        return False, f"OpenRouter HTTP error: {e.response.status_code}"
    except httpx.ConnectError:
        return False, "Cannot connect to OpenRouter API"
    except Exception as e:
        return False, f"OpenRouter connection test failed: {e}"


async def get_recommended_evaluator_models() -> list[dict]:
    """
    Get list of recommended models for evaluation.

    Returns:
        List of model info dicts
    """
    return [
        {
            "id": "anthropic/claude-3.5-sonnet",
            "name": "Claude 3.5 Sonnet",
            "description": "Excellent linguistic judgment, recommended for quality evaluation",
            "cost_tier": "premium"
        },
        {
            "id": "openai/gpt-4o",
            "name": "GPT-4o",
            "description": "Strong multilingual evaluation capabilities",
            "cost_tier": "premium"
        },
        {
            "id": "google/gemini-pro-1.5",
            "name": "Gemini Pro 1.5",
            "description": "Good quality at lower cost",
            "cost_tier": "standard"
        },
        {
            "id": "anthropic/claude-3-haiku",
            "name": "Claude 3 Haiku",
            "description": "Fast and economical option",
            "cost_tier": "economy"
        },
    ]
