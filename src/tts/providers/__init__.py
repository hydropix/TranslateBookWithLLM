"""
TTS Providers Package

Factory functions for creating TTS provider instances.
"""
from .base import TTSProvider, TTSResult, VoiceInfo, TTSError, ProgressCallback
from .edge_tts import EdgeTTSProvider, create_edge_tts_provider

__all__ = [
    # Base classes
    'TTSProvider',
    'TTSResult',
    'VoiceInfo',
    'TTSError',
    'ProgressCallback',
    # Edge-TTS
    'EdgeTTSProvider',
    'create_edge_tts_provider',
]


def create_provider(provider_name: str = "edge-tts") -> TTSProvider:
    """
    Factory function to create a TTS provider by name.

    Args:
        provider_name: Name of the provider ("edge-tts")

    Returns:
        TTSProvider instance

    Raises:
        ValueError: If provider is not supported
    """
    providers = {
        "edge-tts": create_edge_tts_provider,
    }

    if provider_name not in providers:
        available = ", ".join(providers.keys())
        raise ValueError(f"Unknown TTS provider: {provider_name}. Available: {available}")

    return providers[provider_name]()
