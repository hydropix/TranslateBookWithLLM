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
    Emit WebSocket update for translation or audiobook progress
    
    Args:
        socketio: SocketIO instance
        translation_id (str): Translation or audiobook job ID
        data_to_emit (dict): Data to send
        state_manager: Translation state manager instance
    """
    # Check if this is an audiobook job
    if translation_id.startswith('audiobook_'):
        audiobook_id = translation_id.replace('audiobook_', '')
        job_data = state_manager.get_audiobook_job(audiobook_id)
        if job_data:
            data_to_emit['audiobook_id'] = audiobook_id
            try:
                if 'progress' not in data_to_emit and 'progress' in job_data:
                    data_to_emit['progress'] = job_data['progress']
                
                if 'status' not in data_to_emit and 'status' in job_data:
                    data_to_emit['status'] = job_data['status']
                
                socketio.emit('audiobook_update', data_to_emit, namespace='/')
            except Exception as e:
                print(f"WebSocket emission error for audiobook {audiobook_id}: {e}")
    else:
        # Original translation update logic
        translation_data = state_manager.get_translation(translation_id)
        if translation_data:
            data_to_emit['translation_id'] = translation_id
            try:
                if 'stats' not in data_to_emit and 'stats' in translation_data:
                    data_to_emit['stats'] = translation_data['stats']

                if 'progress' not in data_to_emit and 'progress' in translation_data:
                    data_to_emit['progress'] = translation_data['progress']

                socketio.emit('translation_update', data_to_emit, namespace='/')
            except Exception as e:
                print(f"WebSocket emission error for {translation_id}: {e}")