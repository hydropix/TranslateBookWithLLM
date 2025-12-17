/**
 * Main Application Entry Point
 *
 * Coordinates all modules and initializes the translation application.
 * This file serves as the central coordinator for the modular architecture.
 */

// ========================================
// Core Infrastructure
// ========================================
import { StateManager } from './core/state-manager.js';
import { ApiClient } from './core/api-client.js';
import { WebSocketManager } from './core/websocket-manager.js';
import { SettingsManager } from './core/settings-manager.js';

// ========================================
// UI Modules
// ========================================
import { DomHelpers } from './ui/dom-helpers.js';
import { MessageLogger } from './ui/message-logger.js';
import { FormManager } from './ui/form-manager.js';

// ========================================
// Provider Modules
// ========================================
import { ProviderManager } from './providers/provider-manager.js';
import { ModelDetector } from './providers/model-detector.js';

// ========================================
// File Management Modules
// ========================================
import { FileUpload } from './files/file-upload.js';
import { FileManager } from './files/file-manager.js';

// ========================================
// Translation Modules
// ========================================
import { TranslationTracker } from './translation/translation-tracker.js';
import { BatchController } from './translation/batch-controller.js';
import { ProgressManager } from './translation/progress-manager.js';
import { ResumeManager } from './translation/resume-manager.js';

// ========================================
// Utilities
// ========================================
import { Validators } from './utils/validators.js';
import { LifecycleManager } from './utils/lifecycle-manager.js';

// ========================================
// TTS Event Handler
// ========================================

/**
 * Handle TTS update events from WebSocket
 * @param {Object} data - TTS update data
 */
function handleTtsUpdate(data) {
    const { status, progress, message, audio_filename, error, current_chunk, total_chunks } = data;

    // Update TTS progress section
    const ttsProgressSection = DomHelpers.getElement('ttsProgressSection');
    const ttsProgressBar = DomHelpers.getElement('ttsProgressBar');
    const ttsStatusText = DomHelpers.getElement('ttsStatusText');

    switch (status) {
        case 'started':
            // Show TTS progress section
            if (ttsProgressSection) {
                ttsProgressSection.style.display = 'block';
            }
            if (ttsProgressBar) {
                ttsProgressBar.style.width = '0%';
                ttsProgressBar.textContent = '0%';
            }
            if (ttsStatusText) {
                ttsStatusText.textContent = '🔊 Starting audio generation...';
            }
            MessageLogger.addLog('🔊 TTS generation started');
            break;

        case 'processing':
            if (ttsProgressBar) {
                ttsProgressBar.style.width = `${progress}%`;
                ttsProgressBar.textContent = `${progress}%`;
            }
            if (ttsStatusText) {
                const chunkInfo = current_chunk && total_chunks
                    ? ` (${current_chunk}/${total_chunks})`
                    : '';
                ttsStatusText.textContent = `🔊 ${message || 'Generating audio...'}${chunkInfo}`;
            }
            break;

        case 'completed':
            if (ttsProgressBar) {
                ttsProgressBar.style.width = '100%';
                ttsProgressBar.textContent = '100%';
            }
            if (ttsStatusText) {
                ttsStatusText.textContent = `✅ Audio generated: ${audio_filename || 'audio file'}`;
            }
            MessageLogger.addLog(`✅ TTS completed: ${audio_filename || 'audio file'}`);

            // Auto-hide after 5 seconds
            setTimeout(() => {
                if (ttsProgressSection) {
                    ttsProgressSection.style.display = 'none';
                }
            }, 5000);
            break;

        case 'failed':
            if (ttsProgressBar) {
                ttsProgressBar.style.width = '0%';
                ttsProgressBar.textContent = 'Failed';
                ttsProgressBar.style.background = '#ef4444';
            }
            if (ttsStatusText) {
                ttsStatusText.textContent = `❌ TTS failed: ${error || message || 'Unknown error'}`;
            }
            MessageLogger.addLog(`❌ TTS failed: ${error || message || 'Unknown error'}`);
            break;
    }
}

