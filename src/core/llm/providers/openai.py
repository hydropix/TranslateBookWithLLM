"""
OpenAI-compatible provider implementation.

This module provides the OpenAICompatibleProvider class for interacting with
OpenAI API and compatible endpoints (llama.cpp, LM Studio, vLLM, OpenAI, etc.).
"""

from typing import Optional, Callable
import asyncio
import json
import httpx

from ..base import LLMProvider, LLMResponse
from ..exceptions import ContextOverflowError
from ..utils.context_detection import ContextDetector

from src.config import (
    REQUEST_TIMEOUT,
    OLLAMA_NUM_CTX,
    MAX_TRANSLATION_ATTEMPTS
)


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI-compatible API provider (works with llama.cpp, LM Studio, vLLM, OpenAI, etc.)"""

    def __init__(self, api_endpoint: str, model: str, api_key: Optional[str] = None,
                 context_window: int = OLLAMA_NUM_CTX, log_callback: Optional[Callable] = None):
        super().__init__(model)
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.context_window = context_window
        self.log_callback = log_callback
        self._detected_context_size: Optional[int] = None
        self._context_detector = ContextDetector()

    async def generate(self, prompt: str, timeout: int = REQUEST_TIMEOUT,
                      system_prompt: Optional[str] = None) -> Optional[LLMResponse]:
        """
        Generate text using an OpenAI compatible API.

        Args:
            prompt: The user prompt (content to translate)
            timeout: Request timeout in seconds
            system_prompt: Optional system prompt (role/instructions)

        Returns:
            LLMResponse with content and token usage info, or None if failed
        """
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Build messages array with optional system prompt
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            # Disable thinking/reasoning mode for local servers and compatible APIs
            # This prevents models from outputting <think>...</think> blocks
            "thinking": False,
            "enable_thinking": False,
            # Some servers use chat_template_kwargs
            "chat_template_kwargs": {
                "enable_thinking": False
            }
        }

        client = await self._get_client()
        for attempt in range(MAX_TRANSLATION_ATTEMPTS):
            try:
                response = await client.post(
                    self.api_endpoint,
                    json=payload,
                    headers=headers,
                    timeout=timeout
                )
                response.raise_for_status()

                response_json = response.json()
                response_text = response_json.get("choices", [{}])[0].get("message", {}).get("content", "")

                # Extract token usage if available
                usage = response_json.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)

                return LLMResponse(
                    content=response_text,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    context_used=prompt_tokens + completion_tokens,
                    context_limit=self.context_window,
                    was_truncated=False  # OpenAI API doesn't provide truncation info
                )

            except httpx.TimeoutException as e:
                print(f"OpenAI-compatible API Timeout (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
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

                print(f"OpenAI-compatible API HTTP Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                if error_body:
                    print(f"Response details: Status {e.response.status_code}, Body: {error_body}...")

                # Detect context overflow errors (OpenAI-compatible APIs use "context_length_exceeded" or similar)
                context_overflow_keywords = ["context_length", "maximum context", "token limit",
                                              "too many tokens", "reduce the length", "max_tokens"]
                if any(keyword in error_message.lower() for keyword in context_overflow_keywords):
                    raise ContextOverflowError(f"Context overflow: {error_message}")

                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    await asyncio.sleep(2)
                    continue
                return None
            except json.JSONDecodeError as e:
                print(f"OpenAI-compatible API JSON Decode Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    await asyncio.sleep(2)
                    continue
                return None
            except Exception as e:
                print(f"OpenAI-compatible API Unknown Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    await asyncio.sleep(2)
                    continue
                return None

        return None

    async def get_model_context_size(self) -> int:
        """Query server to get model's context size using ContextDetector."""
        if self._detected_context_size:
            return self._detected_context_size

        client = await self._get_client()
        ctx = await self._context_detector.detect(
            client=client,
            model=self.model,
            endpoint=self.api_endpoint,
            api_key=self.api_key,
            log_callback=self.log_callback
        )

        self._detected_context_size = ctx
        return ctx
