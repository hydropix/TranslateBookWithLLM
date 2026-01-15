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
    'Refinement Request',
    'Refinement Response',
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
    '🔍 Debug -',
    // Context management (too verbose)
    '📊 Context stats:',
    '📐 Updating context window:',
    '📈 Increasing context:',
    '🎯 Adaptive context enabled',
    '📐 Refinement context:',
    // Model detection (informational but verbose)
    '[MODEL]',
    'Detected model context size:',
    'Detected context size from',
    'Using default for',
    'Using fallback:',
    // Token usage (shown in stats already)
    'Tokens:',
    '[TOKENS]',
    // Skip messages (not important)
    'Skipping LLM for single/empty character:',
    // Progress Update (empty message key)
    'Progress Update',
    // SRT specific verbose messages
    'Subtitle',
    'refined successfully',
    'using original translation',
    'refinement failed, using original',
    'Parsed',
    'subtitles from SRT file',
    'Grouped',
    'subtitles into',
    'blocks',
    // File parsing messages (too verbose)
    'Processing file:',
    'File type:',
    'Reading file content',
    // Chunking messages (shown in progress already)
    'Created',
    'chunks for translation',
    'main segments',
    // Translation loop messages (redundant with progress)
    'Translation task started',
    'Starting translation loop',
    'Translation loop',
];