// ========================================
// Global State Initialization
// ========================================

/**
 * Initialize application state
 */
function initializeState() {
    // Files state
    StateManager.setState('files.toProcess', []);
    StateManager.setState('files.selected', []);
    StateManager.setState('files.managed', []);

    // Translation state
    StateManager.setState('translation.currentJob', null);
    StateManager.setState('translation.isBatchActive', false);
    StateManager.setState('translation.activeJobs', []);
    StateManager.setState('translation.hasActive', false);

    // UI state
    StateManager.setState('ui.currentProvider', 'ollama');
    StateManager.setState('ui.currentModel', '');
    StateManager.setState('ui.messages', []);

    // Models state
    StateManager.setState('models.currentLoadRequest', null);
    StateManager.setState('models.availableModels', []);
}

// ========================================
// Event Wiring
// ========================================

/**
 * Wire up cross-module events
 */
function wireModuleEvents() {
    // File list changed -> update display
    window.addEventListener('fileListChanged', () => {
        FileUpload.updateFileDisplay();
    });

    // File status changed -> update display
    window.addEventListener('fileStatusChanged', () => {
        FileUpload.updateFileDisplay();
    });

    // Translation started -> update active translations state
    window.addEventListener('translationStarted', () => {
        TranslationTracker.updateActiveTranslationsState();
    });

    // Translation resumed -> update active translations state
    window.addEventListener('translationResumed', () => {
        TranslationTracker.updateActiveTranslationsState();
    });

    // Translation completed -> process next in queue
    window.addEventListener('translationCompleted', () => {
        BatchController.processNextFileInQueue();
    });

    // Translation error -> process next in queue
    window.addEventListener('translationError', () => {
        BatchController.processNextFileInQueue();
    });

    // Process next file in queue (from TranslationTracker)
    window.addEventListener('processNextFile', () => {
        BatchController.processNextFileInQueue();
    });

    // WebSocket events -> module handlers
    WebSocketManager.on('connect', () => {
        // Only refresh models if we don't have any loaded yet
        const hasModels = StateManager.getState('models.availableModels')?.length > 0;
        if (!hasModels) {
            ProviderManager.refreshModels();
        }

        ResumeManager.loadResumableJobs();
        FileManager.refreshFileList();
        TranslationTracker.updateActiveTranslationsState();
    });

    WebSocketManager.on('translation_update', (data) => {
        TranslationTracker.handleTranslationUpdate(data);
    });

    WebSocketManager.on('file_list_changed', (data) => {
        FileManager.refreshFileList();
    });

    WebSocketManager.on('checkpoint_created', (data) => {
        ResumeManager.loadResumableJobs();
    });

    // TTS update events
    WebSocketManager.on('tts_update', (data) => {
        handleTtsUpdate(data);
    });

    // State changes -> update UI
    StateManager.subscribe('translation.isBatchActive', (isActive) => {
        const translateBtn = DomHelpers.getElement('translateBtn');
        if (translateBtn) {
            translateBtn.disabled = isActive;
        }
    });

    StateManager.subscribe('translation.hasActive', (hasActive) => {
        TranslationTracker.updateResumeButtonsState();
    });

    StateManager.subscribe('files.toProcess', (files) => {
        const translateBtn = DomHelpers.getElement('translateBtn');
        if (translateBtn && !StateManager.getState('translation.isBatchActive')) {
            translateBtn.disabled = files.length === 0;
        }
    });
}

// ========================================
// Module Initialization
// ========================================

/**
 * Initialize all modules in proper order
 */
