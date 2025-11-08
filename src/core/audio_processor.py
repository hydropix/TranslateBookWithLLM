"""
Audio processor for converting translated text to audiobooks using Coqui TTS.
Supports multiple languages and voice cloning capabilities.
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import numpy as np

try:
    from TTS.api import TTS
    COQUI_AVAILABLE = True
except ImportError:
    COQUI_AVAILABLE = False
    logging.warning("Coqui TTS not installed. Audio features will be disabled.")

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from src.config import Config

logger = logging.getLogger(__name__)

@dataclass
class AudioConfig:
    """Configuration for audio generation."""
    model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    voice_sample: Optional[str] = None  # Path to voice sample for cloning
    language: str = "en"
    speed: float = 1.0
    output_format: str = "mp3"  # mp3, wav, or flac
    chapter_split: bool = True  # Split audiobook by chapters
    sample_rate: int = 24000
    
class AudioProcessor:
    """Handles text-to-speech conversion for creating audiobooks."""
    
    def __init__(self, config: Config):
        """Initialize the audio processor with configuration."""
        self.config = config
        self.tts = None
        self.audio_config = AudioConfig()
        
        if COQUI_AVAILABLE:
            self._initialize_tts()
    
    def _initialize_tts(self):
        """Initialize the Coqui TTS model."""
        try:
            # List available models
            logger.info("Initializing Coqui TTS...")
            
            # Use GPU if available
            use_cuda = torch.cuda.is_available() if TORCH_AVAILABLE else False
            
            # Initialize TTS with XTTS-v2 for best quality
            self.tts = TTS(self.audio_config.model_name, gpu=use_cuda)
            
            logger.info(f"TTS initialized with model: {self.audio_config.model_name}")
            logger.info(f"GPU acceleration: {'enabled' if use_cuda else 'disabled'}")
            
        except Exception as e:
            logger.error(f"Failed to initialize TTS: {e}")
            self.tts = None
    
    async def text_to_speech(
        self,
        text: str,
        output_path: str,
        language: Optional[str] = None,
        voice_sample: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> Optional[str]:
        """
        Convert text to speech and save as audio file.
        
        Args:
            text: Text to convert
            output_path: Path to save the audio file
            language: Target language code (e.g., 'en', 'fr', 'es')
            voice_sample: Path to voice sample for cloning
            progress_callback: Callback for progress updates
            
        Returns:
            Path to the generated audio file or None if failed
        """
        if not COQUI_AVAILABLE or not self.tts:
            logger.error("TTS not available. Please install Coqui TTS.")
            return None
        
        try:
            # Update language if provided
            if language:
                self.audio_config.language = self._map_language_code(language)
            
            # Prepare output directory
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Generate speech
            if voice_sample and Path(voice_sample).exists():
                # Use voice cloning
                logger.info(f"Generating speech with voice cloning from: {voice_sample}")
                await self._generate_with_voice_clone(
                    text, str(output_path), voice_sample, progress_callback
                )
            else:
                # Use default voice
                logger.info("Generating speech with default voice")
                await self._generate_default(
                    text, str(output_path), progress_callback
                )
            
            # Convert to desired format if needed
            final_path = await self._convert_audio_format(output_path)
            
            logger.info(f"Audio generated successfully: {final_path}")
            return str(final_path)
            
        except Exception as e:
            logger.error(f"Failed to generate speech: {e}")
            return None
    
    async def _generate_with_voice_clone(
        self,
        text: str,
        output_path: str,
        voice_sample: str,
        progress_callback: Optional[callable] = None
    ):
        """Generate speech using voice cloning."""
        # Split text into manageable chunks for better quality
        chunks = self._split_text_for_tts(text)
        total_chunks = len(chunks)
        
        # Temporary files for chunks
        chunk_files = []
        
        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress = (i + 1) / total_chunks * 100
                await progress_callback(f"Generating audio: {progress:.1f}%")
            
            chunk_file = f"{output_path}.chunk_{i}.wav"
            
            # Generate chunk with voice cloning
            await asyncio.to_thread(
                self.tts.tts_to_file,
                text=chunk,
                file_path=chunk_file,
                speaker_wav=voice_sample,
                language=self.audio_config.language,
                speed=self.audio_config.speed
            )
            
            chunk_files.append(chunk_file)
        
        # Merge all chunks
        await self._merge_audio_chunks(chunk_files, output_path)
        
        # Cleanup temporary files
        for chunk_file in chunk_files:
            try:
                os.remove(chunk_file)
            except:
                pass
    
    async def _generate_default(
        self,
        text: str,
        output_path: str,
        progress_callback: Optional[callable] = None
    ):
        """Generate speech with default voice."""
        chunks = self._split_text_for_tts(text)
        total_chunks = len(chunks)
        
        chunk_files = []
        
        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress = (i + 1) / total_chunks * 100
                await progress_callback(f"Generating audio: {progress:.1f}%")
            
            chunk_file = f"{output_path}.chunk_{i}.wav"
            
            # Generate chunk
            await asyncio.to_thread(
                self.tts.tts_to_file,
                text=chunk,
                file_path=chunk_file,
                language=self.audio_config.language,
                speed=self.audio_config.speed
            )
            
            chunk_files.append(chunk_file)
        
        # Merge all chunks
        await self._merge_audio_chunks(chunk_files, output_path)
        
        # Cleanup
        for chunk_file in chunk_files:
            try:
                os.remove(chunk_file)
            except:
                pass
    
    def _split_text_for_tts(self, text: str, max_length: int = 500) -> List[str]:
        """
        Split text into chunks suitable for TTS processing.
        Tries to split at sentence boundaries for natural speech.
        """
        # First, split by paragraphs
        paragraphs = text.split('\n\n')
        
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            # Split long paragraphs by sentences
            sentences = self._split_into_sentences(paragraph)
            
            for sentence in sentences:
                if len(current_chunk) + len(sentence) < max_length:
                    current_chunk += sentence + " "
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence + " "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting - can be improved with NLTK
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s for s in sentences if s.strip()]
    
    async def _merge_audio_chunks(self, chunk_files: List[str], output_path: str):
        """Merge multiple audio chunks into a single file."""
        try:
            from pydub import AudioSegment
            
            # Load and concatenate all chunks
            combined = AudioSegment.empty()
            
            for chunk_file in chunk_files:
                chunk = AudioSegment.from_wav(chunk_file)
                combined += chunk
            
            # Export as WAV first
            combined.export(output_path, format="wav")
            
        except ImportError:
            logger.error("pydub not installed. Cannot merge audio chunks.")
            # Fallback: just rename the first chunk
            if chunk_files:
                os.rename(chunk_files[0], output_path)
    
    async def _convert_audio_format(self, input_path: Path) -> Path:
        """Convert audio to the desired output format."""
        if self.audio_config.output_format == "wav":
            return input_path
        
        try:
            from pydub import AudioSegment
            
            # Load WAV file
            audio = AudioSegment.from_wav(str(input_path))
            
            # Prepare output path
            output_path = input_path.with_suffix(f".{self.audio_config.output_format}")
            
            # Export in desired format
            if self.audio_config.output_format == "mp3":
                audio.export(str(output_path), format="mp3", bitrate="192k")
            elif self.audio_config.output_format == "flac":
                audio.export(str(output_path), format="flac")
            else:
                # Default to MP3
                audio.export(str(output_path), format="mp3", bitrate="192k")
            
            # Remove original WAV
            input_path.unlink()
            
            return output_path
            
        except ImportError:
            logger.warning("pydub not installed. Cannot convert audio format.")
            return input_path
    
    def _map_language_code(self, language: str) -> str:
        """Map language names to Coqui TTS language codes."""
        language_map = {
            'english': 'en',
            'french': 'fr',
            'spanish': 'es',
            'german': 'de',
            'italian': 'it',
            'portuguese': 'pt',
            'polish': 'pl',
            'turkish': 'tr',
            'russian': 'ru',
            'dutch': 'nl',
            'czech': 'cs',
            'arabic': 'ar',
            'chinese': 'zh-cn',
            'japanese': 'ja',
            'hungarian': 'hu',
            'korean': 'ko',
            'hindi': 'hi'
        }
        
        # Check if already a code
        if len(language) == 2:
            return language.lower()
        
        # Map from full name
        return language_map.get(language.lower(), 'en')
    
    async def process_epub_to_audiobook(
        self,
        epub_content: Dict[str, str],
        output_dir: str,
        language: str = "en",
        voice_sample: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> List[str]:
        """
        Convert an EPUB book to audiobook format.
        
        Args:
            epub_content: Dictionary mapping chapter titles to text content
            output_dir: Directory to save audio files
            language: Target language
            voice_sample: Optional voice sample for cloning
            progress_callback: Progress callback function
            
        Returns:
            List of generated audio file paths
        """
        audio_files = []
        total_chapters = len(epub_content)
        
        for i, (chapter_title, chapter_text) in enumerate(epub_content.items()):
            if progress_callback:
                chapter_progress = (i / total_chapters) * 100
                await progress_callback(f"Processing chapter {i+1}/{total_chapters}")
            
            # Clean chapter title for filename
            safe_title = "".join(c for c in chapter_title if c.isalnum() or c in (' ', '-', '_'))
            safe_title = safe_title.replace(' ', '_')[:50]  # Limit length
            
            # Generate audio for chapter
            chapter_file = os.path.join(
                output_dir,
                f"chapter_{i+1:03d}_{safe_title}.{self.audio_config.output_format}"
            )
            
            result = await self.text_to_speech(
                chapter_text,
                chapter_file,
                language=language,
                voice_sample=voice_sample,
                progress_callback=lambda msg: asyncio.create_task(
                    progress_callback(f"Chapter {i+1}: {msg}")
                ) if progress_callback else None
            )
            
            if result:
                audio_files.append(result)
        
        # Create playlist file
        playlist_path = os.path.join(output_dir, "audiobook_playlist.m3u")
        with open(playlist_path, 'w', encoding='utf-8') as f:
            for audio_file in audio_files:
                f.write(f"{os.path.basename(audio_file)}\n")
        
        return audio_files
    
    def estimate_audio_duration(self, text: str, words_per_minute: int = 150) -> float:
        """
        Estimate the duration of the audio in minutes.
        
        Args:
            text: Text to estimate
            words_per_minute: Average speaking rate
            
        Returns:
            Estimated duration in minutes
        """
        word_count = len(text.split())
        return word_count / words_per_minute
    
    def close(self):
        """Cleanup TTS resources."""
        if self.tts:
            # Coqui TTS doesn't have explicit cleanup, but we can release the reference
            self.tts = None
            logger.info("Audio processor closed")