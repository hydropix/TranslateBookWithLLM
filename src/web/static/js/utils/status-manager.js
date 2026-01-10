/**
 * Status Manager - LLM connection status indicator
 *
 * Manages the visual status indicator in the header showing LLM connection state
 */

import { DomHelpers } from '../ui/dom-helpers.js';

/**
 * Status types and their visual representations
 */
const STATUS_TYPES = {
    checking: {
        text: 'LLM: Checking...',
        dotClass: 'checking',
        color: '#6b7280' // gray
    },
    connected: {
        text: 'LLM: Connected',
        dotClass: 'connected',
        color: '#16a34a' // green
    },
    disconnected: {
        text: 'LLM: Disconnected',
        dotClass: 'disconnected',
        color: '#dc2626' // red
    },
    error: {
        text: 'LLM: Error',
        dotClass: 'error',
        color: '#f59e0b' // orange
    },
    waiting: {
        text: 'LLM: Waiting...',
        dotClass: 'waiting',
        color: '#6b7280' // gray
    }
};

/**
 * Current status
 */
let currentStatus = 'checking';

export const StatusManager = {
    /**
     * Initialize status manager
     */
    initialize() {
        // Set initial checking state
        this.setStatus('checking');
    },

    /**
     * Set connection status
     * @param {string} status - Status type ('checking', 'connected', 'disconnected', 'error', 'waiting')
     * @param {string} customText - Optional custom text to override default
     */
    setStatus(status, customText = null) {
        const statusInfo = STATUS_TYPES[status];
        if (!statusInfo) {
            console.warn(`Invalid status type: ${status}`);
            return;
        }

        currentStatus = status;

        // Update text
        const statusText = DomHelpers.getElement('providerStatusText');
        if (statusText) {
            statusText.textContent = customText || statusInfo.text;
            statusText.style.color = statusInfo.color;
        }

        // Update dot
        const statusDot = document.querySelector('.header .status-indicator .status-dot');
        if (statusDot) {
            // Remove all status classes
            statusDot.classList.remove('checking', 'connected', 'disconnected', 'error', 'waiting');
            // Add new status class
            statusDot.classList.add(statusInfo.dotClass);
        }
    },

    /**
     * Set checking status
     */
    setChecking() {
        this.setStatus('checking');
    },

    /**
     * Set connected status
     * @param {string} provider - Provider name (optional)
     * @param {number} modelCount - Number of models available (optional)
     */
    setConnected(provider = null, modelCount = null) {
        let text = 'LLM: Connected';
        if (provider) {
            text = `LLM: ${provider.charAt(0).toUpperCase() + provider.slice(1)}`;
            if (modelCount) {
                text += ` (${modelCount} model${modelCount !== 1 ? 's' : ''})`;
            }
        }
        this.setStatus('connected', text);
    },

    /**
     * Set disconnected status
     * @param {string} reason - Optional reason for disconnection
     */
    setDisconnected(reason = null) {
        const text = reason ? `LLM: Disconnected (${reason})` : 'LLM: Disconnected';
        this.setStatus('disconnected', text);
    },

    /**
     * Set error status
     * @param {string} message - Optional error message
     */
    setError(message = null) {
        const text = message ? `LLM: Error (${message})` : 'LLM: Error';
        this.setStatus('error', text);
    },

    /**
     * Set waiting status
     * @param {string} message - Optional waiting message
     */
    setWaiting(message = null) {
        const text = message || 'LLM: Waiting for connection...';
        this.setStatus('waiting', text);
    },

    /**
     * Get current status
     * @returns {string} Current status type
     */
    getCurrentStatus() {
        return currentStatus;
    }
};
