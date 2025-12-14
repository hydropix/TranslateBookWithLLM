"""
LLM Provider abstraction and implementations
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable
import re
import httpx
import json
import asyncio

from src.config import (
    API_ENDPOINT, DEFAULT_MODEL, REQUEST_TIMEOUT, OLLAMA_NUM_CTX,
    MAX_TRANSLATION_ATTEMPTS, RETRY_DELAY_SECONDS,
    TRANSLATE_TAG_IN, TRANSLATE_TAG_OUT,
    OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_API_ENDPOINT
)


class ContextOverflowError(Exception):
    """Raised when prompt exceeds model's context window"""
    pass


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    def __init__(self, model: str):
        self.model = model
        self._compiled_regex = re.compile(
            rf"{re.escape(TRANSLATE_TAG_IN)}(.*?){re.escape(TRANSLATE_TAG_OUT)}",
            re.DOTALL
        )
        self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create a persistent HTTP client with connection pooling"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                timeout=httpx.Timeout(REQUEST_TIMEOUT)
            )
        return self._client

    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None

    @abstractmethod
    async def generate(self, prompt: str, timeout: int = REQUEST_TIMEOUT,
                      system_prompt: Optional[str] = None) -> Optional[str]:
        """
        Generate text from prompt.

        Args:
            prompt: The user prompt (content to process)
            timeout: Request timeout in seconds
            system_prompt: Optional system prompt (role/instructions)

        Returns:
            Generated text or None if failed
        """
        pass
    
    def extract_translation(self, response: str) -> Optional[str]:
        """
        Extract translation from response using configured tags with strict validation.

        Returns the content between TRANSLATE_TAG_IN and TRANSLATE_TAG_OUT.
        Prefers responses where tags are at exact boundaries for better reliability.

        NOTE: This method completely ignores content within <think></think> tags,
        as these are used by certain LLMs for internal reasoning and should not
        be searched for translation tags.
        """
        if not response:
            return None

        # Trim whitespace from response
        response = response.strip()
        original_length = len(response)

        # IMPORTANT: Remove all <think>...</think> blocks completely
        # These contain LLM's internal reasoning and should be completely ignored
        # Do NOT search for <Translate> tags inside these blocks!

        # Case 1: Complete <think>...</think> blocks
        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL | re.IGNORECASE)

        # Case 2: Orphan closing tag </think> (when Ollama truncates the opening tag)
        # Remove everything from the beginning up to and including </think>
        before_orphan_removal = response
        response = re.sub(r'^.*?</think>\s*', '', response, flags=re.DOTALL | re.IGNORECASE)

        if before_orphan_removal != response:
            removed_length = len(before_orphan_removal) - len(response)
            print(f"[DEBUG] Orphan </think> detected - removed {removed_length} characters from beginning")

        response = response.strip()

        if len(response) < original_length:
            print(f"[DEBUG] Think blocks removed: {original_length} -> {len(response)} chars (-{original_length - len(response)})")
            print(f"[DEBUG] Response after think removal (first 200 chars): {response[:200]}")

        # STRICT VALIDATION: Check if response starts and ends with correct tags
        starts_correctly = response.startswith(TRANSLATE_TAG_IN)
        ends_correctly = response.endswith(TRANSLATE_TAG_OUT)

        if starts_correctly and ends_correctly:
            # Perfect format - extract content between boundary tags
            content = response[len(TRANSLATE_TAG_IN):-len(TRANSLATE_TAG_OUT)]
            return content.strip()

        # FALLBACK: Try regex search for tags anywhere in response (less strict)
        match = self._compiled_regex.search(response)
        if match:
            extracted = match.group(1).strip()

            # Warn if extraction was from middle of response (indicates LLM didn't follow instructions)
            if not starts_correctly or not ends_correctly:
                print(f"⚠️  Warning: Translation tags found but not at response boundaries.")
                print(f"   Response started with tags: {starts_correctly}")
                print(f"   Response ended with tags: {ends_correctly}")
                print(f"   This may indicate the LLM added extra text. Using extracted content anyway.")

            return extracted

        # No tags found at all
        return None
    
    async def translate_text(self, prompt: str) -> Optional[str]:
        """Complete translation workflow: request + extraction"""
        response = await self.generate(prompt)
        if response:
            return self.extract_translation(response)
        return None


