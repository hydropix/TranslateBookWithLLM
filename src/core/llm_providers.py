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
    TRANSLATE_TAG_IN, TRANSLATE_TAG_OUT
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
    async def generate(self, prompt: str, timeout: int = REQUEST_TIMEOUT) -> Optional[str]:
        """Generate text from prompt"""
        pass
    
    def extract_translation(self, response: str) -> Optional[str]:
        """
        Extract translation from response using configured tags with strict validation.

        Returns the content between TRANSLATE_TAG_IN and TRANSLATE_TAG_OUT.
        Prefers responses where tags are at exact boundaries for better reliability.
        """
        if not response:
            return None

        # Trim whitespace from response
        response = response.strip()

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
    
    async def generate(self, prompt: str, timeout: int = REQUEST_TIMEOUT) -> Optional[str]:
        """Generate text using Ollama API"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {
                "num_ctx": self.context_window,
                "truncate": False  # Detect context overflow instead of silent truncation
            }
        }
        
        client = await self._get_client()
        for attempt in range(MAX_TRANSLATION_ATTEMPTS):
            try:
                # print(f"Ollama API Request to {self.api_endpoint} with model {self.model}")
                response = await client.post(
                    self.api_endpoint, 
                    json=payload, 
                    timeout=timeout
                )
                response.raise_for_status()
                
                response_json = response.json()
                response_text = response_json.get("response", "")
                # print(f"Ollama API Response received: {len(response_text)} characters")
                return response_text
                
            except httpx.TimeoutException as e:
                    print(f"Ollama API Timeout (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
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

                    # Detect context size overflow errors
                    if any(keyword in error_message.lower()
                           for keyword in ["context", "truncate", "length", "too long"]):
                        if self.log_callback:
                            self.log_callback("error",
                                f"Context size exceeded! Prompt is too large for model's context window.\n"
                                f"Error: {error_message}\n"
                                f"Consider: 1) Reducing chunk_size, or 2) Increasing OLLAMA_NUM_CTX")
                        raise ContextOverflowError(error_message)

                    print(f"Ollama API HTTP Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    return None
            except json.JSONDecodeError as e:
                    print(f"Ollama API JSON Decode Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    return None
            except Exception as e:
                    print(f"Ollama API Unknown Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
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
    
    async def generate(self, prompt: str, timeout: int = REQUEST_TIMEOUT) -> Optional[str]:
        """Generate text using an OpenAI compatible API"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
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
    
    async def generate(self, prompt: str, timeout: int = REQUEST_TIMEOUT) -> Optional[str]:
        """Generate text using Gemini API"""
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2048
            }
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
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")