export const MessageLogger = {
    // Track last progress message for updating in-place
    lastProgressEntry: null,
    lastProgressTimestamp: null,
    currentFileName: null,
    // Track summary messages for consolidation
    summaryBuffer: [],
    summaryTimeout: null,

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
     * Add entry to activity log with smart consolidation
     * @param {string} message - Log message
     */
    addLog(message) {
        // Filter out verbose/technical messages
        if (this.shouldFilterLog(message)) {
            return;
        }

        // Check if this is a summary message that should be buffered
        if (this.isSummaryMessage(message)) {
            this.bufferSummaryMessage(message);
            return;
        }

        // Extract file name from message if present (format: [filename] message)
        const fileNameMatch = message.match(/^\[([^\]]+)\]\s+(.+)$/);
        if (fileNameMatch) {
            const fileName = fileNameMatch[1];
            const actualMessage = fileNameMatch[2];

            // Update current file being processed
            if (this.currentFileName !== fileName) {
                this.currentFileName = fileName;
                this.lastProgressEntry = null; // Reset progress tracking for new file
            }

            // Consolidate progress/chunk messages
            if (this.shouldConsolidateMessage(actualMessage)) {
                this.updateProgressLog(fileName, actualMessage);
                return;
            }

            // For important messages, create new log entry
            if (this.isImportantMessage(actualMessage)) {
                this._createLogEntry(message);
            }
        } else {
            // Messages without file name - always show if they pass the filter
            this._createLogEntry(message);
        }
    },

    /**
     * Create a new log entry in the container
     * @param {string} message - Message to log
     * @private
     */
    _createLogEntry(message) {
        const logContainer = DomHelpers.getElement('logContainer');
        if (!logContainer) return;

        const timestamp = new Date().toLocaleTimeString();

        // Check if this is a multi-line summary (contains "=== Translation Summary ===" or "=== Recommendations ===")
        const isMultiLineSummary = message.includes('=== Translation Summary ===') ||
                                   message.includes('=== Placeholder Issues ===') ||
                                   message.includes('=== Recommendations ===');

        let formattedMessage;
        if (isMultiLineSummary) {
            // Format multi-line summary with proper line breaks and styling
            formattedMessage = DomHelpers.escapeHtml(message)
                .replace(/\n/g, '<br>')
                .replace(/=== (.*?) ===/g, '<strong style="color: #3b82f6;">$1</strong>')
                .replace(/⚠️/g, '<span style="color: #f59e0b;">⚠️</span>')
                .replace(/✓/g, '<span style="color: #22c55e;">✓</span>')
                .replace(/✗/g, '<span style="color: #ef4444;">✗</span>')
                .replace(/•/g, '<span style="margin-left: 10px;">•</span>');
        } else {
            formattedMessage = DomHelpers.escapeHtml(message);
        }

        const logEntry = DomHelpers.createElement('div', {
            className: 'log-entry' + (isMultiLineSummary ? ' log-summary-detailed' : ''),
            innerHTML: `<span class="log-timestamp">[${timestamp}]</span> ${formattedMessage}`
        });

        logContainer.appendChild(logEntry);
        logContainer.scrollTop = logContainer.scrollHeight;
    },

    /**
     * Update or create a progress log entry (consolidates repetitive messages)
     * @param {string} fileName - Current file name
     * @param {string} message - Progress message
     * @private
     */
    updateProgressLog(fileName, message) {
        const logContainer = DomHelpers.getElement('logContainer');
        if (!logContainer) return;

        // If we already have a progress entry for this file, update it
        if (this.lastProgressEntry && this.lastProgressTimestamp) {
            const timestamp = this.lastProgressTimestamp;
            this.lastProgressEntry.innerHTML = `<span class="log-timestamp">[${timestamp}]</span> <span style="opacity: 0.7;">[${DomHelpers.escapeHtml(fileName)}]</span> ${DomHelpers.escapeHtml(message)}`;
        } else {
            // Create new progress entry
            const timestamp = new Date().toLocaleTimeString();
            this.lastProgressTimestamp = timestamp;
            this.lastProgressEntry = DomHelpers.createElement('div', {
                className: 'log-entry log-progress',
                innerHTML: `<span class="log-timestamp">[${timestamp}]</span> <span style="opacity: 0.7;">[${DomHelpers.escapeHtml(fileName)}]</span> ${DomHelpers.escapeHtml(message)}`
            });
            logContainer.appendChild(this.lastProgressEntry);
        }

        logContainer.scrollTop = logContainer.scrollHeight;
    },

    /**
     * Check if message should be consolidated (updated in-place)
     * @param {string} message - Message to check
     * @returns {boolean} True if should be consolidated
     * @private
     */
    shouldConsolidateMessage(message) {
        // Consolidate chunk progress messages
        const consolidatePatterns = [
            /^\d+\/\d+/,  // Progress like "5/100"
            /Translating chunk/i,
            /Processing chunk/i,
            /Chunk \d+/i,
            /Translation task started/i,
            /Translation in progress/i,
        ];

        return consolidatePatterns.some(pattern => pattern.test(message));
    },

    /**
     * Check if message is important enough to always show
     * @param {string} message - Message to check
     * @returns {boolean} True if important
     * @private
     */
    isImportantMessage(message) {
        // Important messages that should always be shown
        const importantPatterns = [
            /^✅/,  // Success
            /^❌/,  // Error
            /^⚠️/,  // Warning
            /^ℹ️/,  // Info
            /completed/i,
            /failed/i,
            /error/i,
            /warning/i,
            /started/i,
            /finished/i,
            /interrupted/i,
        ];

        return importantPatterns.some(pattern => pattern.test(message));
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
            this.resetProgressTracking();
            this.addLog('📝 Activity log cleared by user');
        }
    },

    /**
     * Reset progress tracking (call when translation completes or new file starts)
     */
    resetProgressTracking() {
        this.lastProgressEntry = null;
        this.lastProgressTimestamp = null;
        this.currentFileName = null;
    },

    /**
     * Check if message is a summary message that should be buffered and consolidated
     * @param {string} message - Message to check
     * @returns {boolean} True if is summary message
     * @private
     */
    isSummaryMessage(message) {
        const summaryPatterns = [
            /✅ EPUB translation complete:/,
            /✅ Translation completed in/,
            /🗑️ Removed .* from file list/,
            /🏁 All files in the batch/,
        ];

        return summaryPatterns.some(pattern => pattern.test(message));
    },

    /**
     * Buffer summary message and schedule consolidation
     * @param {string} message - Summary message to buffer
     * @private
     */
    bufferSummaryMessage(message) {
        this.summaryBuffer.push(message);

        // Clear existing timeout
        if (this.summaryTimeout) {
            clearTimeout(this.summaryTimeout);
        }

        // Schedule consolidation after 500ms of no new summary messages
        // Increased delay to handle EPUB translations with multiple files
        this.summaryTimeout = setTimeout(() => {
            this.flushSummaryBuffer();
        }, 500);
    },

    /**
     * Flush buffered summary messages as a single consolidated entry
     * @private
     */
    flushSummaryBuffer() {
        if (this.summaryBuffer.length === 0) {
            return;
        }

        const logContainer = DomHelpers.getElement('logContainer');
        if (!logContainer) {
            this.summaryBuffer = [];
            return;
        }

        // Extract file name from first message if present
        const firstMessage = this.summaryBuffer[0];
        const fileNameMatch = firstMessage.match(/^\[([^\]]+)\]/);
        const fileName = fileNameMatch ? fileNameMatch[1] : null;

        // Build consolidated summary
        const timestamp = new Date().toLocaleTimeString();
        let summaryHtml = `<span class="log-timestamp">[${timestamp}]</span> `;

        if (fileName) {
            summaryHtml += `<strong style="color: #22c55e;">✅ ${DomHelpers.escapeHtml(fileName)}</strong><br>`;
        }

        // Group messages by type
        const stats = [];
        const completion = [];
        const cleanup = [];

        for (const msg of this.summaryBuffer) {
            // Remove file name prefix for cleaner display
            let cleanMsg = msg.replace(/^\[([^\]]+)\]\s*/, '');

            if (cleanMsg.includes('Translation Summary') || cleanMsg.includes('Total chunks:') ||
                cleanMsg.includes('Success') || cleanMsg.includes('Untranslated')) {
                stats.push(cleanMsg);
            } else if (cleanMsg.includes('translation complete') || cleanMsg.includes('Translation completed')) {
                completion.push(cleanMsg);
            } else if (cleanMsg.includes('Removed') || cleanMsg.includes('All files in the batch')) {
                cleanup.push(cleanMsg);
            }
        }

        // Build compact summary
        const parts = [];

        // Add completion message
        if (completion.length > 0) {
            const mainCompletion = completion.find(m => m.includes('Translation completed in')) || completion[0];
            parts.push(`<span style="margin-left: 10px;">${DomHelpers.escapeHtml(mainCompletion)}</span>`);
        }

        // Add key stats (skip verbose details)
        if (stats.length > 0) {
            const totalChunks = stats.find(s => s.includes('Total chunks:'));
            const epubComplete = stats.find(s => s.includes('EPUB translation complete:'));

            if (epubComplete) {
                parts.push(`<span style="margin-left: 10px; opacity: 0.8;">${DomHelpers.escapeHtml(epubComplete)}</span>`);
            }
            if (totalChunks && !epubComplete) {
                parts.push(`<span style="margin-left: 10px; opacity: 0.8;">${DomHelpers.escapeHtml(totalChunks)}</span>`);
            }
        }

        // Add cleanup message if batch complete
        const batchComplete = cleanup.find(c => c.includes('All files in the batch'));
        if (batchComplete) {
            parts.push(`<span style="margin-left: 10px; color: #6366f1;">${DomHelpers.escapeHtml(batchComplete)}</span>`);
        }

        summaryHtml += parts.join('<br>');

        // Create consolidated log entry
        const logEntry = DomHelpers.createElement('div', {
            className: 'log-entry log-summary',
            innerHTML: summaryHtml
        });

        logContainer.appendChild(logEntry);
        logContainer.scrollTop = logContainer.scrollHeight;

        // Clear buffer
        this.summaryBuffer = [];
        this.summaryTimeout = null;
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

        let translatedText = translateMatch[1];

        // Remove placeholder tags for cleaner preview (UI only, not in console logs)
        // NOTE: These patterns must stay synchronized with src/config.py
        translatedText = translatedText.replace(/\[TAG\d+\]/g, '');  // HTML tag placeholders
        translatedText = translatedText.replace(/\[id\d+\]/g, '');   // Technical content placeholders
        // Also remove legacy Unicode format for backward compatibility
        translatedText = translatedText.replace(/⟦TAG\d+⟧/g, '');

        // Remove common leading whitespace (indentation) from all lines
        const lines = translatedText.split('\n');
        // Find minimum indentation (excluding empty lines)
        const minIndent = lines
            .filter(line => line.trim().length > 0)
            .reduce((min, line) => {
                const match = line.match(/^(\s*)/);
                const indent = match ? match[1].length : 0;
                return Math.min(min, indent);
            }, Infinity);

        // Remove the common indentation from all lines
        if (minIndent > 0 && minIndent !== Infinity) {
            translatedText = lines
                .map(line => line.substring(minIndent))
                .join('\n')
                .trim();
        } else {
            translatedText = translatedText.trim();
        }

        const previewHtml = `<div style="background: #ffffff; border-left: 3px solid #22c55e; padding: 15px; color: #000000; white-space: pre-wrap; line-height: 1.6;">${DomHelpers.escapeHtml(translatedText)}</div>`;

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