class OllamaProvider(LLMProvider):
    """Ollama API provider"""

    def __init__(self, api_endpoint: str = API_ENDPOINT, model: str = DEFAULT_MODEL,
                 context_window: int = OLLAMA_NUM_CTX, log_callback: Optional[Callable] = None):
        super().__init__(model)
        self.api_endpoint = api_endpoint
        self.context_window = context_window
        self.log_callback = log_callback

    async def generate(self, prompt: str, timeout: int = REQUEST_TIMEOUT,
                      system_prompt: Optional[str] = None) -> Optional[str]:
        """
        Generate text using Ollama API.

        Args:
            prompt: The user prompt (content to translate)
            timeout: Request timeout in seconds
            system_prompt: Optional system prompt (role/instructions)

        Returns:
            Generated text or None if failed
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": self.context_window,
                "truncate": False
            }
        }

        # Add system prompt if provided (Ollama supports 'system' field)
        if system_prompt:
            payload["system"] = system_prompt

        client = await self._get_client()
        for attempt in range(MAX_TRANSLATION_ATTEMPTS):
            try:
                response = await client.post(self.api_endpoint, json=payload, timeout=timeout)
                response.raise_for_status()
                response_json = response.json()
                return response_json.get("response", "")

            except httpx.TimeoutException:
                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
                return None
            except httpx.HTTPStatusError as e:
                error_message = str(e)
                if e.response:
                    try:
                        error_data = e.response.json()
                        error_message = error_data.get("error", str(e))
                    except:
                        pass

                if any(keyword in error_message.lower()
                       for keyword in ["context", "truncate", "length", "too long"]):
                    if self.log_callback:
                        self.log_callback("error",
                            f"Context size exceeded! Prompt is too large for model's context window.\n"
                            f"Error: {error_message}\n"
                            f"Consider: 1) Reducing chunk_size, or 2) Increasing OLLAMA_NUM_CTX")
                    raise ContextOverflowError(error_message)

                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
                return None
            except (json.JSONDecodeError, Exception):
                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
                return None

        return None

    async def get_model_context_size(self) -> int:
        """
        Query Ollama API to get the model's context size.

        Returns:
            int: Maximum context size in tokens
        """
        try:
            client = await self._get_client()
            show_endpoint = self.api_endpoint.replace('/api/generate', '/api/show')

            response = await client.post(
                show_endpoint,
                json={"name": self.model},
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()

            # Parse modelfile and parameters to find num_ctx
            modelfile = data.get("modelfile", "")
            parameters = data.get("parameters", "")
            combined = modelfile + "\n" + parameters

            # Look for PARAMETER num_ctx or num_ctx in parameters
            match = re.search(r'num_ctx[\s"]+(\d+)', combined, re.IGNORECASE)
            if match:
                detected_ctx = int(match.group(1))
                if self.log_callback:
                    self.log_callback("info", f"Detected model context size: {detected_ctx} tokens")
                return detected_ctx

            # Default values by model family
            model_family_defaults = {
                "llama": 4096,
                "mistral": 8192,
                "gemma": 8192,
                "phi": 2048,
                "qwen": 8192,
            }

            model_lower = self.model.lower()
            for family, default_ctx in model_family_defaults.items():
                if family in model_lower:
                    if self.log_callback:
                        self.log_callback("info",
                            f"Using default context size for {family}: {default_ctx} tokens")
                    return default_ctx

            # Conservative fallback
            if self.log_callback:
                self.log_callback("warning",
                    "Could not detect model context size, using default: 2048 tokens")
            return 2048

        except Exception as e:
            if self.log_callback:
                self.log_callback("warning",
                    f"Failed to query model context size: {e}. Using configured value.")
            return self.context_window


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI compatible API provider"""

    def __init__(self, api_endpoint: str, model: str, api_key: Optional[str] = None):
        super().__init__(model)
        self.api_endpoint = api_endpoint
        self.api_key = api_key

    async def generate(self, prompt: str, timeout: int = REQUEST_TIMEOUT,
                      system_prompt: Optional[str] = None) -> Optional[str]:
        """
        Generate text using an OpenAI compatible API.

        Args:
            prompt: The user prompt (content to translate)
            timeout: Request timeout in seconds
            system_prompt: Optional system prompt (role/instructions)

        Returns:
            Generated text or None if failed
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
                return response_text

            except httpx.TimeoutException as e:
                    print(f"OpenAI API Timeout (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    return None
            except httpx.HTTPStatusError as e:
                    print(f"OpenAI API HTTP Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if hasattr(e, 'response') and hasattr(e.response, 'text'):
                        print(f"Response details: Status {e.response.status_code}, Body: {e.response.text[:500]}...")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    return None
            except json.JSONDecodeError as e:
                    print(f"OpenAI API JSON Decode Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    return None
            except Exception as e:
                    print(f"OpenAI API Unknown Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    return None

        return None


class OpenRouterProvider(LLMProvider):
    """OpenRouter API provider with cost tracking and model validation"""

    # OpenRouter API endpoints
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    MODELS_URL = "https://openrouter.ai/api/v1/models"

    # Session cost tracking (class-level)
    _session_cost = 0.0
    _session_tokens = {"prompt": 0, "completion": 0}
    _cost_callback: Optional[Callable[[Dict[str, Any]], None]] = None

    # Fallback text-only models (sorted by cost, cheapest first)
    FALLBACK_MODELS = [
        # === FREE/CHEAP MODELS ===
        "google/gemini-2.0-flash-exp:free",
        "google/gemini-2.0-flash-001",
        "meta-llama/llama-3.3-70b-instruct",
        "qwen/qwen-2.5-72b-instruct",
        "mistralai/mistral-small-24b-instruct-2501",
        # === MID-TIER MODELS ===
        "anthropic/claude-3-5-haiku-20241022",
        "openai/gpt-4o-mini",
        "google/gemini-1.5-pro",
        "deepseek/deepseek-chat",
        # === PREMIUM MODELS ===
        "anthropic/claude-sonnet-4",
        "openai/gpt-4o",
        "anthropic/claude-3-5-sonnet-20241022",
    ]

    def __init__(self, api_key: str, model: str = "anthropic/claude-sonnet-4"):
        super().__init__(model)
        self.api_key = api_key

    @classmethod
    def get_session_cost(cls) -> tuple:
        """Get the current session cost and token usage.

        Returns:
            Tuple of (total_cost_usd, token_counts_dict)
        """
        return cls._session_cost, cls._session_tokens.copy()

    @classmethod
    def reset_session_cost(cls) -> None:
        """Reset the session cost tracking."""
        cls._session_cost = 0.0
        cls._session_tokens = {"prompt": 0, "completion": 0}

    @classmethod
    def set_cost_callback(cls, callback: Optional[Callable[[Dict[str, Any]], None]]) -> None:
        """Set a callback to receive cost updates after each API call.

        Args:
            callback: Function that receives a dict with:
                - request_cost: Cost of this specific request (USD)
                - session_cost: Cumulative session cost (USD)
                - prompt_tokens: Tokens used for this request's prompt
                - completion_tokens: Tokens generated in this request
                - total_prompt_tokens: Cumulative prompt tokens
                - total_completion_tokens: Cumulative completion tokens
        """
        cls._cost_callback = callback

    async def get_available_models(self, text_only: bool = True) -> list:
        """Fetch available OpenRouter models from API.

        Args:
            text_only: If True, filter out vision/multimodal models (default: True)

        Returns:
            List of model dicts with id, name, pricing info, sorted by price
        """
        if not self.api_key:
            return self._get_fallback_models()

        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            client = await self._get_client()

            response = await client.get(
                self.MODELS_URL,
                headers=headers,
                timeout=15
            )
            response.raise_for_status()

            models_data = response.json().get("data", [])
            filtered_models = []

            for model in models_data:
                model_id = model.get("id", "")
                architecture = model.get("architecture", {})
                modality = architecture.get("modality", "")

                # Filter logic for text-only models
                if text_only:
                    # Skip multimodal/vision models
                    if modality == "multimodal":
                        continue
                    # Skip models with vision keywords
                    model_id_lower = model_id.lower()
                    vision_keywords = ["vision", "vl", "-v-", "image"]
                    if any(kw in model_id_lower for kw in vision_keywords):
                        continue

                # Get pricing info
                pricing = model.get("pricing", {})
                prompt_price = float(pricing.get("prompt", "0") or "0")
                completion_price = float(pricing.get("completion", "0") or "0")

                # Calculate cost per 1M tokens for display
                prompt_per_million = prompt_price * 1_000_000
                completion_per_million = completion_price * 1_000_000

                filtered_models.append({
                    "id": model_id,
                    "name": model.get("name", model_id),
                    "context_length": model.get("context_length", 0),
                    "pricing": {
                        "prompt": prompt_price,
                        "completion": completion_price,
                        "prompt_per_million": prompt_per_million,
                        "completion_per_million": completion_per_million,
                    },
                    "total_price": prompt_price + completion_price,  # For sorting
                })

            # Sort by total price (cheapest first), free models at top
            filtered_models.sort(key=lambda x: x["total_price"])

            if len(filtered_models) < 5:
                return self._get_fallback_models()

            return filtered_models

        except Exception as e:
            print(f"⚠️ Failed to fetch OpenRouter models: {e}")
            return self._get_fallback_models()

    def _get_fallback_models(self) -> list:
        """Return fallback models list when API fetch fails."""
        return [{"id": m, "name": m, "pricing": {"prompt": 0, "completion": 0}}
                for m in self.FALLBACK_MODELS]

    async def generate(self, prompt: str, timeout: int = REQUEST_TIMEOUT,
                      system_prompt: Optional[str] = None) -> Optional[str]:
        """
        Generate text using OpenRouter API with cost tracking.

        Args:
            prompt: The user prompt (content to translate)
            timeout: Request timeout in seconds
            system_prompt: Optional system prompt (role/instructions)

        Returns:
            Generated text or None if failed
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/hydropix/TranslateBookWithLLM",
            "X-Title": "TranslateBookWithLLM",
        }

        # Build messages array
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        client = await self._get_client()
        for attempt in range(MAX_TRANSLATION_ATTEMPTS):
            try:
                response = await client.post(
                    self.API_URL,
                    headers=headers,
                    json=payload,
                    timeout=timeout
                )
                response.raise_for_status()

                result = response.json()

                if "choices" not in result or len(result["choices"]) == 0:
                    print(f"⚠️ OpenRouter: Unexpected response format: {result}")
                    return None

                response_text = result["choices"][0].get("message", {}).get("content", "")

                # Track cost from usage data
                usage = result.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)

                # OpenRouter returns cost in the response (in USD)
                if "cost" in result:
                    cost = float(result.get("cost", 0))
                else:
                    # Fallback estimate (using typical rates)
                    cost = (prompt_tokens * 0.50 / 1_000_000) + (completion_tokens * 1.50 / 1_000_000)

                # Update session tracking
                OpenRouterProvider._session_cost += cost
                OpenRouterProvider._session_tokens["prompt"] += prompt_tokens
                OpenRouterProvider._session_tokens["completion"] += completion_tokens

                # Log cost info
                print(f"💰 OpenRouter: {prompt_tokens}+{completion_tokens} tokens | "
                      f"Cost: ${cost:.6f} (session: ${OpenRouterProvider._session_cost:.4f})")

                # Call cost callback if set
                if OpenRouterProvider._cost_callback:
                    try:
                        OpenRouterProvider._cost_callback({
                            "request_cost": cost,
                            "session_cost": OpenRouterProvider._session_cost,
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_prompt_tokens": OpenRouterProvider._session_tokens["prompt"],
                            "total_completion_tokens": OpenRouterProvider._session_tokens["completion"],
                        })
                    except Exception as cb_err:
                        print(f"⚠️ Cost callback error: {cb_err}")

                return response_text

            except httpx.TimeoutException as e:
                print(f"OpenRouter API Timeout (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
                return None
            except httpx.HTTPStatusError as e:
                error_body = ""
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    error_body = e.response.text[:500]

                # Parse OpenRouter specific error messages
                if e.response.status_code == 404:
                    print(f"❌ OpenRouter: Model '{self.model}' not found!")
                    print(f"   Check available models at https://openrouter.ai/models")
                    print(f"   Response: {error_body}")
                elif e.response.status_code == 401:
                    print(f"❌ OpenRouter: Invalid API key!")
                elif e.response.status_code == 402:
                    print(f"❌ OpenRouter: Insufficient credits!")
                else:
                    print(f"OpenRouter API HTTP Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    print(f"Response details: Status {e.response.status_code}, Body: {error_body}...")

                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
                return None
            except json.JSONDecodeError as e:
                print(f"OpenRouter API JSON Decode Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
                return None
            except Exception as e:
                print(f"OpenRouter API Unknown Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
                return None

        return None


class GeminiProvider(LLMProvider):
    """Google Gemini API provider"""
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        super().__init__(model)
        self.api_key = api_key
        self.api_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    
    async def get_available_models(self) -> list[dict]:
        """Fetch available Gemini models from API, excluding thinking models"""
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
                
                # Skip thinking, experimental, latest, and vision models
                model_name_lower = model_name.lower()
                skip_keywords = ["thinking", "experimental", "latest", "vision", "-exp-"]
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
                      system_prompt: Optional[str] = None) -> Optional[str]:
        """
        Generate text using Gemini API.

        Args:
            prompt: The user prompt (content to translate)
            timeout: Request timeout in seconds
            system_prompt: Optional system prompt (role/instructions)

        Returns:
            Generated text or None if failed
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
        
        # Debug logs removed - uncomment if needed for troubleshooting
        # print(f"[DEBUG] Gemini API URL: {self.api_endpoint}")
        # print(f"[DEBUG] Using API key: {self.api_key[:10]}...{self.api_key[-4:]}")
        
        client = await self._get_client()
        for attempt in range(MAX_TRANSLATION_ATTEMPTS):
            try:
                # print(f"Gemini API Request to {self.api_endpoint}")
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
                
                # print(f"Gemini API Response received: {len(response_text)} characters")
                return response_text
                
            except httpx.TimeoutException as e:
                    print(f"Gemini API Timeout (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    return None
            except httpx.HTTPStatusError as e:
                    print(f"Gemini API HTTP Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if hasattr(e, 'response') and hasattr(e.response, 'text'):
                        print(f"Response details: Status {e.response.status_code}, Body: {e.response.text[:200]}...")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    return None
            except json.JSONDecodeError as e:
                    print(f"Gemini API JSON Decode Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    return None
            except Exception as e:
                    print(f"Gemini API Unknown Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    return None
                    
        return None


def create_llm_provider(provider_type: str = "ollama", **kwargs) -> LLMProvider:
    """Factory function to create LLM providers"""
    # Auto-detect provider from model name if not explicitly set
    model = kwargs.get("model", DEFAULT_MODEL)
    if provider_type == "ollama" and model and model.startswith("gemini"):
        # Auto-switch to Gemini provider when Gemini model is detected
        # print(f"[INFO] Auto-switching to Gemini provider for model '{model}'")
        provider_type = "gemini"

    if provider_type.lower() == "ollama":
        return OllamaProvider(
            api_endpoint=kwargs.get("api_endpoint", API_ENDPOINT),
            model=kwargs.get("model", DEFAULT_MODEL)
        )
    elif provider_type.lower() == "openai":
        return OpenAICompatibleProvider(
            api_endpoint=kwargs.get("api_endpoint"),
            model=kwargs.get("model", DEFAULT_MODEL),
            api_key=kwargs.get("api_key")
        )
    elif provider_type.lower() == "gemini":
        api_key = kwargs.get("api_key")
        if not api_key:
            # Try to get from environment
            import os
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("Gemini provider requires an API key. Set GEMINI_API_KEY environment variable or pass api_key parameter.")
        return GeminiProvider(
            api_key=api_key,
            model=kwargs.get("model", "gemini-2.0-flash")
        )
    elif provider_type.lower() == "openrouter":
        api_key = kwargs.get("api_key")
        if not api_key:
            # Try to get from environment
            import os
            api_key = os.getenv("OPENROUTER_API_KEY", OPENROUTER_API_KEY)
            if not api_key:
                raise ValueError("OpenRouter provider requires an API key. Set OPENROUTER_API_KEY environment variable or pass api_key parameter.")
        return OpenRouterProvider(
            api_key=api_key,
            model=kwargs.get("model", OPENROUTER_MODEL)
        )
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")