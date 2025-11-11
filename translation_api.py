"""
Flask web server for translation API with WebSocket support
"""
import os
import sys
import logging
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
app = Flask(__name__, 
            static_folder='src/web/static',
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
    logger.info("💡 Press Ctrl+C to stop the server")
    logger.info("")

    # Production deployment note
    if HOST == '0.0.0.0':
        logger.warning("⚠️  Server is binding to 0.0.0.0 (all network interfaces)")
        logger.warning("   For production, use a proper WSGI server like gunicorn:")
        logger.warning("   gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 translation_api:app")
        logger.info("")

    socketio.run(app, debug=False, host=HOST, port=PORT)