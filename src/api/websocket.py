"""
WebSocket handlers for real-time communication
"""
from flask import request
from flask_socketio import emit


def configure_websocket_handlers(socketio, state_manager):
    """Configure WebSocket event handlers"""
    
    @socketio.on('connect')
    def handle_websocket_connect():
        print(f'🔌 WebSocket client connected: {request.sid}')
        emit('connected', {'message': 'Connected to translation server via WebSocket'})

    @socketio.on('disconnect')
    def handle_websocket_disconnect():
        print(f'🔌 WebSocket client disconnected: {request.sid}')


def emit_update(socketio, translation_id, data_to_emit, state_manager):
    """
    Emit WebSocket update for translation progress

    Args:
        socketio: SocketIO instance
        translation_id (str): Translation job ID
        data_to_emit (dict): Data to send
        state_manager: Translation state manager instance
    """
    translation_data = state_manager.get_translation(translation_id)
    if translation_data:
        data_to_emit['translation_id'] = translation_id
        try:
            if 'stats' not in data_to_emit and 'stats' in translation_data:
                data_to_emit['stats'] = translation_data['stats']

            if 'progress' not in data_to_emit and 'progress' in translation_data:
                data_to_emit['progress'] = translation_data['progress']

            # Store last translation for UI restoration after browser refresh
            log_entry = data_to_emit.get('log_entry')
            if (log_entry and log_entry.get('type') == 'llm_response' and
                log_entry.get('data', {}).get('response')):
                state_manager.set_translation_field(
                    translation_id, 'last_translation', log_entry['data']['response']
                )

            socketio.emit('translation_update', data_to_emit, namespace='/')
        except Exception as e:
            print(f"WebSocket emission error for {translation_id}: {e}")