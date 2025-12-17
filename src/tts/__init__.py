"""
TTS (Text-to-Speech) Module

Provides text-to-speech generation capabilities using Edge-TTS
with optional Opus encoding via ffmpeg.

Usage:
    from src.tts import TTSConfig, AudioProcessor, generate_tts_for_text

    # Simple usage
    success, message = await generate_tts_for_text(
        text="Hello, world!",
        output_path="output.opus",
        language="English"
    )

    # With custom config
    config = TTSConfig(
        voice="zh-CN-XiaoxiaoNeural",
        rate="+10%",
        output_format="opus"
    )
    processor = AudioProcessor(config)
    success, message = await processor.generate_audio(
        text="你好世界",
        output_path="chinese.opus",
        language="Chinese"
    )
"""
from .tts_config import (
    TTSConfig,
    DEFAULT_VOICES,
    get_voice_for_language,
    # Environment variables
    TTS_ENABLED,
    TTS_PROVIDER,
    TTS_VOICE,
    TTS_RATE,
    TTS_OUTPUT_FORMAT,
    TTS_BITRATE,
)

from .audio_processor import (
    AudioProcessor,
    create_tts_provider,
    generate_tts_for_text,
    chunk_text_for_tts,
    check_ffmpeg_available,
    check_ffmpeg_with_instructions,
    get_ffmpeg_install_instructions,
)

from .providers import (
    TTSProvider,
    TTSResult,
    VoiceInfo,
    TTSError,
    ProgressCallback,
    EdgeTTSProvider,
)

__all__ = [
    # Config
    'TTSConfig',
    'DEFAULT_VOICES',
    'get_voice_for_language',
    'TTS_ENABLED',
    'TTS_PROVIDER',
    'TTS_VOICE',
    'TTS_RATE',
    'TTS_OUTPUT_FORMAT',
    'TTS_BITRATE',
    # Processor
    'AudioProcessor',
    'create_tts_provider',
    'generate_tts_for_text',
    'chunk_text_for_tts',
    'check_ffmpeg_available',
    'check_ffmpeg_with_instructions',
    'get_ffmpeg_install_instructions',
    # Providers
    'TTSProvider',
    'TTSResult',
    'VoiceInfo',
    'TTSError',
    'ProgressCallback',
    'EdgeTTSProvider',
]
