/**
 * Message Logger - Centralized logging and user messaging
 *
 * Handles both user-facing messages and activity log entries
 */

import { DomHelpers } from './dom-helpers.js';

/**
 * Log filters - messages containing these strings will be skipped
 */
const LOG_FILTERS = [
    'LLM Request',
    'LLM Response',
    '🔍 Input file path:',
    '🔍 Resolved path:',
    '🔍 Parent directory:',
    '📋 Path parts:',
    '📋 Parent directory name:',
    '📋 Expected uploads directory:',
    '🔍 File is confirmed',
    '🔍 File is NOT in uploads',
    '🗑️ Cleaned up uploaded source file:',
    'ℹ️ Skipped cleanup',
    '🧹 Starting cleanup check',
    '📁 File path in config:',
    '🔍 Debug -'
];

export const MessageLogger = {
    /**
     * Show a user message
     * @param {string} text - Message text
     * @param {string} type - Message type ('success', 'error', 'info', 'warning')
     */
    showMessage(text, type = 'info') {
        const messagesDiv = DomHelpers.getElement('messages');
        if (!messagesDiv) return;

        if (!text) {
            DomHelpers.setHtml(messagesDiv, '');
            return;
        }

        const messageHtml = `<div class="message ${type}">${DomHelpers.escapeHtml(text)}</div>`;
        DomHelpers.setHtml(messagesDiv, messageHtml);
    },

    /**
     * Add entry to activity log
     * @param {string} message - Log message
     */
    addLog(message) {
        // Filter out verbose/technical messages
        if (this.shouldFilterLog(message)) {
            return;
        }

        const logContainer = DomHelpers.getElement('logContainer');
        if (!logContainer) return;

        const timestamp = new Date().toLocaleTimeString();
        const logEntry = DomHelpers.createElement('div', {
            className: 'log-entry',
            innerHTML: `<span class="log-timestamp">[${timestamp}]</span> ${message}`
        });

        logContainer.appendChild(logEntry);
        logContainer.scrollTop = logContainer.scrollHeight;
    },

    /**
     * Check if log message should be filtered out
     * @param {string} message - Log message
     * @returns {boolean} True if should be filtered
     */
    shouldFilterLog(message) {
        return LOG_FILTERS.some(filter => message.includes(filter));
    },

    /**
     * Clear the activity log
     */
    clearLog() {
        const logContainer = DomHelpers.getElement('logContainer');
        if (logContainer) {
            DomHelpers.clearChildren(logContainer);
            this.addLog('📝 Activity log cleared by user');
        }
    },

    /**
     * Update translation preview
     * @param {string} response - LLM response containing translation
     */
    updateTranslationPreview(response) {
        const previewElement = DomHelpers.getElement('lastTranslationPreview');
        if (!previewElement) return;

        // Extract text between <TRANSLATION> tags
        const translateMatch = response.match(/<TRANSLATION>([\s\S]*?)<\/TRANSLATION>/);
        if (!translateMatch) return;

        let translatedText = translateMatch[1].trim();

        // Remove placeholder tags (⟦TAG0⟧, ⟦TAG1⟧, etc.) for cleaner preview
        translatedText = translatedText.replace(/⟦TAG\d+⟧/g, '');

        const previewHtml = `
            <div style="background: #ffffff; border-left: 3px solid #22c55e; padding: 15px; color: #000000; white-space: pre-wrap; line-height: 1.6;">
                ${DomHelpers.escapeHtml(translatedText)}
            </div>
        `;

        DomHelpers.setHtml(previewElement, previewHtml);
    },

    /**
     * Reset translation preview
     */
    resetTranslationPreview() {
        const previewElement = DomHelpers.getElement('lastTranslationPreview');
        if (previewElement) {
            const placeholderHtml = '<div style="color: #6b7280; font-style: italic; padding: 10px;">No translation yet...</div>';
            DomHelpers.setHtml(previewElement, placeholderHtml);
        }
    }
};
