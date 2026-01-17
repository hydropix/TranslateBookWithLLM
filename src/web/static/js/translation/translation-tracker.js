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
import { ProgressManager } from './progress-manager.js';
import { LifecycleManager } from '../utils/lifecycle-manager.js';

// Storage configuration with versioning
const STORAGE_VERSION = 1;
const STORAGE_KEY_PREFIX = 'tbl_translation_state';
const TRANSLATION_STATE_STORAGE_KEY = `${STORAGE_KEY_PREFIX}_v${STORAGE_VERSION}`;

/**
 * Validate translation state structure
 * @param {any} data - Data to validate
 * @returns {boolean} True if valid
 */
function validateTranslationState(data) {
    if (!data || typeof data !== 'object') return false;

    // Check required fields
    if (!('version' in data)) return false;
    if (!('currentJob' in data)) return false;
    if (!('isBatchActive' in data)) return false;
    if (!('activeJobs' in data)) return false;
    if (!('hasActive' in data)) return false;

    // Validate types
    if (typeof data.isBatchActive !== 'boolean') return false;
    if (typeof data.hasActive !== 'boolean') return false;
    if (!Array.isArray(data.activeJobs)) return false;

    // Validate currentJob if present
    if (data.currentJob !== null) {
        if (typeof data.currentJob !== 'object') return false;
        if (!('translationId' in data.currentJob)) return false;
        if (!('fileRef' in data.currentJob)) return false;
    }

    return true;
}

