"""
TTS Providers Package

Factory functions for creating TTS provider instances.
"""
from .base import TTSProvider, TTSResult, VoiceInfo, TTSError, ProgressCallback
from .edge_tts import EdgeTTSProvider, create_edge_tts_provider
from .chatterbox_tts import (
    ChatterboxProvider,
    create_chatterbox_provider,
    is_chatterbox_available,
    get_gpu_status,
    CHATTERBOX_LANGUAGES,
    MAX_TEXT_LENGTH as CHATTERBOX_MAX_TEXT_LENGTH,
    sanitize_text_for_tts,
)

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
    # Chatterbox TTS
    'ChatterboxProvider',
    'create_chatterbox_provider',
    'is_chatterbox_available',
    'get_gpu_status',
    'CHATTERBOX_LANGUAGES',
    'CHATTERBOX_MAX_TEXT_LENGTH',
    'sanitize_text_for_tts',
]


def create_provider(provider_name: str = "edge-tts", **kwargs) -> TTSProvider:
    """
    Factory function to create a TTS provider by name.

    Args:
        provider_name: Name of the provider ("edge-tts", "chatterbox")
        **kwargs: Additional arguments passed to provider constructor
            - For chatterbox: voice_prompt_path, exaggeration, cfg_weight

    Returns:
        TTSProvider instance

    Raises:
        ValueError: If provider is not supported
    """
    if provider_name == "edge-tts":
        return create_edge_tts_provider()

    elif provider_name == "chatterbox":
        return create_chatterbox_provider(
            voice_prompt_path=kwargs.get('voice_prompt_path'),
            exaggeration=kwargs.get('exaggeration', 0.5),
            cfg_weight=kwargs.get('cfg_weight', 0.5)
        )

    else:
        available = "edge-tts, chatterbox"
        raise ValueError(f"Unknown TTS provider: {provider_name}. Available: {available}")