function initializeModules() {
    console.log('🚀 Initializing TranslateBookWithLLM application...');

    // 1. Core infrastructure
    initializeState();
    WebSocketManager.connect();
    SettingsManager.initialize();

    // 2. UI modules
    FormManager.initialize();

    // 3. Provider modules
    ProviderManager.initialize();
    ModelDetector.initialize();

    // 4. File management
    FileUpload.initialize();
    FileManager.initialize();

    // 5. Translation modules
    TranslationTracker.initialize();
    ProgressManager.reset();
    ResumeManager.initialize();

    // 6. Lifecycle management
    LifecycleManager.initialize();

    // 7. Wire up events
    wireModuleEvents();

    console.log('✅ Application initialized successfully');

    // Expose StateManager for debugging
    if (typeof window !== 'undefined') {
        window.__STATE_MANAGER__ = StateManager;
    }
}

// ========================================
// Global Function Exposure for HTML onclick
// ========================================

/**
 * Expose functions to window for onclick handlers in HTML
 * These functions will be called directly from HTML attributes
 */

// File Upload
window.handleFileSelect = FileUpload.handleFileSelect.bind(FileUpload);
window.resetFiles = () => {
    FileUpload.clearAll();
    DomHelpers.hide('fileInfo');
    const fileListContainer = DomHelpers.getElement('fileListContainer');
    if (fileListContainer) {
        fileListContainer.innerHTML = '';
    }
    MessageLogger.showMessage('File list cleared', 'info');
};

// Form Manager
window.toggleAdvanced = FormManager.toggleAdvanced.bind(FormManager);
window.checkCustomSourceLanguage = (element) => FormManager.checkCustomSourceLanguage(element);
window.checkCustomTargetLanguage = (element) => FormManager.checkCustomTargetLanguage(element);
window.resetForm = FormManager.resetForm.bind(FormManager);

// Batch Controller
window.startBatchTranslation = BatchController.startBatchTranslation.bind(BatchController);
window.interruptCurrentTranslation = async () => {
    const currentJob = StateManager.getState('translation.currentJob');
    if (!currentJob) {
        MessageLogger.showMessage('No active translation to interrupt', 'info');
        return;
    }

    const interruptBtn = DomHelpers.getElement('interruptBtn');
    if (interruptBtn) {
        interruptBtn.disabled = true;
        DomHelpers.setText(interruptBtn, '⏳ Interrupting...');
    }

    try {
        await ApiClient.interruptTranslation(currentJob.translationId);
        MessageLogger.showMessage('Translation interrupt request sent', 'info');
        MessageLogger.addLog('⏹️ Interrupt request sent to server');
    } catch (error) {
        MessageLogger.showMessage(`Error interrupting translation: ${error.message}`, 'error');
        if (interruptBtn) {
            interruptBtn.disabled = false;
            DomHelpers.setText(interruptBtn, '⏹️ Interrupt Current & Stop Batch');
        }
    }
};

// Resume Manager
window.resumeJob = ResumeManager.resumeJob.bind(ResumeManager);
window.deleteCheckpoint = ResumeManager.deleteCheckpoint.bind(ResumeManager);
window.loadResumableJobs = ResumeManager.loadResumableJobs.bind(ResumeManager);

// Provider Manager
window.refreshModels = ProviderManager.refreshModels.bind(ProviderManager);

// Settings Manager
window.saveSettings = async () => {
    const saveBtn = DomHelpers.getElement('saveSettingsBtn');
    const statusSpan = DomHelpers.getElement('saveSettingsStatus');

    if (saveBtn) {
        saveBtn.disabled = true;
        DomHelpers.setText(saveBtn, '💾 Saving...');
    }

    try {
        const result = await SettingsManager.saveAllSettings(true);
        if (result.success) {
            if (statusSpan) {
                statusSpan.textContent = '✅ Settings saved!';
                statusSpan.style.color = '#059669';
                setTimeout(() => { statusSpan.textContent = ''; }, 3000);
            }
            MessageLogger.addLog(`Settings saved: ${result.savedToEnv?.join(', ') || 'local preferences'}`);
        } else {
            throw new Error(result.error || 'Unknown error');
        }
    } catch (error) {
        if (statusSpan) {
            statusSpan.textContent = `❌ ${error.message}`;
            statusSpan.style.color = '#dc2626';
        }
        MessageLogger.addLog(`Failed to save settings: ${error.message}`, 'error');
    } finally {
        if (saveBtn) {
            saveBtn.disabled = false;
            DomHelpers.setText(saveBtn, '💾 Save Settings');
        }
    }
};

