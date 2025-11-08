"""
Flask web server for translation API with WebSocket support
"""
import os
import sys
from datetime import datetime
from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from src.config import (
    API_ENDPOINT as DEFAULT_OLLAMA_API_ENDPOINT,
    DEFAULT_MODEL,
    MAIN_LINES_PER_CHUNK,
    REQUEST_TIMEOUT,
    OLLAMA_NUM_CTX,
    PORT
)
from src.api.routes import configure_routes
from src.api.websocket import configure_websocket_handlers
from src.api.handlers import start_translation_job, start_audiobook_generation
from src.api.translation_state import get_state_manager

# Initialize Flask app with static folder configuration
app = Flask(__name__, 
            static_folder='src/web/static',
            static_url_path='/static')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Thread-safe state manager
state_manager = get_state_manager()
OUTPUT_DIR = "translated_files"

# Ensure output directory exists
try:
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    print(f"✅ Output folder '{OUTPUT_DIR}' is ready.")
except OSError as e:
    print(f"❌ Critical error: Unable to create output folder '{OUTPUT_DIR}': {e}")

# Static files are now handled automatically by Flask

# Wrapper function for starting translation jobs
def start_job_wrapper(translation_id, config):
    """Wrapper to inject dependencies into job starter"""
    start_translation_job(translation_id, config, state_manager, OUTPUT_DIR, socketio)

# Wrapper function for starting audiobook generation
def start_audiobook_wrapper(audiobook_id, config):
    """Wrapper to inject dependencies into audiobook generator"""
    start_audiobook_generation(audiobook_id, config, state_manager, OUTPUT_DIR, socketio)

# Configure routes and WebSocket handlers
configure_routes(app, state_manager, OUTPUT_DIR, start_job_wrapper, start_audiobook_wrapper)
configure_websocket_handlers(socketio, state_manager)

if __name__ == '__main__':
    print("\n" + "="*60 + f"\n🚀 LLM TRANSLATION SERVER (Version {datetime.now().strftime('%Y%m%d-%H%M')})\n" + "="*60)
    print(f"   - Default Ollama Endpoint: {DEFAULT_OLLAMA_API_ENDPOINT}")
    print(f"   - Interface: http://localhost:{PORT} (or http://<your_ip>:{PORT})")
    print(f"   - API: http://localhost:{PORT}/api/")
    print(f"   - Supported formats: .txt, .epub, and .srt")
    print(f"   - Audio features: Text-to-Speech audiobook generation")
    print("\n💡 Press Ctrl+C to stop the server\n")
    socketio.run(app, debug=False, host='0.0.0.0', port=PORT, allow_unsafe_werkzeug=True)