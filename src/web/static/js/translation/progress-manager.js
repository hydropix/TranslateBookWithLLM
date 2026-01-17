/**
 * Progress Manager - Translation progress tracking and display
 *
 * Manages progress bar updates and statistics display for active translations.
 * Supports different file types (text, EPUB, SRT) with appropriate stat labels.
 */

import { DomHelpers } from '../ui/dom-helpers.js';

// State for tracking chunk completion times (for ETA calculation)
let chunkCompletionTimes = [];
let lastCompletedChunks = 0;
let lastElapsedTime = 0;
const MAX_SAMPLES = 10; // Number of recent chunks to average for ETA

/**
 * Format elapsed time in a human-readable format
 * - Under 60s: shows seconds (e.g., "45.2s")
 * - Under 1h: shows minutes and seconds (e.g., "5m 23s")
 * - 1h+: shows hours, minutes and seconds (e.g., "1h 23m 45s")
 * @param {number} seconds - Elapsed time in seconds
 * @returns {string} Formatted time string
 */
function formatElapsedTime(seconds) {
    if (seconds < 60) {
        return seconds.toFixed(1) + 's';
    }

    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
        return `${hours}h ${minutes}m ${secs}s`;
    }

    return `${minutes}m ${secs}s`;
}

/**
 * Calculate and update estimated time remaining
 * Uses a moving average of the last N chunk completion times
 * @param {number} completedChunks - Number of completed chunks
 * @param {number} totalChunks - Total number of chunks
 * @param {number} elapsedTime - Total elapsed time in seconds
 */
function updateEstimatedTimeRemaining(completedChunks, totalChunks, elapsedTime) {
    // Track time per chunk when a new chunk is completed
    if (completedChunks > lastCompletedChunks && elapsedTime > lastElapsedTime) {
        const chunksCompleted = completedChunks - lastCompletedChunks;
        const timeTaken = elapsedTime - lastElapsedTime;
        const timePerChunk = timeTaken / chunksCompleted;

        chunkCompletionTimes.push(timePerChunk);

        // Keep only the last N samples
        if (chunkCompletionTimes.length > MAX_SAMPLES) {
            chunkCompletionTimes.shift();
        }
    }

    lastCompletedChunks = completedChunks;
    lastElapsedTime = elapsedTime;

    // Calculate ETA only if we have samples
    if (chunkCompletionTimes.length === 0 || completedChunks === 0) {
        DomHelpers.setText('estimatedTimeRemaining', '--');
        return;
    }

    const remainingChunks = totalChunks - completedChunks;

    if (remainingChunks <= 0) {
        DomHelpers.setText('estimatedTimeRemaining', '0s');
        return;
    }

    // Calculate average time per chunk from recent samples
    const avgTimePerChunk = chunkCompletionTimes.reduce((a, b) => a + b, 0) / chunkCompletionTimes.length;
    const estimatedRemaining = avgTimePerChunk * remainingChunks;

    DomHelpers.setText('estimatedTimeRemaining', formatElapsedTime(estimatedRemaining));
}

/**
 * Reset ETA tracking state
 */
function resetEtaTracking() {
    chunkCompletionTimes = [];
    lastCompletedChunks = 0;
    lastElapsedTime = 0;
}

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
        DomHelpers.setText('elapsedTime', formatElapsedTime(stats.elapsed_time));

        // Update ETA based on chunk progress
        const completed = fileType === 'srt'
            ? (stats.completed_subtitles || 0)
            : (stats.completed_chunks || 0);
        const total = fileType === 'srt'
            ? (stats.total_subtitles || 0)
            : (stats.total_chunks || 0);

        updateEstimatedTimeRemaining(completed, total, stats.elapsed_time);
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
        DomHelpers.setText('estimatedTimeRemaining', '--');
        resetEtaTracking();
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