export const TranslationTracker = {
    // Debounce timer for saving state
    _saveStateTimer: null,
    _saveStateDebounceMs: 100,

    /**
     * Initialize translation tracker
     */
    async initialize() {
        // Clean up old storage versions
        this.cleanupOldStorageVersions();

        // Setup event listeners FIRST (they need to be ready before any state changes)
        this.setupEventListeners();

        // CRITICAL: Check server session BEFORE restoring state
        // This prevents restoring state from a previous server session
        try {
            const serverWasRestarted = await LifecycleManager.getServerSessionCheck();

            if (serverWasRestarted) {
                this.initializeDefaultTranslationState();
            } else {
                this.restoreTranslationStateSync();

                await Promise.all([
                    this.updateActiveTranslationsState(),
                    this.reconcileStateWithServer()
                ]);
            }
        } catch (error) {
            console.error('Failed to initialize translation state:', error);
            MessageLogger.addLog('⚠️ Could not fully restore previous session state');

            // Fallback: restore from localStorage anyway
            this.restoreTranslationStateSync();
        }

        // Mark initialization as complete
        this._initializationComplete = true;
    },

    /**
     * Check if initialization is complete
     * @returns {boolean} True if initialization is complete
     */
    isInitialized() {
        return this._initializationComplete === true;
    },

    /**
     * Clean up old localStorage versions
     */
    cleanupOldStorageVersions() {
        try {
            // Remove old non-versioned key
            const oldKey = 'tbl_translation_state';
            if (localStorage.getItem(oldKey)) {
                localStorage.removeItem(oldKey);
            }

            // Remove any other versions (future-proofing)
            for (let i = 0; i < STORAGE_VERSION; i++) {
                const oldVersionKey = `${STORAGE_KEY_PREFIX}_v${i}`;
                if (localStorage.getItem(oldVersionKey)) {
                    localStorage.removeItem(oldVersionKey);
                }
            }
        } catch (error) {
            console.warn('Failed to cleanup old storage versions:', error);
        }
    },

    /**
     * Restore translation state from localStorage synchronously
     * This ensures the UI shows the translation state immediately on page load
     */
    restoreTranslationStateSync() {
        try {
            const stored = localStorage.getItem(TRANSLATION_STATE_STORAGE_KEY);

            if (!stored) {
                this.initializeDefaultTranslationState();
                return;
            }

            const savedState = JSON.parse(stored);

            if (!validateTranslationState(savedState)) {
                MessageLogger.addLog('⚠️ Previous session state was corrupted, starting fresh');
                this.initializeDefaultTranslationState();
                this.clearTranslationState();
                return;
            }

            if (savedState.version !== STORAGE_VERSION) {
                this.initializeDefaultTranslationState();
                this.clearTranslationState();
                return;
            }

            if (savedState.isBatchActive && savedState.currentJob) {
                StateManager.setState('translation.currentJob', savedState.currentJob);
                StateManager.setState('translation.isBatchActive', savedState.isBatchActive);
                StateManager.setState('translation.activeJobs', savedState.activeJobs || []);
                StateManager.setState('translation.hasActive', savedState.hasActive || false);

                DomHelpers.show('progressSection');
                DomHelpers.show('interruptBtn');

                const translateBtn = DomHelpers.getElement('translateBtn');
                if (translateBtn) {
                    translateBtn.disabled = true;
                    translateBtn.innerHTML = '⏳ Batch in Progress...';
                }

                MessageLogger.addLog('🔄 Restored previous translation session');
            } else {
                this.initializeDefaultTranslationState();
            }
        } catch (error) {
            console.error('Failed to restore translation state from localStorage:', error);
            MessageLogger.addLog('⚠️ Could not restore previous session, starting fresh');
            this.initializeDefaultTranslationState();
        }
    },

    /**
     * Reconcile local state with server state
     * Checks if localStorage state matches server reality
     */
    async reconcileStateWithServer() {
        try {
            const currentJob = StateManager.getState('translation.currentJob');

            // If we have a local job, verify it exists on server
            if (currentJob && currentJob.translationId) {
                try {
                    const serverState = await ApiClient.getTranslationStatus(currentJob.translationId);

                    if (serverState.status === 'completed' ||
                        serverState.status === 'error' ||
                        serverState.status === 'interrupted') {

                        MessageLogger.addLog(`🔄 Syncing state: translation ${serverState.status} on server`);
                        this.resetUIToIdle();
                    } else if (serverState.status === 'running' || serverState.status === 'queued') {
                        // Calculate progress from stats if available
                        if (serverState.stats) {
                            this.updateStats(currentJob.fileRef.fileType, serverState.stats);
                        }
                    }
                } catch (error) {
                    if (error.status === 404) {
                        MessageLogger.addLog('⚠️ Translation job no longer exists, resetting');
                        this.resetUIToIdle();
                    }
                }
            }

            await this.restoreActiveTranslation();

        } catch (error) {
            console.warn('Failed to reconcile state with server:', error);
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
     * Save translation state to localStorage (debounced)
     */
    saveTranslationState() {
        // Clear existing timer
        if (this._saveStateTimer) {
            clearTimeout(this._saveStateTimer);
        }

        // Debounce to avoid multiple rapid saves
        this._saveStateTimer = setTimeout(() => {
            this._performSaveTranslationState();
        }, this._saveStateDebounceMs);
    },

    /**
     * Perform the actual save to localStorage
     * @private
     */
    _performSaveTranslationState() {
        try {
            const state = {
                version: STORAGE_VERSION,
                currentJob: StateManager.getState('translation.currentJob'),
                isBatchActive: StateManager.getState('translation.isBatchActive'),
                activeJobs: StateManager.getState('translation.activeJobs'),
                hasActive: StateManager.getState('translation.hasActive'),
                timestamp: Date.now()
            };

            localStorage.setItem(TRANSLATION_STATE_STORAGE_KEY, JSON.stringify(state));
        } catch (error) {
            console.error('Failed to save translation state to localStorage:', error);

            // Check if it's a quota exceeded error
            if (error.name === 'QuotaExceededError') {
                MessageLogger.addLog('⚠️ Browser storage full, could not save translation state');
            } else {
                MessageLogger.addLog('⚠️ Failed to save translation state');
            }
        }
    },

    /**
     * Clear translation state from localStorage
     */
    clearTranslationState() {
        try {
            // Clear any pending save
            if (this._saveStateTimer) {
                clearTimeout(this._saveStateTimer);
                this._saveStateTimer = null;
            }

            localStorage.removeItem(TRANSLATION_STATE_STORAGE_KEY);
        } catch (error) {
            console.error('Failed to clear translation state from localStorage:', error);
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
                let matchingFile = filesToProcess.find(f =>
                    f.translationId === job.translation_id ||
                    f.filePath === job.input_file ||
                    f.name === job.input_file?.split('/').pop()
                );

                // If no matching file found, create a virtual file reference from server data
                // This allows restoration after browser refresh even if filesToProcess is empty
                if (!matchingFile && job.input_filename) {
                    matchingFile = {
                        name: job.input_filename,
                        translationId: job.translation_id,
                        status: 'Processing',
                        type: job.file_type || 'txt',
                        isVirtual: true
                    };
                }

                if (matchingFile) {
                    StateManager.setState('translation.currentJob', {
                        fileRef: matchingFile,
                        translationId: job.translation_id
                    });
                    StateManager.setState('translation.isBatchActive', true);

                    DomHelpers.show('progressSection');
                    this.updateTranslationTitle(matchingFile);

                    // Calculate progress from stats (job contains total_chunks, completed_chunks, etc.)
                    if (job.total_chunks > 0) {
                        const stats = {
                            total_chunks: job.total_chunks,
                            completed_chunks: job.completed_chunks || 0,
                            failed_chunks: job.failed_chunks || 0,
                            elapsed_time: job.elapsed_time
                        };
                        this.updateStats(matchingFile.fileType, stats);
                    }

                    if (job.last_translation) {
                        MessageLogger.updateTranslationPreview(job.last_translation);
                    }

                    const translateBtn = DomHelpers.getElement('translateBtn');
                    if (translateBtn) {
                        translateBtn.disabled = true;
                        translateBtn.innerHTML = '⏳ Batch in Progress...';
                    }
                    DomHelpers.show('interruptBtn');

                    if (!matchingFile.isVirtual) {
                        this.updateFileStatusInList(matchingFile.name, 'Processing', job.translation_id);
                    }

                    break;
                }
            }
        } catch (error) {
            console.warn('Failed to restore active translation:', error);
        }
    },

    setupEventListeners() {
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
            if (data.translation_id && !currentJob) {
                if (data.status === 'completed' || data.status === 'error' || data.status === 'interrupted') {
                    this.resetUIToIdle();
                }
            }
            return;
        }

        const currentFile = currentJob.fileRef;

        if (data.log) {
            MessageLogger.addLog(`[${currentFile.name}] ${data.log}`);
        }

        // Progress is now calculated from stats in ProgressManager.update()
        // No need to call updateProgress() separately
        if (data.stats) {
            this.updateStats(currentFile.fileType, data.stats);
        }

        if (data.log_entry && data.log_entry.type === 'llm_response' &&
            data.log_entry.data && data.log_entry.data.response) {
            MessageLogger.updateTranslationPreview(data.log_entry.data.response);
        }

        if (data.status === 'completed') {
            MessageLogger.resetProgressTracking();
            this.finishCurrentFileTranslation(
                `✅ ${currentFile.name}: Translation completed!`,
                'success',
                data
            );
            this.updateActiveTranslationsState();
        } else if (data.status === 'interrupted') {
            MessageLogger.resetProgressTracking();
            this.finishCurrentFileTranslation(
                `ℹ️ ${currentFile.name}: Translation interrupted.`,
                'info',
                data
            );
            this.updateActiveTranslationsState();
        } else if (data.status === 'error') {
            MessageLogger.resetProgressTracking();
            this.finishCurrentFileTranslation(
                `❌ ${currentFile.name}: Error - ${data.error || 'Unknown error.'}`,
                'error',
                data
            );
            this.updateActiveTranslationsState();
        } else if (data.status === 'running') {
            MessageLogger.resetProgressTracking();
            DomHelpers.show('progressSection');
            DomHelpers.show('statsGrid');
            this.updateTranslationTitle(currentFile);
            this.resetOpenRouterCostDisplay();

            MessageLogger.showMessage(`Translation in progress for ${currentFile.name}...`, 'info');
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
        // Use ProgressManager.update() which calculates progress from stats
        ProgressManager.update({ stats: stats }, fileType);
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

        StateManager.setState('translation.currentJob', null);

        if (resultData.status === 'completed') {
            this.processNextFileInQueue();
        } else if (resultData.status === 'interrupted') {
            MessageLogger.addLog('🛑 Batch processing stopped by user.');
            this.resetUIToIdle();
        } else {
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

    resetUIToIdle() {
        StateManager.setState('translation.isBatchActive', false);
        StateManager.setState('translation.currentJob', null);

        this.clearTranslationState();

        DomHelpers.hide('interruptBtn');
        DomHelpers.setDisabled('interruptBtn', false);
        DomHelpers.setText('interruptBtn', '⏹️ Interrupt Current & Stop Batch');

        const filesToProcess = StateManager.getState('files.toProcess');
        DomHelpers.setDisabled('translateBtn', filesToProcess.length === 0 || !StatusManager.isConnected());
        DomHelpers.setText('translateBtn', '▶️ Start Translation Batch');

        if (filesToProcess.length === 0) {
            DomHelpers.hide('progressSection');
        }

        this.updateActiveTranslationsState();

        if (window.loadResumableJobs) {
            window.loadResumableJobs();
        }
    }
};
