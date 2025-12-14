/**
 * Translation Tracker - Track active translations and handle WebSocket updates
 *
 * Manages active translation state, WebSocket event handling,
 * translation completion, error handling, and batch queue progression.
 */

import { StateManager } from '../core/state-manager.js';
import { ApiClient } from '../core/api-client.js';
import { MessageLogger } from '../ui/message-logger.js';
import { DomHelpers } from '../ui/dom-helpers.js';

export const TranslationTracker = {
    /**
     * Initialize translation tracker
     */
    initialize() {
        this.setupEventListeners();
        this.updateActiveTranslationsState();
    },

    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Listen for state changes
        StateManager.subscribe('translation.currentJob', (job) => {
            if (job) {
                console.log('Current job updated:', job);
            }
        });

        StateManager.subscribe('translation.hasActive', (hasActive) => {
            console.log('Active translation state changed:', hasActive);
            this.updateResumeButtonsState();
        });
    },

    /**
     * Handle translation update from WebSocket
     * @param {Object} data - Translation update data
     */
    handleTranslationUpdate(data) {
        const currentJob = StateManager.getState('translation.currentJob');

        if (!currentJob || data.translation_id !== currentJob.translationId) {
            // Received update for a job that's not current - possible state inconsistency
            if (data.translation_id && !currentJob) {
                console.warn('Received translation update but no current job. Possible state desync.');
                // Check if we should reset UI
                if (data.status === 'completed' || data.status === 'error' || data.status === 'interrupted') {
                    console.log('Translation finished, ensuring UI is in idle state');
                    this.resetUIToIdle();
                }
            }
            return;
        }

        const currentFile = currentJob.fileRef;

        // Handle logs
        if (data.log) {
            MessageLogger.addLog(`[${currentFile.name}] ${data.log}`);
        }

        // Handle progress
        if (data.progress !== undefined) {
            this.updateProgress(data.progress);
        }

        // Handle stats
        if (data.stats) {
            this.updateStats(currentFile.fileType, data.stats);
        }

        // Handle structured log entries for translation preview
        if (data.log_entry && data.log_entry.type === 'llm_response' &&
            data.log_entry.data && data.log_entry.data.response) {
            MessageLogger.updateTranslationPreview(data.log_entry.data.response);
        }

        // Handle status changes
        if (data.status === 'completed') {
            this.finishCurrentFileTranslation(
                `✅ ${currentFile.name}: Translation completed!`,
                'success',
                data
            );
            this.updateActiveTranslationsState();
        } else if (data.status === 'interrupted') {
            this.finishCurrentFileTranslation(
                `ℹ️ ${currentFile.name}: Translation interrupted.`,
                'info',
                data
            );
            this.updateActiveTranslationsState();
        } else if (data.status === 'error') {
            this.finishCurrentFileTranslation(
                `❌ ${currentFile.name}: Error - ${data.error || 'Unknown error.'}`,
                'error',
                data
            );
            this.updateActiveTranslationsState();
        } else if (data.status === 'running') {
            DomHelpers.show('progressSection');
            DomHelpers.setText('currentFileProgressTitle', `📊 Translating: ${currentFile.name}`);

            // Reset OpenRouter cost display for new translation
            this.resetOpenRouterCostDisplay();

            if (currentFile.fileType === 'epub') {
                MessageLogger.showMessage(`Translating EPUB file: ${currentFile.name}... This may take some time.`, 'info');
                DomHelpers.hide('statsGrid');
            } else if (currentFile.fileType === 'srt') {
                MessageLogger.showMessage(`Translating SRT subtitle file: ${currentFile.name}...`, 'info');
                DomHelpers.show('statsGrid');
            } else {
                MessageLogger.showMessage(`Translation in progress for ${currentFile.name}...`, 'info');
                DomHelpers.show('statsGrid');
            }

            this.updateFileStatusInList(currentFile.name, 'Processing');
        }
    },

    /**
     * Update statistics display
     * @param {string} fileType - File type (txt, epub, srt)
     * @param {Object} stats - Statistics object
     */
    updateStats(fileType, stats) {
        if (fileType === 'epub') {
            DomHelpers.hide('statsGrid');
        } else if (fileType === 'srt') {
            DomHelpers.show('statsGrid');
            DomHelpers.setText('totalChunks', stats.total_subtitles || '0');
            DomHelpers.setText('completedChunks', stats.completed_subtitles || '0');
            DomHelpers.setText('failedChunks', stats.failed_subtitles || '0');
        } else {
            DomHelpers.show('statsGrid');
            DomHelpers.setText('totalChunks', stats.total_chunks || '0');
            DomHelpers.setText('completedChunks', stats.completed_chunks || '0');
            DomHelpers.setText('failedChunks', stats.failed_chunks || '0');
        }

        if (stats.elapsed_time !== undefined) {
            DomHelpers.setText('elapsedTime', stats.elapsed_time.toFixed(1) + 's');
        }

        // Update OpenRouter cost display if available
        this.updateOpenRouterCost(stats);
    },

    /**
     * Update OpenRouter cost display
     * @param {Object} stats - Statistics object containing cost data
     */
    updateOpenRouterCost(stats) {
        const costGrid = DomHelpers.getElement('openrouterCostGrid');
        if (!costGrid) return;

        const cost = stats.openrouter_cost || 0;
        const promptTokens = stats.openrouter_prompt_tokens || 0;
        const completionTokens = stats.openrouter_completion_tokens || 0;
        const totalTokens = promptTokens + completionTokens;

        // Show cost grid if there's any cost or token data
        if (cost > 0 || totalTokens > 0) {
            DomHelpers.show('openrouterCostGrid');
            DomHelpers.setText('openrouterCost', '$' + cost.toFixed(4));
            DomHelpers.setText('openrouterTokens', totalTokens.toLocaleString());
        }
    },

    /**
     * Reset OpenRouter cost display for a new translation
     */
    resetOpenRouterCostDisplay() {
        DomHelpers.hide('openrouterCostGrid');
        DomHelpers.setText('openrouterCost', '$0.0000');
        DomHelpers.setText('openrouterTokens', '0');
    },

    /**
     * Update progress bar
     * @param {number} percent - Progress percentage (0-100)
     */
    updateProgress(percent) {
        const progressBar = DomHelpers.getElement('progressBar');
        if (!progressBar) return;

        progressBar.style.width = percent + '%';
        DomHelpers.setText(progressBar, Math.round(percent) + '%');
    },

    /**
     * Update file status in UI list
     * @param {string} fileName - File name
     * @param {string} newStatus - New status text
     * @param {string} [translationId] - Translation ID
     */
    updateFileStatusInList(fileName, newStatus, translationId = null) {
        const fileListItem = DomHelpers.getOne(`#fileListContainer li[data-filename="${fileName}"] .file-status`);
        if (fileListItem) {
            DomHelpers.setText(fileListItem, `(${newStatus})`);
        }

        // Update in state
        const filesToProcess = StateManager.getState('files.toProcess');
        const fileObj = filesToProcess.find(f => f.name === fileName);
        if (fileObj) {
            fileObj.status = newStatus;
            if (translationId) {
                fileObj.translationId = translationId;
            }
            StateManager.setState('files.toProcess', filesToProcess);
        }
    },

    /**
     * Finish current file translation and update UI
     * @param {string} statusMessage - Status message to display
     * @param {string} messageType - Message type (success, error, info)
     * @param {Object} resultData - Translation result data
     */
    finishCurrentFileTranslation(statusMessage, messageType, resultData) {
        const currentJob = StateManager.getState('translation.currentJob');
        if (!currentJob) return;

        const currentFile = currentJob.fileRef;
        currentFile.status = resultData.status || 'unknown_error';
        currentFile.result = resultData.result;

        MessageLogger.showMessage(statusMessage, messageType);
        this.updateFileStatusInList(
            currentFile.name,
            resultData.status === 'completed' ? 'Completed' :
            (resultData.status === 'interrupted' ? 'Interrupted' : 'Error')
        );

        // Remove file from filesToProcess if translation completed or was interrupted
        if (resultData.status === 'completed' || resultData.status === 'interrupted') {
            this.removeFileFromProcessingList(currentFile.name);
        }

        // Clear current job
        StateManager.setState('translation.currentJob', null);

        // Only continue to next file if translation completed successfully (NOT if interrupted)
        if (resultData.status === 'completed') {
            this.processNextFileInQueue();
        } else if (resultData.status === 'interrupted') {
            // User stopped the translation - stop the entire batch
            MessageLogger.addLog('🛑 Batch processing stopped by user.');
            this.resetUIToIdle();
        } else {
            // Error case - continue to next file
            this.processNextFileInQueue();
        }
    },

    /**
     * Remove file from processing list
     * @param {string} filename - Filename to remove
     */
    removeFileFromProcessingList(filename) {
        const filesToProcess = StateManager.getState('files.toProcess');
        const fileIndex = filesToProcess.findIndex(f => f.name === filename);

        if (fileIndex !== -1) {
            filesToProcess.splice(fileIndex, 1);
            StateManager.setState('files.toProcess', filesToProcess);
            MessageLogger.addLog(`🗑️ Removed ${filename} from file list (source file cleaned up)`);
        }
    },

    /**
     * Process next file in queue (delegates to batch-controller when available)
     */
    processNextFileInQueue() {
        // Trigger event for batch controller to handle
        window.dispatchEvent(new CustomEvent('processNextFile'));
    },

    /**
     * Check and update active translations state
     */
    async updateActiveTranslationsState() {
        try {
            const response = await ApiClient.getActiveTranslations();
            const activeJobs = (response.translations || []).filter(
                t => t.status === 'running' || t.status === 'queued'
            );

            const wasActive = StateManager.getState('translation.hasActive');
            const hasActive = activeJobs.length > 0;

            StateManager.setState('translation.hasActive', hasActive);
            StateManager.setState('translation.activeJobs', activeJobs);

            // If state changed, update UI
            if (wasActive !== hasActive) {
                console.log('Active translation state changed:', hasActive);
                this.updateResumeButtonsState();
            }

            return { hasActive, activeJobs };
        } catch (error) {
            console.error('Error updating active translations state:', error);
            return {
                hasActive: StateManager.getState('translation.hasActive'),
                activeJobs: StateManager.getState('translation.activeJobs')
            };
        }
    },

    /**
     * Update the state of all resume buttons based on active translations
     */
    updateResumeButtonsState() {
        const resumeButtons = DomHelpers.getElements('button[onclick^="resumeJob"]');
        const hasActive = StateManager.getState('translation.hasActive');

        resumeButtons.forEach(button => {
            if (hasActive) {
                button.disabled = true;
                button.style.opacity = '0.5';
                button.style.cursor = 'not-allowed';
                button.title = '⚠️ Cannot resume: a translation is already in progress';
            } else {
                button.disabled = false;
                button.style.opacity = '1';
                button.style.cursor = 'pointer';
                button.title = 'Resume this translation';
            }
        });

        // Update warning banner
        this.updateResumableJobsWarningBanner();
    },

    /**
     * Update or create the warning banner in resumable jobs section
     */
    updateResumableJobsWarningBanner() {
        const listContainer = DomHelpers.getElement('resumableJobsList');
        if (!listContainer) return;

        const existingBanner = listContainer.querySelector('.active-translation-warning');
        const hasActive = StateManager.getState('translation.hasActive');
        const activeJobs = StateManager.getState('translation.activeJobs');

        if (hasActive) {
            const activeNames = activeJobs.map(t => t.output_filename || 'Unknown').join(', ');
            const bannerHtml = `
                <div class="active-translation-warning" style="background: #fef3c7; border: 1px solid #f59e0b; padding: 12px; margin-bottom: 15px; border-radius: 6px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 20px;">⚠️</span>
                        <div style="flex: 1;">
                            <strong style="color: #92400e;">Active translation in progress</strong>
                            <p style="margin: 5px 0 0 0; font-size: 13px; color: #78350f;">
                                Resume disabled. Active translation(s): ${DomHelpers.escapeHtml(activeNames)}
                            </p>
                        </div>
                    </div>
                </div>
            `;

            if (existingBanner) {
                existingBanner.outerHTML = bannerHtml;
            } else {
                // Insert at the beginning of the container
                listContainer.insertAdjacentHTML('afterbegin', bannerHtml);
            }
        } else if (existingBanner) {
            // Remove banner if no active translations
            existingBanner.remove();
        }
    },

    /**
     * Reset UI state to idle (no active translation)
     */
    resetUIToIdle() {
        console.log('Resetting UI to idle state...');

        // Reset state variables
        StateManager.setState('translation.isBatchActive', false);
        StateManager.setState('translation.currentJob', null);

        // Reset UI elements
        DomHelpers.hide('interruptBtn');
        DomHelpers.setDisabled('interruptBtn', false);
        DomHelpers.setText('interruptBtn', '⏹️ Interrupt Current & Stop Batch');

        const filesToProcess = StateManager.getState('files.toProcess');
        DomHelpers.setDisabled('translateBtn', filesToProcess.length === 0);
        DomHelpers.setText('translateBtn', '▶️ Start Translation Batch');

        // Hide progress section if no files to process
        if (filesToProcess.length === 0) {
            DomHelpers.hide('progressSection');
        }

        // Update active translations state
        this.updateActiveTranslationsState();

        // Reload resumable jobs to show any newly created checkpoints
        if (window.loadResumableJobs) {
            window.loadResumableJobs();
        }

        MessageLogger.addLog('🔄 UI reset to idle state');
    }
};
