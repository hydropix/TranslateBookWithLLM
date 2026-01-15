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
import { StatusManager } from '../utils/status-manager.js';
import { FileUpload } from '../files/file-upload.js';

const TRANSLATION_STATE_STORAGE_KEY = 'tbl_translation_state';

export const TranslationTracker = {
    /**
     * Initialize translation tracker
     */
    initialize() {
        this.setupEventListeners();
        // First, try to restore from localStorage synchronously
        this.restoreTranslationStateSync();
        this.updateActiveTranslationsState();
        // Then verify with server after a short delay to allow file queue to restore first
        setTimeout(() => this.restoreActiveTranslation(), 1500);
    },

    /**
     * Restore translation state from localStorage synchronously
     * This ensures the UI shows the translation state immediately on page load
     */
    restoreTranslationStateSync() {
        try {
            const stored = localStorage.getItem(TRANSLATION_STATE_STORAGE_KEY);

            if (!stored) {
                // No saved state, initialize defaults
                this.initializeDefaultTranslationState();
                return;
            }

            const savedState = JSON.parse(stored);

            // Only restore if there's an active job saved
            if (savedState.isBatchActive && savedState.currentJob) {
                StateManager.setState('translation.currentJob', savedState.currentJob);
                StateManager.setState('translation.isBatchActive', savedState.isBatchActive);
                StateManager.setState('translation.activeJobs', savedState.activeJobs || []);
                StateManager.setState('translation.hasActive', savedState.hasActive || false);

                // Show progress section
                DomHelpers.show('progressSection');
                DomHelpers.show('interruptBtn');

                // Update translate button
                const translateBtn = DomHelpers.getElement('translateBtn');
                if (translateBtn) {
                    translateBtn.disabled = true;
                    translateBtn.innerHTML = '⏳ Batch in Progress...';
                }
            } else {
                // Saved state exists but no active job, initialize defaults
                this.initializeDefaultTranslationState();
            }
        } catch (error) {
            console.warn('Failed to restore translation state from localStorage:', error);
            this.initializeDefaultTranslationState();
        }
    },

    /**
     * Initialize default translation state (when no saved state exists)
     */
    initializeDefaultTranslationState() {
        StateManager.setState('translation.currentJob', null);
        StateManager.setState('translation.isBatchActive', false);
        StateManager.setState('translation.activeJobs', []);
        StateManager.setState('translation.hasActive', false);
    },

    /**
     * Save translation state to localStorage
     */
    saveTranslationState() {
        try {
            const state = {
                currentJob: StateManager.getState('translation.currentJob'),
                isBatchActive: StateManager.getState('translation.isBatchActive'),
                activeJobs: StateManager.getState('translation.activeJobs'),
                hasActive: StateManager.getState('translation.hasActive')
            };
            localStorage.setItem(TRANSLATION_STATE_STORAGE_KEY, JSON.stringify(state));
        } catch (error) {
            console.warn('Failed to save translation state to localStorage:', error);
        }
    },

    /**
     * Clear translation state from localStorage
     */
    clearTranslationState() {
        try {
            localStorage.removeItem(TRANSLATION_STATE_STORAGE_KEY);
        } catch (error) {
            console.warn('Failed to clear translation state from localStorage:', error);
        }
    },

    /**
     * Restore active translation state if there's one running on the server
     */
    async restoreActiveTranslation() {
        try {
            const response = await ApiClient.getActiveTranslations();
            const activeJobs = (response.translations || []).filter(
                t => t.status === 'running' || t.status === 'queued'
            );

            if (activeJobs.length === 0) return;

            // Find matching file in our queue
            const filesToProcess = StateManager.getState('files.toProcess') || [];

            for (const job of activeJobs) {
                const matchingFile = filesToProcess.find(f =>
                    f.translationId === job.translation_id ||
                    f.filePath === job.input_file ||
                    f.name === job.input_file?.split('/').pop()
                );

                if (matchingFile) {

                    // Restore state
                    StateManager.setState('translation.currentJob', {
                        fileRef: matchingFile,
                        translationId: job.translation_id
                    });
                    StateManager.setState('translation.isBatchActive', true);

                    // Update UI
                    this.updateFileStatusInList(matchingFile.name, 'Processing', job.translation_id);
                    DomHelpers.show('progressSection');
                    this.updateTranslationTitle(matchingFile);

                    // Update progress if available
                    if (job.progress !== undefined) {
                        this.updateProgress(job.progress);
                    }

                    // Update button states
                    const translateBtn = DomHelpers.getElement('translateBtn');
                    if (translateBtn) {
                        translateBtn.disabled = true;
                        translateBtn.innerHTML = '⏳ Batch in Progress...';
                    }
                    DomHelpers.show('interruptBtn');

                    break;
                }
            }
        } catch {
            // Failed to restore active translation
        }
    },

    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Listen for state changes and auto-save to localStorage
        StateManager.subscribe('translation.currentJob', () => {
            this.saveTranslationState();
        });

        StateManager.subscribe('translation.isBatchActive', () => {
            this.saveTranslationState();
        });

        StateManager.subscribe('translation.hasActive', () => {
            this.updateResumeButtonsState();
            this.saveTranslationState();
        });

        StateManager.subscribe('translation.activeJobs', () => {
            this.saveTranslationState();
        });
    },

    /**
     * Handle translation update from WebSocket
     * @param {Object} data - Translation update data
     */
    handleTranslationUpdate(data) {
        const currentJob = StateManager.getState('translation.currentJob');

        if (!currentJob || data.translation_id !== currentJob.translationId) {
            // Check if we should reset UI for finished jobs
            if (data.translation_id && !currentJob) {
                if (data.status === 'completed' || data.status === 'error' || data.status === 'interrupted') {
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
            MessageLogger.resetProgressTracking(); // Reset before showing completion message
            this.finishCurrentFileTranslation(
                `✅ ${currentFile.name}: Translation completed!`,
                'success',
                data
            );
            this.updateActiveTranslationsState();
        } else if (data.status === 'interrupted') {
            MessageLogger.resetProgressTracking(); // Reset before showing interruption message
            this.finishCurrentFileTranslation(
                `ℹ️ ${currentFile.name}: Translation interrupted.`,
                'info',
                data
            );
            this.updateActiveTranslationsState();
        } else if (data.status === 'error') {
            MessageLogger.resetProgressTracking(); // Reset before showing error message
            this.finishCurrentFileTranslation(
                `❌ ${currentFile.name}: Error - ${data.error || 'Unknown error.'}`,
                'error',
                data
            );
            this.updateActiveTranslationsState();
        } else if (data.status === 'running') {
            MessageLogger.resetProgressTracking(); // Reset when starting new translation
            DomHelpers.show('progressSection');
            this.updateTranslationTitle(currentFile);

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
     * Update translation title with file icon/thumbnail and name
     * @param {Object} file - File object
     */
    updateTranslationTitle(file) {
        const titleElement = DomHelpers.getElement('currentFileProgressTitle');
        if (!titleElement) return;

        // Clear existing content
        titleElement.innerHTML = '';

        // Create main container with vertical layout
        const mainContainer = document.createElement('div');
        mainContainer.style.display = 'flex';
        mainContainer.style.flexDirection = 'column';
        mainContainer.style.gap = '8px';

        // Add "Translating" text
        const translatingText = document.createElement('div');
        translatingText.textContent = 'Translating';
        translatingText.style.fontWeight = 'bold';
        mainContainer.appendChild(translatingText);

        // Create file info container (icon + filename)
        const fileInfoContainer = document.createElement('div');
        fileInfoContainer.style.display = 'flex';
        fileInfoContainer.style.alignItems = 'center';
        fileInfoContainer.style.gap = '8px';

        // Icon/thumbnail container
        const iconContainer = document.createElement('span');
        iconContainer.style.display = 'inline-flex';
        iconContainer.style.alignItems = 'center';
        iconContainer.style.fontSize = '24px';

        if (file.fileType === 'epub' && file.thumbnail) {
            // Show thumbnail
            const img = document.createElement('img');
            img.src = `/api/thumbnails/${encodeURIComponent(file.thumbnail)}`;
            img.alt = 'Cover';
            img.style.width = '48px';
            img.style.height = '72px';
            img.style.objectFit = 'cover';
            img.style.borderRadius = '3px';
            img.style.boxShadow = '0 2px 4px rgba(0,0,0,0.2)';

            // Fallback to generic SVG on error
            img.onerror = () => {
                iconContainer.innerHTML = this._createGenericEPUBIcon();
            };

            iconContainer.appendChild(img);
        } else {
            // Generic icons
            iconContainer.innerHTML = this._getFileIcon(file.fileType);
        }

        fileInfoContainer.appendChild(iconContainer);

        // File name (split name and extension)
        const fileNameContainer = document.createElement('div');
        fileNameContainer.style.display = 'flex';
        fileNameContainer.style.flexDirection = 'column';
        fileNameContainer.style.gap = '4px';

        // Split filename and extension
        const lastDotIndex = file.name.lastIndexOf('.');
        const fileNameWithoutExt = lastDotIndex > 0 ? file.name.substring(0, lastDotIndex) : file.name;
        const fileExt = lastDotIndex > 0 ? file.name.substring(lastDotIndex) : '';

        // Create container for name + extension
        const nameRow = document.createElement('div');
        nameRow.style.display = 'flex';
        nameRow.style.alignItems = 'baseline';
        nameRow.style.gap = '2px';

        // File name (bold and larger)
        const fileNameSpan = document.createElement('span');
        fileNameSpan.textContent = fileNameWithoutExt;
        fileNameSpan.style.fontSize = '18px';
        fileNameSpan.style.fontWeight = 'bold';
        nameRow.appendChild(fileNameSpan);

        // Extension (normal size)
        if (fileExt) {
            const extSpan = document.createElement('span');
            extSpan.textContent = fileExt;
            extSpan.style.fontSize = '14px';
            extSpan.style.color = 'var(--text-muted-light)';
            nameRow.appendChild(extSpan);
        }

        fileNameContainer.appendChild(nameRow);

        // Language info (source → target)
        if (file.sourceLanguage && file.targetLanguage) {
            const langSpan = document.createElement('div');
            langSpan.textContent = `${file.sourceLanguage} → ${file.targetLanguage}`;
            langSpan.style.fontSize = '12px';
            langSpan.style.color = 'var(--text-muted-light)';
            langSpan.style.fontWeight = 'normal';
            fileNameContainer.appendChild(langSpan);
        }

        fileInfoContainer.appendChild(fileNameContainer);

        // Add file info to main container
        mainContainer.appendChild(fileInfoContainer);

        // Add main container to title element
        titleElement.appendChild(mainContainer);
    },

    /**
     * Get file icon based on file type
     * @param {string} fileType - File type ('txt', 'epub', 'srt')
     * @returns {string} HTML string for icon
     */
    _getFileIcon(fileType) {
        if (fileType === 'epub') {
            return this._createGenericEPUBIcon();
        } else if (fileType === 'srt') {
            return '🎬';
        }
        return '📄';
    },

    /**
     * Create generic EPUB icon as SVG
     * @returns {string} SVG HTML string
     */
    _createGenericEPUBIcon() {
        return `
            <svg style="width: 48px; height: 72px;" viewBox="0 0 48 72" xmlns="http://www.w3.org/2000/svg">
                <!-- Book cover -->
                <rect x="6" y="3" width="36" height="66" rx="2.5"
                      fill="#5a8ee8" stroke="#3676d8" stroke-width="2"/>
                <!-- Book spine line -->
                <path d="M6 13 L42 13" stroke="#3676d8" stroke-width="1.8"/>
                <!-- Text lines -->
                <path d="M10 22 L38 22 M10 32 L38 32 M10 42 L32 42"
                      stroke="white" stroke-width="2.2" stroke-linecap="round" opacity="0.8"/>
                <!-- EPUB badge -->
                <circle cx="24" cy="56" r="5" fill="white" opacity="0.9"/>
                <text x="24" y="60" text-anchor="middle" font-size="6"
                      fill="#3676d8" font-weight="bold">E</text>
            </svg>
        `;
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
            // Persist to localStorage
            FileUpload.notifyFileListChanged();
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

        // Note: File is now removed from the list when translation starts,
        // not when it completes (see batch-controller.js)

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
                this.updateResumeButtonsState();
            }

            return { hasActive, activeJobs };
        } catch {
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

        // Reset state variables
        StateManager.setState('translation.isBatchActive', false);
        StateManager.setState('translation.currentJob', null);

        // Clear saved state from localStorage
        this.clearTranslationState();

        // Reset UI elements
        DomHelpers.hide('interruptBtn');
        DomHelpers.setDisabled('interruptBtn', false);
        DomHelpers.setText('interruptBtn', '⏹️ Interrupt Current & Stop Batch');

        const filesToProcess = StateManager.getState('files.toProcess');
        DomHelpers.setDisabled('translateBtn', filesToProcess.length === 0 || !StatusManager.isConnected());
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
    }
};
