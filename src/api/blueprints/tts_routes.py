"""
TTS (Text-to-Speech) routes for generating audio from existing files

Supports multiple TTS providers:
- edge-tts: Microsoft Edge neural voices (cloud-based)
- chatterbox: ResembleAI's local GPU-accelerated TTS with voice cloning
"""
import os
import asyncio
import logging
import threading
import uuid
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

from src.tts.tts_config import TTSConfig, CHATTERBOX_VOICES, DEFAULT_VOICES
from src.tts.providers import (
    is_chatterbox_available,
    get_gpu_status,
    CHATTERBOX_LANGUAGES,
)
from src.utils.file_utils import generate_tts_for_translation
from src.api.services import FileService

logger = logging.getLogger(__name__)

# Allowed audio extensions for voice prompt upload
ALLOWED_VOICE_PROMPT_EXTENSIONS = {'.wav', '.mp3', '.flac', '.ogg', '.m4a'}


def create_tts_blueprint(output_dir, socketio):
    """
    Create and configure the TTS blueprint

    Args:
        output_dir: Base directory for file operations
        socketio: SocketIO instance for real-time updates
    """
    bp = Blueprint('tts', __name__)
    file_service = FileService(output_dir)

    # Track active TTS jobs
    tts_jobs = {}

    def run_tts_async(job_id, filepath, target_language, tts_config):
        """Run TTS generation in a separate thread with async loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Emit started event
            socketio.emit('tts_update', {
                'job_id': job_id,
                'status': 'started',
                'message': 'TTS generation started',
                'filename': os.path.basename(filepath)
            }, namespace='/')

            def log_callback(key, message):
                """Log callback for TTS progress"""
                logger.info(f"TTS [{job_id}]: {message}")

            def progress_callback(current, total, message):
                """Progress callback for TTS"""
                progress_pct = int((current / total) * 100) if total > 0 else 0
                socketio.emit('tts_update', {
                    'job_id': job_id,
                    'status': 'processing',
                    'progress': progress_pct,
                    'current_chunk': current,
                    'total_chunks': total,
                    'message': message
                }, namespace='/')

            # Run TTS generation
            success, message, audio_path = loop.run_until_complete(
                generate_tts_for_translation(
                    translated_filepath=filepath,
                    target_language=target_language,
                    tts_config=tts_config,
                    log_callback=log_callback,
                    progress_callback=progress_callback
                )
            )

            if success:
                audio_filename = os.path.basename(audio_path) if audio_path else None
                socketio.emit('tts_update', {
                    'job_id': job_id,
                    'status': 'completed',
                    'progress': 100,
                    'audio_filename': audio_filename,
                    'audio_path': audio_path,
                    'message': 'TTS generation completed successfully'
                }, namespace='/')

                # Trigger file list refresh
                socketio.emit('file_list_changed', {
                    'reason': 'tts_completed',
                    'filename': audio_filename
                }, namespace='/')

                tts_jobs[job_id] = {
                    'status': 'completed',
                    'audio_path': audio_path,
                    'audio_filename': audio_filename
                }
            else:
                socketio.emit('tts_update', {
                    'job_id': job_id,
                    'status': 'failed',
                    'error': message,
                    'message': f'TTS generation failed: {message}'
                }, namespace='/')

                tts_jobs[job_id] = {
                    'status': 'failed',
                    'error': message
                }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"TTS error [{job_id}]: {error_msg}")

            socketio.emit('tts_update', {
                'job_id': job_id,
                'status': 'failed',
                'error': error_msg,
                'message': f'TTS generation error: {error_msg}'
            }, namespace='/')

            tts_jobs[job_id] = {
                'status': 'failed',
                'error': error_msg
            }

        finally:
            loop.close()

    @bp.route('/api/tts/generate', methods=['POST'])
    def generate_tts():
        """
        Generate TTS audio from an existing file

        Request body:
        {
            "filename": "translated_book.epub",
            "target_language": "Chinese",
            "tts_provider": "edge-tts",  // or "chatterbox"
            "tts_voice": "",  // Optional, auto-select if empty
            "tts_rate": "+0%",
            "tts_format": "opus",
            "tts_bitrate": "64k",
            // Chatterbox-specific options:
            "tts_voice_prompt_path": "",  // Path to audio file for voice cloning
            "tts_exaggeration": 0.5,  // Emotion level (0.0-1.0)
            "tts_cfg_weight": 0.5  // Classifier-free guidance weight
        }
        """
        try:
            data = request.json
            if not data:
                return jsonify({"error": "No data provided"}), 400

            filename = data.get('filename')
            if not filename:
                return jsonify({"error": "No filename provided"}), 400

            # Find the file
            file_path = file_service.find_file(filename)
            if not file_path:
                return jsonify({"error": f"File not found: {filename}"}), 404

            filepath = str(file_path)

            # Get TTS configuration from request
            target_language = data.get('target_language', 'English')
            provider = data.get('tts_provider', 'edge-tts')

            # Validate provider choice
            if provider == 'chatterbox' and not is_chatterbox_available():
                return jsonify({
                    "error": "Chatterbox TTS is not available",
                    "details": "Missing dependencies: torch, chatterbox-tts, or torchaudio. "
                               "Install with: pip install chatterbox-tts torch torchaudio"
                }), 400

            tts_config = TTSConfig(
                enabled=True,
                provider=provider,
                voice=data.get('tts_voice', ''),
                rate=data.get('tts_rate', '+0%'),
                volume=data.get('tts_volume', '+0%'),
                pitch=data.get('tts_pitch', '+0Hz'),
                output_format=data.get('tts_format', 'opus'),
                bitrate=data.get('tts_bitrate', '64k'),
                target_language=target_language,
                # Chatterbox-specific settings
                voice_prompt_path=data.get('tts_voice_prompt_path', ''),
                exaggeration=float(data.get('tts_exaggeration', 0.5)),
                cfg_weight=float(data.get('tts_cfg_weight', 0.5)),
            )

            # Generate job ID
            job_id = str(uuid.uuid4())[:8]

            # Store job info
            tts_jobs[job_id] = {
                'status': 'starting',
                'filename': filename,
                'filepath': filepath
            }

            # Start TTS in background thread
            thread = threading.Thread(
                target=run_tts_async,
                args=(job_id, filepath, target_language, tts_config),
                daemon=True
            )
            thread.start()

            return jsonify({
                "success": True,
                "job_id": job_id,
                "message": f"TTS generation started for {filename}"
            })

        except Exception as e:
            current_app.logger.error(f"Error starting TTS generation: {str(e)}")
            return jsonify({"error": "Failed to start TTS generation", "details": str(e)}), 500

    @bp.route('/api/tts/status/<job_id>', methods=['GET'])
    def get_tts_status(job_id):
        """Get the status of a TTS job"""
        if job_id not in tts_jobs:
            return jsonify({"error": "Job not found"}), 404

        return jsonify(tts_jobs[job_id])

    @bp.route('/api/tts/voices', methods=['GET'])
    def list_voices():
        """List available TTS voices by language for Edge-TTS (default)"""
        # Group voices by language
        voices_by_language = {}
        for key, voice in DEFAULT_VOICES.items():
            # Skip short codes, use full names
            if len(key) > 2 and '-' not in key:
                voices_by_language[key.capitalize()] = voice

        return jsonify({
            "voices": voices_by_language,
            "default_provider": "edge-tts"
        })

    @bp.route('/api/tts/voices/chatterbox', methods=['GET'])
    def list_chatterbox_voices():
        """
        List available languages for Chatterbox TTS.

        Chatterbox supports 23 languages. Voice is determined by the
        voice prompt audio file (voice cloning) or uses default model voice.

        Returns:
            JSON with supported languages and availability status
        """
        available = is_chatterbox_available()

        return jsonify({
            "available": available,
            "provider": "chatterbox",
            "languages": CHATTERBOX_LANGUAGES,
            "language_count": len(CHATTERBOX_LANGUAGES),
            "features": {
                "voice_cloning": True,
                "emotion_control": True,
                "gpu_acceleration": True,
            },
            "note": "Voice is determined by uploaded voice prompt or uses default model voice"
        })

    @bp.route('/api/tts/providers', methods=['GET'])
    def list_providers():
        """
        List available TTS providers and their status.

        Returns:
            JSON with provider information and availability
        """
        providers = {
            "edge-tts": {
                "name": "Edge TTS",
                "description": "Microsoft Edge neural voices (cloud-based)",
                "available": True,  # Always available (uses HTTP API)
                "features": {
                    "voice_selection": True,
                    "rate_control": True,
                    "volume_control": True,
                    "pitch_control": True,
                    "voice_cloning": False,
                    "gpu_required": False,
                },
                "language_count": len([k for k in DEFAULT_VOICES.keys() if len(k) > 2 and '-' not in k]),
            },
            "chatterbox": {
                "name": "Chatterbox TTS",
                "description": "Local GPU-accelerated TTS with voice cloning",
                "available": is_chatterbox_available(),
                "features": {
                    "voice_selection": False,  # Voice determined by audio prompt
                    "rate_control": False,
                    "volume_control": False,
                    "pitch_control": False,
                    "voice_cloning": True,
                    "emotion_control": True,
                    "gpu_required": True,
                },
                "language_count": len(CHATTERBOX_LANGUAGES),
            }
        }

        return jsonify({
            "providers": providers,
            "default": "edge-tts"
        })

    @bp.route('/api/tts/gpu-status', methods=['GET'])
    def gpu_status():
        """
        Get GPU status for Chatterbox TTS.

        Returns:
            JSON with GPU availability, name, and VRAM information
        """
        status = get_gpu_status()
        status["chatterbox_ready"] = is_chatterbox_available() and status.get("cuda_available", False)

        return jsonify(status)

    @bp.route('/api/tts/voice-prompt/upload', methods=['POST'])
    def upload_voice_prompt():
        """
        Upload an audio file for voice cloning with Chatterbox TTS.

        The uploaded file will be saved to the output directory and can
        be referenced in TTS generation requests.

        Form data:
            file: Audio file (WAV, MP3, FLAC, OGG, M4A)

        Returns:
            JSON with the path to the saved voice prompt
        """
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        # Validate file extension
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()

        if ext not in ALLOWED_VOICE_PROMPT_EXTENSIONS:
            return jsonify({
                "error": f"Invalid file type: {ext}",
                "allowed": list(ALLOWED_VOICE_PROMPT_EXTENSIONS)
            }), 400

        # Create voice_prompts directory if it doesn't exist
        voice_prompts_dir = os.path.join(output_dir, 'voice_prompts')
        os.makedirs(voice_prompts_dir, exist_ok=True)

        # Generate unique filename to avoid conflicts
        unique_filename = f"{uuid.uuid4().hex[:8]}_{filename}"
        save_path = os.path.join(voice_prompts_dir, unique_filename)

        try:
            file.save(save_path)
            logger.info(f"Voice prompt saved: {save_path}")

            return jsonify({
                "success": True,
                "filename": unique_filename,
                "path": save_path,
                "message": f"Voice prompt uploaded successfully"
            })

        except Exception as e:
            logger.error(f"Failed to save voice prompt: {e}")
            return jsonify({
                "error": "Failed to save voice prompt",
                "details": str(e)
            }), 500

    @bp.route('/api/tts/voice-prompts', methods=['GET'])
    def list_voice_prompts():
        """
        List available voice prompt files for voice cloning.

        Returns:
            JSON with list of available voice prompt files
        """
        voice_prompts_dir = os.path.join(output_dir, 'voice_prompts')

        if not os.path.exists(voice_prompts_dir):
            return jsonify({
                "voice_prompts": [],
                "directory": voice_prompts_dir
            })

        prompts = []
        for filename in os.listdir(voice_prompts_dir):
            ext = os.path.splitext(filename)[1].lower()
            if ext in ALLOWED_VOICE_PROMPT_EXTENSIONS:
                filepath = os.path.join(voice_prompts_dir, filename)
                prompts.append({
                    "filename": filename,
                    "path": filepath,
                    "size_bytes": os.path.getsize(filepath),
                    "extension": ext
                })

        return jsonify({
            "voice_prompts": prompts,
            "directory": voice_prompts_dir,
            "count": len(prompts)
        })

    @bp.route('/api/tts/voice-prompt/<filename>', methods=['DELETE'])
    def delete_voice_prompt(filename):
        """
        Delete a voice prompt file.

        Args:
            filename: Name of the voice prompt file to delete

        Returns:
            JSON with success status
        """
        voice_prompts_dir = os.path.join(output_dir, 'voice_prompts')
        filepath = os.path.join(voice_prompts_dir, secure_filename(filename))

        if not os.path.exists(filepath):
            return jsonify({"error": "Voice prompt not found"}), 404

        try:
            os.remove(filepath)
            logger.info(f"Voice prompt deleted: {filepath}")

            return jsonify({
                "success": True,
                "message": f"Voice prompt '{filename}' deleted"
            })

        except Exception as e:
            logger.error(f"Failed to delete voice prompt: {e}")
            return jsonify({
                "error": "Failed to delete voice prompt",
                "details": str(e)
            }), 500

    return bp
