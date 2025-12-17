"""
API Routes
"""
from .config_routes import create_config_blueprint
from .translation_routes import create_translation_blueprint
from .file_routes import create_file_blueprint
from .security_routes import create_security_blueprint
from .tts_routes import create_tts_blueprint

__all__ = [
    'create_config_blueprint',
    'create_translation_blueprint',
    'create_file_blueprint',
    'create_security_blueprint',
    'create_tts_blueprint'
]
