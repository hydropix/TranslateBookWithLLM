"""
TTS (Text-to-Speech) routes for generating audio from existing files
"""
import os
import asyncio
import logging
import threading
import uuid
from flask import Blueprint, request, jsonify, current_app

from src.tts.tts_config import TTSConfig
from src.utils.file_utils import generate_tts_for_translation
from src.api.services import FileService

logger = logging.getLogger(__name__)


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
            "tts_voice": "",  // Optional, auto-select if empty
            "tts_rate": "+0%",
            "tts_format": "opus",
            "tts_bitrate": "64k"
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

            tts_config = TTSConfig(
                enabled=True,
                provider='edge-tts',
                voice=data.get('tts_voice', ''),
                rate=data.get('tts_rate', '+0%'),
                volume=data.get('tts_volume', '+0%'),
                pitch=data.get('tts_pitch', '+0Hz'),
                output_format=data.get('tts_format', 'opus'),
                bitrate=data.get('tts_bitrate', '64k'),
                target_language=target_language
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
        """List available TTS voices by language"""
        from src.tts.tts_config import DEFAULT_VOICES

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

    return bp
