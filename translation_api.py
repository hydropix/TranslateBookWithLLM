"""
Flask web server for translation API with WebSocket support
"""
import os
import sys
import logging
import webbrowser
import threading
from datetime import datetime
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Reduce verbosity of werkzeug (Flask HTTP server logs)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'replace')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'replace')

from src.config import (
    API_ENDPOINT as DEFAULT_OLLAMA_API_ENDPOINT,
    DEFAULT_MODEL,
    PORT,
    HOST,
    OUTPUT_DIR
)
from src.api.routes import configure_routes
from src.api.websocket import configure_websocket_handlers
from src.api.handlers import start_translation_job
from src.api.translation_state import get_state_manager


# Initialize Flask app with static folder configuration
base_path = os.getcwd()
static_folder_path = os.path.join(base_path, 'src', 'web', 'static')
app = Flask(__name__,
            static_folder=static_folder_path,
            static_url_path='/static')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Thread-safe state manager
state_manager = get_state_manager()

def validate_configuration():
    """Validate required configuration before starting server"""
    issues = []

    if not PORT or not isinstance(PORT, int):
        issues.append("PORT must be a valid integer")
    if not DEFAULT_MODEL:
        issues.append("DEFAULT_MODEL must be configured")
    if not DEFAULT_OLLAMA_API_ENDPOINT:
        issues.append("API_ENDPOINT must be configured")

    if issues:
        logger.error("\n" + "="*70)
        logger.error("❌ CONFIGURATION ERROR")
        logger.error("="*70)
        for issue in issues:
            logger.error(f"   • {issue}")
        logger.error("\n💡 SOLUTION:")
        logger.error("   1. Create a .env file from .env.example")
        logger.error("   2. Configure the required settings")
        logger.error("   3. Restart the application")
        logger.error("\n   Quick setup:")
        logger.error("   python -m src.utils.env_helper setup")
        logger.error("="*70 + "\n")
        raise ValueError("Configuration validation failed. See errors above.")

    logger.info("✅ Configuration validated successfully")

# Ensure output directory exists
try:
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    logger.info(f"Output folder '{OUTPUT_DIR}' is ready")
except OSError as e:
    logger.error(f"Critical error: Unable to create output folder '{OUTPUT_DIR}': {e}")
    sys.exit(1)

# Static files are now handled automatically by Flask

# Wrapper function for starting translation jobs
def start_job_wrapper(translation_id, config):
    """Wrapper to inject dependencies into job starter"""
    start_translation_job(translation_id, config, state_manager, OUTPUT_DIR, socketio)

# Configure routes and WebSocket handlers
configure_routes(app, state_manager, OUTPUT_DIR, start_job_wrapper)
configure_websocket_handlers(socketio, state_manager)

# Restore incomplete jobs from database on startup
def restore_incomplete_jobs():
    """Restore incomplete translation jobs from checkpoints on server startup"""
    try:
        resumable_jobs = state_manager.get_resumable_jobs()
        if resumable_jobs:
            logger.info(f"📦 Found {len(resumable_jobs)} incomplete translation job(s) from previous session:")
            for job in resumable_jobs:
                translation_id = job['translation_id']
                progress = job.get('progress', {})
                completed = progress.get('completed_chunks', 0)
                total = progress.get('total_chunks', 0)

                # Restore job into in-memory state
                state_manager.restore_job_from_checkpoint(translation_id)

                logger.info(f"   - {translation_id}: {job['file_type'].upper()} ({completed}/{total} chunks completed)")
            logger.info("   Use the web interface to resume or delete these jobs")
        else:
            logger.info("📦 No incomplete jobs to restore")
    except Exception as e:
        logger.error(f"Error restoring incomplete jobs: {e}")

restore_incomplete_jobs()

def open_browser(host, port):
    """Open the web interface in the default browser after a short delay"""
    def _open():
        # Small delay to ensure server is ready
        import time
        time.sleep(1.5)
        url = f"http://{'localhost' if host == '0.0.0.0' else host}:{port}"
        logger.info(f"🌐 Opening browser at {url}")
        webbrowser.open(url)

    # Run in background thread to not block server startup
    thread = threading.Thread(target=_open, daemon=True)
    thread.start()


def test_ollama_connection():
    """Test Ollama connection at startup and log result"""
    import requests
    try:
        base_url = DEFAULT_OLLAMA_API_ENDPOINT.split('/api/')[0]
        tags_url = f"{base_url}/api/tags"
        logger.info(f"🔍 Testing Ollama connection at {tags_url}...")
        response = requests.get(tags_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = [m.get('name') for m in data.get('models', [])]
            logger.info(f"✅ Ollama connected! Found {len(models)} model(s): {models}")
            return True
        else:
            logger.warning(f"⚠️ Ollama returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        logger.warning(f"⚠️ Cannot connect to Ollama at {base_url}")
        logger.warning(f"   Make sure Ollama is running ('ollama serve')")
        return False
    except Exception as e:
        logger.warning(f"⚠️ Ollama connection test failed: {e}")
        return False


if __name__ == '__main__':
    # Validate configuration before starting
    validate_configuration()

    logger.info("="*60)
    logger.info(f"🚀 LLM TRANSLATION SERVER (Version {datetime.now().strftime('%Y%m%d-%H%M')})")
    logger.info("="*60)
    logger.info(f"   - Default Ollama Endpoint: {DEFAULT_OLLAMA_API_ENDPOINT}")
    logger.info(f"   - Interface: http://{HOST}:{PORT}")
    logger.info(f"   - API: http://{HOST}:{PORT}/api/")
    logger.info(f"   - Health Check: http://{HOST}:{PORT}/api/health")
    logger.info(f"   - Supported formats: .txt, .epub, and .srt")
    logger.info("")

    # Test Ollama connection at startup
    test_ollama_connection()

    logger.info("")
    logger.info("💡 Press Ctrl+C to stop the server")
    logger.info("")

    # Production deployment note
    if HOST == '0.0.0.0':
        logger.warning("⚠️  Server is binding to 0.0.0.0 (all network interfaces)")
        logger.warning("   For production, use a proper WSGI server like gunicorn:")
        logger.warning("   gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 translation_api:app")
        logger.info("")

    # Auto-open browser (especially useful for portable executable)
    open_browser(HOST, PORT)

    socketio.run(app, debug=False, host=HOST, port=PORT, allow_unsafe_werkzeug=True)