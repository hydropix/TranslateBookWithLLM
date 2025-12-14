"""
Configuration and health check routes
"""
import os
import sys
import asyncio
import logging
import requests
from flask import Blueprint, request, jsonify, send_from_directory


def get_base_path():
    """Get base path for resources, handling PyInstaller frozen executables"""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        return sys._MEIPASS
    else:
        # Running as normal Python script
        return os.getcwd()

from src.config import (
    API_ENDPOINT as DEFAULT_OLLAMA_API_ENDPOINT,
    DEFAULT_MODEL,
    MAIN_LINES_PER_CHUNK,
    REQUEST_TIMEOUT,
    OLLAMA_NUM_CTX,
    MAX_TRANSLATION_ATTEMPTS,
    RETRY_DELAY_SECONDS,
    DEFAULT_SOURCE_LANGUAGE,
    DEFAULT_TARGET_LANGUAGE,
    DEBUG_MODE,
    GEMINI_API_KEY,
    OPENAI_API_KEY,
    OPENROUTER_API_KEY
)

# Setup logger for this module
logger = logging.getLogger('config_routes')
if DEBUG_MODE:
    logger.setLevel(logging.DEBUG)


def create_config_blueprint():
    """Create and configure the config blueprint"""
    bp = Blueprint('config', __name__)

    @bp.route('/')
    def serve_interface():
        """Serve the main translation interface"""
        base_path = get_base_path()
        templates_dir = os.path.join(base_path, 'src', 'web', 'templates')
        interface_path = os.path.join(templates_dir, 'translation_interface.html')
        if os.path.exists(interface_path):
            return send_from_directory(templates_dir, 'translation_interface.html')
        return f"<h1>Error: Interface not found</h1><p>Looked in: {interface_path}</p>", 404

    @bp.route('/api/health', methods=['GET'])
    def health_check():
        """API health check endpoint"""
        return jsonify({
            "status": "ok",
            "message": "Translation API is running",
            "translate_module": "loaded",
            "ollama_default_endpoint": DEFAULT_OLLAMA_API_ENDPOINT,
            "supported_formats": ["txt", "epub", "srt"]
        })

    @bp.route('/api/models', methods=['GET'])
    def get_available_models():
        """Get available models from Ollama, Gemini, or OpenRouter"""
        provider = request.args.get('provider', 'ollama')

        if provider == 'gemini':
            return _get_gemini_models()
        elif provider == 'openrouter':
            return _get_openrouter_models()
        else:
            return _get_ollama_models()

    @bp.route('/api/config', methods=['GET'])
    def get_default_config():
        """Get default configuration values"""
        config_response = {
            "api_endpoint": DEFAULT_OLLAMA_API_ENDPOINT,
            "default_model": DEFAULT_MODEL,
            "chunk_size": MAIN_LINES_PER_CHUNK,
            "timeout": REQUEST_TIMEOUT,
            "context_window": OLLAMA_NUM_CTX,
            "max_attempts": MAX_TRANSLATION_ATTEMPTS,
            "retry_delay": RETRY_DELAY_SECONDS,
            "supported_formats": ["txt", "epub", "srt"],
            "gemini_api_key": GEMINI_API_KEY,
            "openai_api_key": OPENAI_API_KEY,
            "openrouter_api_key": OPENROUTER_API_KEY,
            "default_source_language": DEFAULT_SOURCE_LANGUAGE,
            "default_target_language": DEFAULT_TARGET_LANGUAGE
        }

        if DEBUG_MODE:
            logger.debug(f"📤 /api/config response:")
            logger.debug(f"   default_source_language: {DEFAULT_SOURCE_LANGUAGE}")
            logger.debug(f"   default_target_language: {DEFAULT_TARGET_LANGUAGE}")
            logger.debug(f"   api_endpoint: {DEFAULT_OLLAMA_API_ENDPOINT}")
            logger.debug(f"   default_model: {DEFAULT_MODEL}")

        return jsonify(config_response)

    def _get_openrouter_models():
        """Get available text-only models from OpenRouter API"""
        api_key = request.args.get('api_key')
        if not api_key:
            api_key = os.getenv('OPENROUTER_API_KEY', OPENROUTER_API_KEY)

        if not api_key:
            return jsonify({
                "models": [],
                "model_names": [],
                "default": "anthropic/claude-sonnet-4",
                "status": "api_key_missing",
                "count": 0,
                "error": "OpenRouter API key is required. Set OPENROUTER_API_KEY environment variable or pass api_key parameter."
            })

        try:
            from src.core.llm_providers import OpenRouterProvider

            openrouter_provider = OpenRouterProvider(api_key=api_key)
            models = asyncio.run(openrouter_provider.get_available_models(text_only=True))

            if models:
                model_names = [m['id'] for m in models]
                return jsonify({
                    "models": models,
                    "model_names": model_names,
                    "default": "anthropic/claude-sonnet-4",
                    "status": "openrouter_connected",
                    "count": len(models)
                })
            else:
                return jsonify({
                    "models": [],
                    "model_names": [],
                    "default": "anthropic/claude-sonnet-4",
                    "status": "openrouter_error",
                    "count": 0,
                    "error": "Failed to retrieve OpenRouter models"
                })

        except Exception as e:
            print(f"❌ Error retrieving OpenRouter models: {e}")
            return jsonify({
                "models": [],
                "model_names": [],
                "default": "anthropic/claude-sonnet-4",
                "status": "openrouter_error",
                "count": 0,
                "error": f"Error connecting to OpenRouter API: {str(e)}"
            })

    def _get_gemini_models():
        """Get available models from Gemini API"""
        api_key = request.args.get('api_key')
        if not api_key:
            api_key = os.getenv('GEMINI_API_KEY')

        if not api_key:
            return jsonify({
                "models": [],
                "default": "gemini-2.0-flash",
                "status": "api_key_missing",
                "count": 0,
                "error": "Gemini API key is required. Set GEMINI_API_KEY environment variable or pass api_key parameter."
            })

        try:
            from src.core.llm_providers import GeminiProvider

            gemini_provider = GeminiProvider(api_key=api_key)
            models = asyncio.run(gemini_provider.get_available_models())

            if models:
                model_names = [m['name'] for m in models]
                return jsonify({
                    "models": models,
                    "model_names": model_names,
                    "default": "gemini-2.0-flash",
                    "status": "gemini_connected",
                    "count": len(models)
                })
            else:
                return jsonify({
                    "models": [],
                    "default": "gemini-2.0-flash",
                    "status": "gemini_error",
                    "count": 0,
                    "error": "Failed to retrieve Gemini models"
                })

        except Exception as e:
            print(f"❌ Error retrieving Gemini models: {e}")
            return jsonify({
                "models": [],
                "default": "gemini-2.0-flash",
                "status": "gemini_error",
                "count": 0,
                "error": f"Error connecting to Gemini API: {str(e)}"
            })

    def _get_ollama_models():
        """Get available models from Ollama API"""
        ollama_base_from_ui = request.args.get('api_endpoint', DEFAULT_OLLAMA_API_ENDPOINT)

        if DEBUG_MODE:
            logger.debug(f"📥 /api/models request for Ollama")
            logger.debug(f"   api_endpoint from UI: {ollama_base_from_ui}")
            logger.debug(f"   default endpoint: {DEFAULT_OLLAMA_API_ENDPOINT}")

        try:
            base_url = ollama_base_from_ui.split('/api/')[0]
            tags_url = f"{base_url}/api/tags"

            if DEBUG_MODE:
                logger.debug(f"   Connecting to: {tags_url}")

            response = requests.get(tags_url, timeout=10)  # Increased timeout from 5 to 10

            if DEBUG_MODE:
                logger.debug(f"   Response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                models_data = data.get('models', [])
                model_names = [m.get('name') for m in models_data if m.get('name')]

                if DEBUG_MODE:
                    logger.debug(f"   Models found: {model_names}")

                return jsonify({
                    "models": model_names,
                    "default": DEFAULT_MODEL if DEFAULT_MODEL in model_names else (model_names[0] if model_names else DEFAULT_MODEL),
                    "status": "ollama_connected",
                    "count": len(model_names)
                })
            else:
                if DEBUG_MODE:
                    logger.debug(f"   ❌ Non-200 response: {response.status_code}")
                    logger.debug(f"   Response body: {response.text[:500]}")

        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection refused to {tags_url}. Is Ollama running?"
            if DEBUG_MODE:
                logger.debug(f"   ❌ ConnectionError: {e}")
            print(f"❌ {error_msg}")
        except requests.exceptions.Timeout as e:
            error_msg = f"Timeout connecting to {tags_url} (10s)"
            if DEBUG_MODE:
                logger.debug(f"   ❌ Timeout: {e}")
            print(f"❌ {error_msg}")
        except requests.exceptions.RequestException as e:
            if DEBUG_MODE:
                logger.debug(f"   ❌ RequestException: {type(e).__name__}: {e}")
            print(f"❌ Could not connect to Ollama at {ollama_base_from_ui}: {e}")
        except Exception as e:
            if DEBUG_MODE:
                logger.debug(f"   ❌ Unexpected error: {type(e).__name__}: {e}")
            print(f"❌ Error retrieving models from {ollama_base_from_ui}: {e}")

        return jsonify({
            "models": [],
            "default": DEFAULT_MODEL,
            "status": "ollama_offline_or_error",
            "count": 0,
            "error": f"Ollama is not accessible at {ollama_base_from_ui} or an error occurred. Verify that Ollama is running ('ollama serve') and the endpoint is correct."
        })

    return bp
