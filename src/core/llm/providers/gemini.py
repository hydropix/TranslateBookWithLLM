"""
Google Gemini provider implementation.

This module provides the GeminiProvider class for interacting with
Google's Gemini API.

Features:
    - Gemini 2.0 Flash and other models
    - Large context windows
    - Efficient batch processing
"""

from typing import Optional
import httpx
import asyncio

from src.config import REQUEST_TIMEOUT, MAX_TRANSLATION_ATTEMPTS
from ..base import LLMProvider, LLMResponse
from ..exceptions import ContextOverflowError


class GeminiProvider(LLMProvider):
    """
    Provider for Google Gemini API.

    Supports Gemini models including:
        - gemini-2.0-flash-exp
        - gemini-1.5-pro
        - gemini-1.5-flash

    Features:
        - Large context windows (up to 2M tokens for some models)
        - Fast response times
        - Good for batch translation

    Configuration:
        api_key: Google AI API key (required)
        model: Gemini model name

    Example:
        >>> provider = GeminiProvider(
        ...     api_key="AI...",
        ...     model="gemini-2.0-flash-exp"
        ... )
        >>> response = await provider.generate("Translate: Hello")
    """

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        """
        Initialize the Gemini provider.

        Args:
            api_key: Google AI API key
            model: Gemini model name (default: gemini-2.0-flash)
        """
        super().__init__(model)
        self.api_key = api_key
        self.api_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    async def get_available_models(self) -> list[dict]:
        """
        Fetch available Gemini models from API, excluding experimental/vision models.

        Returns:
            List of model dictionaries with name, displayName, description, and token limits
        """
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }

        models_endpoint = "https://generativelanguage.googleapis.com/v1beta/models"

        client = await self._get_client()
        try:
            response = await client.get(
                models_endpoint,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            models = []

            for model in data.get("models", []):
                model_name = model.get("name", "").replace("models/", "")

                # Skip experimental, latest, and vision models
                model_name_lower = model_name.lower()
                skip_keywords = ["experimental", "latest", "vision", "-exp-"]
                if any(keyword in model_name_lower for keyword in skip_keywords):
                    continue

                # Only include models that support generateContent
                supported_methods = model.get("supportedGenerationMethods", [])
                if "generateContent" in supported_methods:
                    models.append({
                        "name": model_name,
                        "displayName": model.get("displayName", model_name),
                        "description": model.get("description", ""),
                        "inputTokenLimit": model.get("inputTokenLimit", 0),
                        "outputTokenLimit": model.get("outputTokenLimit", 0)
                    })

            return models

        except Exception as e:
            print(f"Error fetching Gemini models: {e}")
            return []

    async def generate(self, prompt: str, timeout: int = REQUEST_TIMEOUT,
                      system_prompt: Optional[str] = None) -> Optional[LLMResponse]:
        """
        Generate text using Gemini API.

        Args:
            prompt: The user prompt (content to translate)
            timeout: Request timeout in seconds
            system_prompt: Optional system prompt (role/instructions)

        Returns:
            LLMResponse with content and token usage info, or None if failed

        Raises:
            ContextOverflowError: If input exceeds Gemini's context window
        """
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }

        payload = {
            "contents": [{
                "role": "user",
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2048
            }
        }

        # Add system instruction if provided (Gemini API supports systemInstruction field)
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{
                    "text": system_prompt
                }]
            }

        client = await self._get_client()
        for attempt in range(MAX_TRANSLATION_ATTEMPTS):
            try:
                response = await client.post(
                    self.api_endpoint,
                    headers=headers,
                    json=payload,
                    timeout=timeout
                )
                response.raise_for_status()

                response_json = response.json()
                # Extract text from Gemini response structure
                response_text = ""
                if "candidates" in response_json and response_json["candidates"]:
                    content = response_json["candidates"][0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        response_text = parts[0].get("text", "")

                # Extract token usage if available
                usage_metadata = response_json.get("usageMetadata", {})
                prompt_tokens = usage_metadata.get("promptTokenCount", 0)
                completion_tokens = usage_metadata.get("candidatesTokenCount", 0)

                return LLMResponse(
                    content=response_text,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    context_used=prompt_tokens + completion_tokens,
                    context_limit=0,  # Gemini manages context internally
                    was_truncated=False
                )

            except httpx.TimeoutException as e:
                    print(f"Gemini API Timeout (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(2)
                        continue
                    return None
            except httpx.HTTPStatusError as e:
                    error_message = str(e)
                    error_body = ""
                    if hasattr(e, 'response') and hasattr(e.response, 'text'):
                        error_body = e.response.text[:500]
                        error_message = f"{e} - {error_body}"

                    print(f"Gemini API HTTP Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if error_body:
                        print(f"Response details: Status {e.response.status_code}, Body: {error_body[:200]}...")

                    # Detect context overflow errors (Gemini uses "RESOURCE_EXHAUSTED" or token limits)
                    context_overflow_keywords = ["resource_exhausted", "token limit", "input too long",
                                                  "maximum input", "context length", "too many tokens"]
                    if any(keyword in error_message.lower() for keyword in context_overflow_keywords):
                        raise ContextOverflowError(f"Gemini context overflow: {error_message}")

                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(2)
                        continue
                    return None
            except Exception as e:
                    print(f"Gemini API Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(2)
                        continue
                    return None

        return None
