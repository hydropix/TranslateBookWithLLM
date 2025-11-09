"""
Flask routes orchestrator for the translation API

This module serves as a lightweight coordinator that registers
all route blueprints. The actual route implementations are organized
into separate modules for better maintainability:

- blueprints/config_routes.py: Health checks, models, and configuration
- blueprints/translation_routes.py: Translation job management
- blueprints/file_routes.py: File listing, download, delete operations
- blueprints/security_routes.py: File upload and security endpoints
"""
from flask import jsonify

from .blueprints import (
    create_config_blueprint,
    create_translation_blueprint,
    create_file_blueprint,
    create_security_blueprint
)


def configure_routes(app, state_manager, output_dir, start_translation_job):
    """
    Configure Flask routes by registering all blueprints

    Args:
        app: Flask application instance
        state_manager: Translation state manager
        output_dir: Base directory for file operations
        start_translation_job: Function to start translation jobs
    """

    # Register config and health check routes
    config_bp = create_config_blueprint()
    app.register_blueprint(config_bp)

    # Register translation management routes
    translation_bp = create_translation_blueprint(state_manager, start_translation_job)
    app.register_blueprint(translation_bp)

    # Register file management routes
    file_bp = create_file_blueprint(output_dir)
    app.register_blueprint(file_bp)

    # Register security and upload routes
    security_bp = create_security_blueprint(output_dir)
    app.register_blueprint(security_bp)

    # Register error handlers
    _register_error_handlers(app)


def _register_error_handlers(app):
    """Register global error handlers"""

    @app.errorhandler(404)
    def route_not_found(error):
        return jsonify({"error": "API Endpoint not found"}), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        import traceback
        tb_str = traceback.format_exc()
        print(f"INTERNAL SERVER ERROR: {error}\nTRACEBACK:\n{tb_str}")
        return jsonify({"error": "Internal server error", "details": str(error)}), 500