/**
 * Progress Manager - Translation progress tracking and display
 *
 * Manages progress bar updates and statistics display for active translations.
 * Supports different file types (text, EPUB, SRT) with appropriate stat labels.
 */

import { DomHelpers } from '../ui/dom-helpers.js';

/**
 * Update progress bar
 * @param {number} percent - Progress percentage (0-100)
 */
function updateProgressBar(percent) {
    const progressBar = DomHelpers.getElement('progressBar');

    if (progressBar) {
        progressBar.style.width = percent + '%';
        progressBar.textContent = Math.round(percent) + '%';
    }
}

/**
 * Update statistics display based on file type
 * @param {Object} stats - Statistics object from server
 * @param {string} fileType - File type ('txt', 'epub', 'srt')
 */
function updateStatistics(stats, fileType) {
    if (!stats) return;

    const statsGrid = DomHelpers.getElement('statsGrid');

    if (fileType === 'epub') {
        // Hide stats for EPUB (no chunk-based tracking)
        DomHelpers.hide('statsGrid');
    } else if (fileType === 'srt') {
        // Show subtitle-specific stats
        DomHelpers.show('statsGrid');
        DomHelpers.setText('totalChunks', stats.total_subtitles || '0');
        DomHelpers.setText('completedChunks', stats.completed_subtitles || '0');
        DomHelpers.setText('failedChunks', stats.failed_subtitles || '0');
    } else {
        // Show chunk-based stats (text files)
        DomHelpers.show('statsGrid');
        DomHelpers.setText('totalChunks', stats.total_chunks || '0');
        DomHelpers.setText('completedChunks', stats.completed_chunks || '0');
        DomHelpers.setText('failedChunks', stats.failed_chunks || '0');
    }

    // Update elapsed time (common for all types)
    if (stats.elapsed_time !== undefined) {
        DomHelpers.setText('elapsedTime', stats.elapsed_time.toFixed(1) + 's');
    }
}

export const ProgressManager = {
    /**
     * Update progress display
     * @param {number} percent - Progress percentage (0-100)
     */
    updateProgress(percent) {
        updateProgressBar(percent);
    },

    /**
     * Update progress and statistics together
     * @param {Object} data - Update data from server
     * @param {number} data.progress - Progress percentage
     * @param {Object} data.stats - Statistics object
     * @param {string} fileType - File type ('txt', 'epub', 'srt')
     */
    update(data, fileType) {
        if (data.progress !== undefined) {
            updateProgressBar(data.progress);
        }

        if (data.stats) {
            updateStatistics(data.stats, fileType);
        }
    },

    /**
     * Reset progress display to initial state
     */
    reset() {
        updateProgressBar(0);
        DomHelpers.setText('totalChunks', '0');
        DomHelpers.setText('completedChunks', '0');
        DomHelpers.setText('failedChunks', '0');
        DomHelpers.setText('elapsedTime', '0s');
        DomHelpers.hide('statsGrid');
        // Reset chunk statistics panel
        this.hideChunkStatistics();
    },

    /**
     * Update chunk statistics display (T052)
     * @param {Object} chunkStats - Chunk statistics data
     */
    updateChunkStatistics(chunkStats) {
        const panel = DomHelpers.getElement('chunkStatisticsPanel');
        if (!panel) return;

        if (chunkStats) {
            DomHelpers.setText('chunkAvgSize', chunkStats.avgSize || '-');
            DomHelpers.setText('chunkSizeRange', chunkStats.sizeRange || '-');
            DomHelpers.setText('chunkWithinTolerance', chunkStats.withinTolerance || '-');
            DomHelpers.setText('chunkOversized', chunkStats.oversized || '0');
            panel.style.display = 'block';
        }
    },

    /**
     * Hide chunk statistics panel
     */
    hideChunkStatistics() {
        const panel = DomHelpers.getElement('chunkStatisticsPanel');
        if (panel) {
            panel.style.display = 'none';
        }
    },

    /**
     * Parse chunk statistics from log message (T052)
     * @param {string} message - Log message
     * @returns {Object|null} Parsed chunk statistics or null
     */
    parseChunkStatisticsFromLog(message) {
        // Parse: "📊 Chunk Statistics: X chunks, avg Y chars (Z-W range), A.B% within tolerance, C oversized"
        const summaryMatch = message.match(/📊 Chunk Statistics: (\d+) chunks, avg (\d+) chars \((\d+)-(\d+) range\), ([\d.]+)% within tolerance(?:, (\d+) oversized)?/);
        if (summaryMatch) {
            return {
                totalChunks: summaryMatch[1],
                avgSize: summaryMatch[2] + ' chars',
                sizeRange: summaryMatch[3] + '-' + summaryMatch[4] + ' chars',
                withinTolerance: summaryMatch[5] + '%',
                oversized: summaryMatch[6] || '0'
            };
        }

        // Alternative pattern for simpler summary
        const simpleMatch = message.match(/Total: (\d+) chunks, Size range: (\d+)-(\d+) chars/);
        if (simpleMatch) {
            return {
                totalChunks: simpleMatch[1],
                sizeRange: simpleMatch[2] + '-' + simpleMatch[3] + ' chars'
            };
        }

        return null;
    },

    /**
     * Show progress section
     */
    show() {
        DomHelpers.show('progressSection');
    },

    /**
     * Hide progress section
     */
    hide() {
        DomHelpers.hide('progressSection');
    },

    /**
     * Set progress to complete (100%)
     */
    complete() {
        updateProgressBar(100);
    },

    /**
     * Get current progress percentage
     * @returns {number} Current progress (0-100)
     */
    getCurrentProgress() {
        const progressBar = DomHelpers.getElement('progressBar');

        if (!progressBar) return 0;

        const widthStyle = progressBar.style.width;
        const match = widthStyle.match(/(\d+(?:\.\d+)?)/);

        return match ? parseFloat(match[1]) : 0;
    }
};