// Message Logger
window.clearActivityLog = MessageLogger.clearLog.bind(MessageLogger);

// File Manager
window.refreshFileList = FileManager.refreshFileList.bind(FileManager);
window.downloadSelectedFiles = FileManager.downloadSelectedFiles.bind(FileManager);
window.deleteSelectedFiles = FileManager.deleteSelectedFiles.bind(FileManager);
window.toggleSelectAll = FileManager.toggleSelectAll.bind(FileManager);

// File manager functions (exposed in file-manager.js)
// window.toggleFileSelection, downloadSingleFile, deleteSingleFile, openLocalFile

// ========================================
// TTS (Audiobook) Generation
// ========================================

/**
 * Show TTS configuration modal and start audiobook generation
 * @param {string} filename - File to generate audio from
 * @param {string} filepath - Full path to the file
 */
window.createAudiobook = async function(filename, filepath) {
    // Show TTS modal
    showTTSModal(filename, filepath);
};

/**
 * Show TTS configuration modal
 */
function showTTSModal(filename, filepath) {
    // Remove existing modal if present
    const existingModal = document.getElementById('ttsModal');
    if (existingModal) {
        existingModal.remove();
    }

    // Create modal HTML
    const modalHtml = `
        <div id="ttsModal" class="modal-overlay" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000;">
            <div class="modal-content" style="background: white; border-radius: 12px; padding: 25px; max-width: 500px; width: 90%; max-height: 90vh; overflow-y: auto; box-shadow: 0 10px 40px rgba(0,0,0,0.3);">
                <h2 style="margin: 0 0 20px 0; color: #1f2937;">🎧 Generate Audiobook</h2>
                <p style="margin: 0 0 20px 0; color: #6b7280; font-size: 14px;">
                    Generate audio narration for: <strong>${DomHelpers.escapeHtml(filename)}</strong>
                </p>

                <div style="display: grid; gap: 15px;">
                    <div class="form-group" style="margin-bottom: 0;">
                        <label style="font-size: 13px; font-weight: 500;">Target Language</label>
                        <select id="ttsModalLanguage" class="form-control" style="font-size: 13px;">
                            <option value="Chinese">Chinese</option>
                            <option value="English">English</option>
                            <option value="French">French</option>
                            <option value="Spanish">Spanish</option>
                            <option value="German">German</option>
                            <option value="Italian">Italian</option>
                            <option value="Japanese">Japanese</option>
                            <option value="Korean">Korean</option>
                            <option value="Portuguese">Portuguese</option>
                            <option value="Russian">Russian</option>
                        </select>
                        <small style="color: #6b7280;">Used for automatic voice selection</small>
                    </div>

                    <div class="form-group" style="margin-bottom: 0;">
                        <label style="font-size: 13px; font-weight: 500;">Voice (optional)</label>
                        <input type="text" id="ttsModalVoice" class="form-control" placeholder="e.g., zh-CN-XiaoxiaoNeural" style="font-size: 13px;">
                        <small style="color: #6b7280;">Leave empty for auto-selection based on language</small>
                    </div>

                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                        <div class="form-group" style="margin-bottom: 0;">
                            <label style="font-size: 13px; font-weight: 500;">Speech Rate</label>
                            <select id="ttsModalRate" class="form-control" style="font-size: 13px;">
                                <option value="-20%">Slower (-20%)</option>
                                <option value="-10%">Slightly slower (-10%)</option>
                                <option value="+0%" selected>Normal</option>
                                <option value="+10%">Slightly faster (+10%)</option>
                                <option value="+20%">Faster (+20%)</option>
                                <option value="+30%">Much faster (+30%)</option>
                            </select>
                        </div>

                        <div class="form-group" style="margin-bottom: 0;">
                            <label style="font-size: 13px; font-weight: 500;">Audio Format</label>
                            <select id="ttsModalFormat" class="form-control" style="font-size: 13px;">
                                <option value="opus" selected>Opus (compact)</option>
                                <option value="mp3">MP3 (compatible)</option>
                            </select>
                        </div>
                    </div>

                    <div class="form-group" style="margin-bottom: 0;">
                        <label style="font-size: 13px; font-weight: 500;">Audio Bitrate</label>
                        <select id="ttsModalBitrate" class="form-control" style="font-size: 13px;">
                            <option value="48k">48k (smaller file)</option>
                            <option value="64k" selected>64k (balanced)</option>
                            <option value="96k">96k (higher quality)</option>
                            <option value="128k">128k (best quality)</option>
                        </select>
                    </div>
                </div>

                <div style="display: flex; gap: 10px; margin-top: 25px; justify-content: flex-end;">
                    <button id="ttsModalCancel" class="btn btn-secondary" style="padding: 10px 20px;">
                        Cancel
                    </button>
                    <button id="ttsModalGenerate" class="btn btn-primary" style="padding: 10px 20px; background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);">
                        🎧 Generate Audio
                    </button>
                </div>
            </div>
        </div>
    `;

    // Add modal to DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // Get modal elements
    const modal = document.getElementById('ttsModal');
    const cancelBtn = document.getElementById('ttsModalCancel');
    const generateBtn = document.getElementById('ttsModalGenerate');

    // Close modal on cancel
    cancelBtn.addEventListener('click', () => {
        modal.remove();
    });

    // Close modal on backdrop click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });

    // Close on Escape key
    const handleEscape = (e) => {
        if (e.key === 'Escape') {
            modal.remove();
            document.removeEventListener('keydown', handleEscape);
        }
    };
    document.addEventListener('keydown', handleEscape);

    // Generate audio
    generateBtn.addEventListener('click', async () => {
        const language = document.getElementById('ttsModalLanguage').value;
        const voice = document.getElementById('ttsModalVoice').value;
        const rate = document.getElementById('ttsModalRate').value;
        const format = document.getElementById('ttsModalFormat').value;
        const bitrate = document.getElementById('ttsModalBitrate').value;

        // Disable button and show loading
        generateBtn.disabled = true;
        generateBtn.textContent = '⏳ Starting...';

        try {
            const result = await ApiClient.generateTTS({
                filename: filename,
                target_language: language,
                tts_voice: voice,
                tts_rate: rate,
                tts_format: format,
                tts_bitrate: bitrate
            });

            MessageLogger.showMessage(`TTS generation started for ${filename}`, 'success');
            MessageLogger.addLog(`🎧 Started audiobook generation: ${filename} (Job ID: ${result.job_id})`);

            // Close modal
            modal.remove();

            // Show TTS progress section
            const ttsProgressSection = DomHelpers.getElement('ttsProgressSection');
            if (ttsProgressSection) {
                ttsProgressSection.style.display = 'block';
            }

        } catch (error) {
            MessageLogger.showMessage(`Error starting TTS: ${error.message}`, 'error');
            generateBtn.disabled = false;
            generateBtn.textContent = '🎧 Generate Audio';
        }
    });
}

// ========================================
// API Endpoint Configuration
// ========================================

// Set API base URL (same origin)
if (typeof window !== 'undefined') {
    window.API_BASE_URL = window.location.origin;
}

// ========================================
// Application Bootstrap
// ========================================

/**
 * Start application when DOM is ready
 */
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeModules);
} else {
    // DOM already loaded
    initializeModules();
}

// ========================================
// Module Exports (for testing)
// ========================================

export {
    StateManager,
    ApiClient,
    WebSocketManager,
    SettingsManager,
    DomHelpers,
    MessageLogger,
    FormManager,
    ProviderManager,
    ModelDetector,
    FileUpload,
    FileManager,
    TranslationTracker,
    BatchController,
    ProgressManager,
    ResumeManager,
    Validators,
    LifecycleManager
};
