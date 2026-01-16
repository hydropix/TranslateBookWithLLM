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
 * All file types (txt, epub, srt) show stats uniformly
 * @param {Object} stats - Statistics object from server
 * @param {string} fileType - File type ('txt', 'epub', 'srt')
 */
function updateStatistics(stats, fileType) {
    if (!stats) return;

    DomHelpers.show('statsGrid');

    if (fileType === 'srt') {
        DomHelpers.setText('totalChunks', stats.total_subtitles || '0');
        DomHelpers.setText('completedChunks', stats.completed_subtitles || '0');
        DomHelpers.setText('failedChunks', stats.failed_subtitles || '0');
    } else {
        // txt and epub use the same chunk-based stats
        DomHelpers.setText('totalChunks', stats.total_chunks || '0');
        DomHelpers.setText('completedChunks', stats.completed_chunks || '0');
        DomHelpers.setText('failedChunks', stats.failed_chunks || '0');
    }

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
     * Update statistics display
     * @param {string} fileType - File type ('txt', 'epub', 'srt')
     * @param {Object} stats - Statistics object from server
     */
    updateStats(fileType, stats) {
        updateStatistics(stats, fileType);
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
