"""
TTS (Text-to-Speech) Configuration Module

Provides centralized configuration for TTS generation including
provider selection, voice settings, and audio encoding options.
"""
import os
from dataclasses import dataclass, field
from typing import Optional, Dict

# Default voice mappings by language code
# These are high-quality neural voices from Edge-TTS
DEFAULT_VOICES: Dict[str, str] = {
    # Chinese
    "chinese": "zh-CN-XiaoxiaoNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "zh-cn": "zh-CN-XiaoxiaoNeural",
    "zh-tw": "zh-TW-HsiaoChenNeural",

    # English
    "english": "en-US-AriaNeural",
    "en": "en-US-AriaNeural",
    "en-us": "en-US-AriaNeural",
    "en-gb": "en-GB-SoniaNeural",

    # French
    "french": "fr-FR-DeniseNeural",
    "fr": "fr-FR-DeniseNeural",

    # German
    "german": "de-DE-KatjaNeural",
    "de": "de-DE-KatjaNeural",

    # Spanish
    "spanish": "es-ES-ElviraNeural",
    "es": "es-ES-ElviraNeural",

    # Italian
    "italian": "it-IT-ElsaNeural",
    "it": "it-IT-ElsaNeural",

    # Japanese
    "japanese": "ja-JP-NanamiNeural",
    "ja": "ja-JP-NanamiNeural",

    # Korean
    "korean": "ko-KR-SunHiNeural",
    "ko": "ko-KR-SunHiNeural",

    # Portuguese
    "portuguese": "pt-BR-FranciscaNeural",
    "pt": "pt-BR-FranciscaNeural",
    "pt-br": "pt-BR-FranciscaNeural",
    "pt-pt": "pt-PT-RaquelNeural",

    # Russian
    "russian": "ru-RU-SvetlanaNeural",
    "ru": "ru-RU-SvetlanaNeural",

    # Arabic
    "arabic": "ar-SA-ZariyahNeural",
    "ar": "ar-SA-ZariyahNeural",

    # Hindi
    "hindi": "hi-IN-SwaraNeural",
    "hi": "hi-IN-SwaraNeural",
}

# Load TTS settings from environment
TTS_ENABLED = os.getenv('TTS_ENABLED', 'false').lower() == 'true'
TTS_PROVIDER = os.getenv('TTS_PROVIDER', 'edge-tts')
TTS_VOICE = os.getenv('TTS_VOICE', '')  # Empty = auto-select based on language
TTS_RATE = os.getenv('TTS_RATE', '+0%')  # Speed adjustment: -50% to +100%
TTS_VOLUME = os.getenv('TTS_VOLUME', '+0%')  # Volume adjustment: -50% to +50%
TTS_PITCH = os.getenv('TTS_PITCH', '+0Hz')  # Pitch adjustment

# Audio encoding settings
TTS_OUTPUT_FORMAT = os.getenv('TTS_OUTPUT_FORMAT', 'opus')  # opus, mp3, wav
TTS_BITRATE = os.getenv('TTS_BITRATE', '64k')  # For opus/mp3 encoding
TTS_SAMPLE_RATE = int(os.getenv('TTS_SAMPLE_RATE', '24000'))  # Hz

# Chunking settings for TTS
TTS_CHUNK_SIZE = int(os.getenv('TTS_CHUNK_SIZE', '5000'))  # Max chars per TTS chunk
TTS_PAUSE_BETWEEN_CHUNKS = float(os.getenv('TTS_PAUSE_BETWEEN_CHUNKS', '0.5'))  # Seconds


def get_voice_for_language(language: str) -> str:
    """
    Get the default voice for a given language.

    Args:
        language: Language name or code (e.g., 'Chinese', 'zh', 'en-US')

    Returns:
        Voice name for Edge-TTS, or empty string if not found
    """
    normalized = language.lower().strip()
    return DEFAULT_VOICES.get(normalized, '')


@dataclass
class TTSConfig:
    """Configuration for TTS generation"""

    # Core settings
    enabled: bool = TTS_ENABLED
    provider: str = TTS_PROVIDER

    # Voice settings
    voice: str = TTS_VOICE
    rate: str = TTS_RATE
    volume: str = TTS_VOLUME
    pitch: str = TTS_PITCH

    # Output settings
    output_format: str = TTS_OUTPUT_FORMAT
    bitrate: str = TTS_BITRATE
    sample_rate: int = TTS_SAMPLE_RATE

    # Processing settings
    chunk_size: int = TTS_CHUNK_SIZE
    pause_between_chunks: float = TTS_PAUSE_BETWEEN_CHUNKS

    # Runtime settings (set during execution)
    target_language: str = ''
    output_path: Optional[str] = None

    @classmethod
    def from_cli_args(cls, args) -> 'TTSConfig':
        """Create config from CLI arguments"""
        config = cls(
            enabled=getattr(args, 'tts', False),
            voice=getattr(args, 'tts_voice', '') or TTS_VOICE,
            rate=getattr(args, 'tts_rate', None) or TTS_RATE,
            bitrate=getattr(args, 'tts_bitrate', None) or TTS_BITRATE,
            output_format=getattr(args, 'tts_format', None) or TTS_OUTPUT_FORMAT,
        )
        return config

    @classmethod
    def from_env(cls) -> 'TTSConfig':
        """Create config from environment variables only"""
        return cls()

    @classmethod
    def from_web_request(cls, request_data: dict) -> 'TTSConfig':
        """Create config from web request data"""
        return cls(
            enabled=request_data.get('tts_enabled', False),
            voice=request_data.get('tts_voice', '') or TTS_VOICE,
            rate=request_data.get('tts_rate', TTS_RATE),
            volume=request_data.get('tts_volume', TTS_VOLUME),
            bitrate=request_data.get('tts_bitrate', TTS_BITRATE),
            output_format=request_data.get('tts_format', TTS_OUTPUT_FORMAT),
        )

    def get_effective_voice(self, language: str = '') -> str:
        """
        Get the voice to use, auto-selecting if not specified.

        Args:
            language: Target language for auto-selection

        Returns:
            Voice name to use
        """
        if self.voice:
            return self.voice

        lang = language or self.target_language
        if lang:
            auto_voice = get_voice_for_language(lang)
            if auto_voice:
                return auto_voice

        # Fallback to English
        return DEFAULT_VOICES['english']

    def get_output_extension(self) -> str:
        """Get file extension for the output format"""
        format_extensions = {
            'opus': '.opus',
            'mp3': '.mp3',
            'wav': '.wav',
            'ogg': '.ogg',
        }
        return format_extensions.get(self.output_format.lower(), '.opus')

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'enabled': self.enabled,
            'provider': self.provider,
            'voice': self.voice,
            'rate': self.rate,
            'volume': self.volume,
            'pitch': self.pitch,
            'output_format': self.output_format,
            'bitrate': self.bitrate,
            'sample_rate': self.sample_rate,
            'chunk_size': self.chunk_size,
            'pause_between_chunks': self.pause_between_chunks,
            'target_language': self.target_language,
        }
