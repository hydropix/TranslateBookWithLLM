"""
Centralized LLM client for all API communication
"""
from typing import Optional, Dict, Any

from src.config import API_ENDPOINT, DEFAULT_MODEL
from src.core.llm_providers import create_llm_provider, LLMProvider


class LLMClient:
    """Centralized client for LLM API communication"""
    
    def __init__(self, provider_type: str = "ollama", **kwargs):
        self.provider_type = provider_type
        self.provider_kwargs = kwargs
        self._provider: Optional[LLMProvider] = None
        
        # For backward compatibility
        if "api_endpoint" in kwargs and "model" in kwargs:
            self.api_endpoint = kwargs["api_endpoint"]
            self.model = kwargs["model"]
        else:
            self.api_endpoint = API_ENDPOINT
            self.model = DEFAULT_MODEL
    
    def _get_provider(self) -> LLMProvider:
        """Get or create the LLM provider"""
        if not self._provider:
            self._provider = create_llm_provider(self.provider_type, **self.provider_kwargs)
        return self._provider
    
    async def make_request(self, prompt: str, model: Optional[str] = None,
                    timeout: int = None, system_prompt: Optional[str] = None) -> Optional[str]:
        """
        Make a request to the LLM API with error handling and retries

        Args:
            prompt: The user prompt to send (content to process)
            model: Model to use (defaults to instance model)
            timeout: Request timeout in seconds
            system_prompt: Optional system prompt (role/instructions)

        Returns:
            Raw response text or None if failed
        """
        provider = self._get_provider()

        # Update model if specified
        if model:
            provider.model = model

        if timeout:
            return await provider.generate(prompt, timeout, system_prompt=system_prompt)
        else:
            return await provider.generate(prompt, system_prompt=system_prompt)
    
    def extract_translation(self, response: str) -> Optional[str]:
        """
        Extract translation from response using configured tags
        
        Args:
            response: Raw LLM response
            
        Returns:
            Extracted translation or None if not found
        """
        provider = self._get_provider()
        return provider.extract_translation(response)
    
    async def translate_text(self, prompt: str, model: Optional[str] = None) -> Optional[str]:
        """
        Complete translation workflow: request + extraction
        
        Args:
            prompt: Translation prompt
            model: Model to use
            
        Returns:
            Extracted translation or None if failed
        """
        provider = self._get_provider()
        
        # Update model if specified
        if model:
            provider.model = model
            
        return await provider.translate_text(prompt)
    
    async def close(self):
        """Close the HTTP client and clean up resources"""
        if self._provider:
            await self._provider.close()
            self._provider = None


# Global instance for backward compatibility
default_client = LLMClient(provider_type="ollama", api_endpoint=API_ENDPOINT, model=DEFAULT_MODEL)


def create_llm_client(llm_provider: str, gemini_api_key: Optional[str],
                      api_endpoint: str, model_name: str,
                      openai_api_key: Optional[str] = None) -> Optional[LLMClient]:
    """
    Factory function to create LLM client based on provider or custom endpoint

    Args:
        llm_provider: Provider type ('ollama', 'gemini', or 'openai')
        gemini_api_key: API key for Gemini provider
        api_endpoint: API endpoint for custom Ollama instance or OpenAI-compatible API
        model_name: Model name to use
        openai_api_key: API key for OpenAI provider

    Returns:
        LLMClient instance or None if using default client
    """
    if llm_provider == "gemini" and gemini_api_key:
        return LLMClient(provider_type="gemini", api_key=gemini_api_key, model=model_name)
    if llm_provider == "openai":
        return LLMClient(provider_type="openai", api_endpoint=api_endpoint, model=model_name, api_key=openai_api_key)
    if llm_provider == "ollama":
        # Always create a new client for Ollama to ensure proper configuration
        return LLMClient(provider_type="ollama", api_endpoint=api_endpoint, model=model_name)
    return None