"""
Translation job management routes
"""
import os
import time
from flask import Blueprint, request, jsonify

from src.config import (
    MAIN_LINES_PER_CHUNK,
    REQUEST_TIMEOUT,
    OLLAMA_NUM_CTX
)


def create_translation_blueprint(state_manager, start_translation_job):
    """
    Create and configure the translation blueprint

    Args:
        state_manager: Translation state manager instance
        start_translation_job: Function to start translation jobs
    """
    bp = Blueprint('translation', __name__)

    @bp.route('/api/translate', methods=['POST'])
    def start_translation_request():
        """Start a new translation job"""
        data = request.json

        # Validate required fields
        if 'file_path' in data:
            required_fields = ['file_path', 'source_language', 'target_language',
                             'model', 'llm_api_endpoint', 'output_filename', 'file_type']
        else:
            required_fields = ['text', 'source_language', 'target_language',
                             'model', 'llm_api_endpoint', 'output_filename']

        for field in required_fields:
            if field not in data or (isinstance(data[field], str) and not data[field].strip()) or (not isinstance(data[field], str) and data[field] is None):
                if field == 'text' and data.get('file_type') == 'txt' and data.get('text') == "":
                    pass
                else:
                    return jsonify({"error": f"Missing or empty field: {field}"}), 400

        # Generate unique translation ID
        translation_id = f"trans_{int(time.time() * 1000)}"

        # Build configuration
        config = {
            'source_language': data['source_language'],
            'target_language': data['target_language'],
            'model': data['model'],
            'chunk_size': int(data.get('chunk_size', MAIN_LINES_PER_CHUNK)),
            'llm_api_endpoint': data['llm_api_endpoint'],
            'request_timeout': int(data.get('timeout', REQUEST_TIMEOUT)),
            'context_window': int(data.get('context_window', OLLAMA_NUM_CTX)),
            'max_attempts': int(data.get('max_attempts', 2)),
            'retry_delay': int(data.get('retry_delay', 2)),
            'output_filename': data['output_filename'],
            'custom_instructions': data.get('custom_instructions', ''),
            'llm_provider': data.get('llm_provider', 'ollama'),
            'gemini_api_key': data.get('gemini_api_key') or os.getenv('GEMINI_API_KEY', ''),
            'enable_post_processing': data.get('enable_post_processing', False),
            'post_processing_instructions': data.get('post_processing_instructions', ''),
            'simple_mode': data.get('simple_mode', False)
        }

        # Add file-specific or text-specific configuration
        if 'file_path' in data:
            config['file_path'] = data['file_path']
            config['file_type'] = data['file_type']
        else:
            config['text'] = data['text']
            config['file_type'] = data.get('file_type', 'txt')

        # Create translation in state manager
        state_manager.create_translation(translation_id, config)

        # Start translation job
        start_translation_job(translation_id, config)

        return jsonify({
            "translation_id": translation_id,
            "message": "Translation queued.",
            "config_received": config
        })

    @bp.route('/api/translation/<translation_id>', methods=['GET'])
    def get_translation_job_status(translation_id):
        """Get status of a translation job"""
        job_data = state_manager.get_translation(translation_id)
        if not job_data:
            return jsonify({"error": "Translation not found"}), 404

        stats = job_data.get('stats', {
            'start_time': time.time(),
            'total_chunks': 0,
            'completed_chunks': 0,
            'failed_chunks': 0
        })

        # Calculate elapsed time
        if job_data.get('status') == 'running' or job_data.get('status') == 'queued':
            elapsed = time.time() - stats.get('start_time', time.time())
        else:
            elapsed = stats.get('elapsed_time', time.time() - stats.get('start_time', time.time()))

        return jsonify({
            "translation_id": translation_id,
            "status": job_data.get('status'),
            "progress": job_data.get('progress'),
            "stats": {
                'total_chunks': stats.get('total_chunks', 0),
                'completed_chunks': stats.get('completed_chunks', 0),
                'failed_chunks': stats.get('failed_chunks', 0),
                'start_time': stats.get('start_time'),
                'elapsed_time': elapsed
            },
            "logs": job_data.get('logs', [])[-100:],
            "result_preview": "[Preview functionality removed. Download file to view content.]" if job_data.get('status') in ['completed', 'interrupted'] else None,
            "error": job_data.get('error'),
            "config": job_data.get('config'),
            "output_filepath": job_data.get('output_filepath')
        })

    @bp.route('/api/translation/<translation_id>/interrupt', methods=['POST'])
    def interrupt_translation_job(translation_id):
        """Interrupt a running translation job"""
        if not state_manager.exists(translation_id):
            return jsonify({"error": "Translation not found"}), 404

        job_data = state_manager.get_translation(translation_id)
        if job_data.get('status') == 'running' or job_data.get('status') == 'queued':
            state_manager.set_interrupted(translation_id, True)
            return jsonify({
                "message": "Interruption signal sent. Translation will stop after the current segment."
            }), 200

        return jsonify({
            "message": "The translation is not in an interruptible state (e.g., already completed or failed)."
        }), 400

    @bp.route('/api/translations', methods=['GET'])
    def list_all_translations():
        """List all translation jobs"""
        summary_list = state_manager.get_translation_summaries()
        return jsonify({"translations": summary_list})

    return bp
