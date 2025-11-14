/**
 * WebSocket Manager - WebSocket connection and event handling
 *
 * Manages WebSocket lifecycle and provides event routing
 */

import { MessageLogger } from '../ui/message-logger.js';
import { ApiClient } from './api-client.js';

let socket = null;
const eventHandlers = new Map();

export const WebSocketManager = {
    /**
     * Initialize and connect WebSocket
     */
    connect() {
        if (socket) {
            console.warn('WebSocket already connected');
            return;
        }

        socket = io();

        // Connection events
        socket.on('connect', () => {
            const baseUrl = ApiClient.getBaseUrl();
            console.log('WebSocket connected to:', baseUrl);
            MessageLogger.addLog('✅ WebSocket connection to server established.');
            this.emit('connect');
        });

        socket.on('disconnect', () => {
            console.log('WebSocket disconnected.');
            MessageLogger.addLog('❌ WebSocket connection lost.');
            this.emit('disconnect');
        });

        // Application events
        socket.on('translation_update', (data) => {
            this.emit('translation_update', data);
        });

        socket.on('file_list_changed', (data) => {
            console.log('File list changed:', data.reason, '-', data.filename);
            this.emit('file_list_changed', data);
        });

        socket.on('checkpoint_created', (data) => {
            console.log('Checkpoint created:', data);
            MessageLogger.addLog(`⏸️ ${data.message || 'Checkpoint created'}`);
            this.emit('checkpoint_created', data);
        });
    },

    /**
     * Disconnect WebSocket
     */
    disconnect() {
        if (socket) {
            socket.disconnect();
            socket = null;
        }
    },

    /**
     * Check if WebSocket is connected
     * @returns {boolean} True if connected
     */
    isConnected() {
        return socket && socket.connected;
    },

    /**
     * Register event handler
     * @param {string} eventName - Event name
     * @param {Function} handler - Event handler function
     * @returns {Function} Unsubscribe function
     */
    on(eventName, handler) {
        if (!eventHandlers.has(eventName)) {
            eventHandlers.set(eventName, []);
        }
        eventHandlers.get(eventName).push(handler);

        // Return unsubscribe function
        return () => this.off(eventName, handler);
    },

    /**
     * Unregister event handler
     * @param {string} eventName - Event name
     * @param {Function} handler - Event handler to remove
     */
    off(eventName, handler) {
        if (eventHandlers.has(eventName)) {
            const handlers = eventHandlers.get(eventName);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    },

    /**
     * Emit event to registered handlers
     * @param {string} eventName - Event name
     * @param {any} [data] - Event data
     */
    emit(eventName, data) {
        if (eventHandlers.has(eventName)) {
            eventHandlers.get(eventName).forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`Error in WebSocket event handler for "${eventName}":`, error);
                }
            });
        }
    },

    /**
     * Send message through WebSocket
     * @param {string} eventName - Event name
     * @param {any} data - Data to send
     */
    send(eventName, data) {
        if (socket && socket.connected) {
            socket.emit(eventName, data);
        } else {
            console.error('Cannot send message: WebSocket not connected');
        }
    },

    /**
     * Get underlying socket.io instance (for advanced usage)
     * @returns {Socket|null} Socket.io instance
     */
    getSocket() {
        return socket;
    }
};
