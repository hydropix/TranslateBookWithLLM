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
import { StatusManager } from './utils/status-manager.js';
import { initializeThemeManager } from './utils/theme-manager.js';

// ========================================
// TTS Modules
// ========================================
import { TTSManager } from './tts/tts-manager.js';

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

            const errorText = error || message || 'Unknown error';
            const isFFmpegError = errorText.toLowerCase().includes('ffmpeg');

            if (ttsStatusText) {
                if (isFFmpegError) {
                    // Show FFmpeg install button instead of long instructions
                    ttsStatusText.innerHTML = `
                        <span style="color: #ef4444;">❌ FFmpeg is required for audio encoding</span>
                        <div style="margin-top: 10px;">
                            <button id="installFFmpegBtn" class="btn btn-primary" style="margin-right: 10px;" onclick="window.installFFmpeg()">
                                <span class="material-symbols-outlined" style="font-size: 18px; vertical-align: middle;">download</span>
                                Install FFmpeg (winget)
                            </button>
                            <a href="https://ffmpeg.org/download.html" target="_blank" class="btn btn-secondary" style="text-decoration: none;">
                                Manual Download
                            </a>
                        </div>
                        <p style="margin-top: 8px; font-size: 0.8rem; color: var(--text-secondary);">
                            After installation, restart the application.
                        </p>
                    `;
                } else {
                    ttsStatusText.textContent = `❌ TTS failed: ${errorText}`;
                }
            }
            MessageLogger.addLog(`❌ TTS failed: ${errorText}`);
            break;
    }
}

/**
 * Install FFmpeg via winget (Windows)
 */
window.installFFmpeg = async function() {
    const btn = document.getElementById('installFFmpegBtn');
    const ttsStatusText = DomHelpers.getElement('ttsStatusText');

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `
            <span class="material-symbols-outlined rotating" style="font-size: 18px; vertical-align: middle;">sync</span>
            Installing...
        `;
    }

    try {
        const response = await fetch('/api/tts/ffmpeg/install', { method: 'POST' });
        const result = await response.json();

        if (result.success) {
            if (ttsStatusText) {
                ttsStatusText.innerHTML = `
                    <span style="color: #22c55e;">✅ ${result.message}</span>
                    <p style="margin-top: 8px; font-size: 0.8rem; color: var(--text-secondary);">
                        Please restart the application to use TTS.
                    </p>
                `;
            }
            MessageLogger.addLog('✅ FFmpeg installed successfully');
        } else {
            if (ttsStatusText) {
                ttsStatusText.innerHTML = `
                    <span style="color: #ef4444;">❌ Installation failed: ${result.error}</span>
                    <div style="margin-top: 10px;">
                        <a href="https://ffmpeg.org/download.html" target="_blank" class="btn btn-secondary" style="text-decoration: none;">
                            Manual Download
                        </a>
                    </div>
                `;
            }
            MessageLogger.addLog(`❌ FFmpeg installation failed: ${result.error}`);
        }
    } catch (err) {
        if (ttsStatusText) {
            ttsStatusText.innerHTML = `
                <span style="color: #ef4444;">❌ Installation error: ${err.message}</span>
                <div style="margin-top: 10px;">
                    <a href="https://ffmpeg.org/download.html" target="_blank" class="btn btn-secondary" style="text-decoration: none;">
                        Manual Download
                    </a>
                </div>
            `;
        }
        MessageLogger.addLog(`❌ FFmpeg installation error: ${err.message}`);
    }
}

// ========================================
// Global State Initialization
// ========================================

/**
 * Initialize application state
 * Note: Some state (like files.toProcess) will be restored from localStorage
 * by their respective modules, so we only set defaults if not already present
 */
function initializeState() {
    // Files state - only initialize if not already set (will be restored by FileUpload)
    if (!StateManager.getState('files.toProcess')) {
        StateManager.setState('files.toProcess', []);
    }
    if (!StateManager.getState('files.selected')) {
        StateManager.setState('files.selected', []);
    }
    if (!StateManager.getState('files.managed')) {
        StateManager.setState('files.managed', []);
    }

    // Translation state - DO NOT reset here, will be restored by TranslationTracker from localStorage
    // TranslationTracker.initialize() will handle loading saved state or initializing defaults

    // UI state
    StateManager.setState('ui.currentProvider', 'ollama');
    StateManager.setState('ui.currentModel', '');
    StateManager.setState('ui.messages', []);

    // Models state
    StateManager.setState('models.currentLoadRequest', null);
    StateManager.setState('models.availableModels', []);
}

/**
 * Calculate and apply preview height based on MAX_TOKENS_PER_CHUNK
 * Formula: Fixed 300px height regardless of token count
 * @param {number} maxTokens - MAX_TOKENS_PER_CHUNK value (not used, kept for API compatibility)
 */
function updatePreviewHeight(maxTokens = 450) {
    // Fixed height of 300px
    const fixedHeight = 300;

    // Apply to CSS variable
    document.documentElement.style.setProperty('--preview-height', `${fixedHeight}px`);
}

/**
 * Fetch and apply MAX_TOKENS_PER_CHUNK from server
 */
async function initializePreviewHeight() {
    try {
        // Fetch config from server
        const response = await fetch('/api/config/max-tokens');
        if (response.ok) {
            const data = await response.json();
            const maxTokens = data.max_tokens_per_chunk || 450;
            updatePreviewHeight(maxTokens);
        } else {
            updatePreviewHeight(450);
        }
    } catch {
        updatePreviewHeight(450);
    }
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
            // Only enable if files exist AND LLM is connected
            translateBtn.disabled = files.length === 0 || !StatusManager.isConnected();
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

    // 1. Core infrastructure
    initializeState();
    WebSocketManager.connect();
    SettingsManager.initialize();

    // 2. UI modules
    initializeThemeManager();
    FormManager.initialize();
    StatusManager.initialize();
    initializePreviewHeight(); // Load and apply preview height

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

    // 6. TTS Manager
    TTSManager.initialize();

    // 7. Lifecycle management
    LifecycleManager.initialize();

    // 8. Wire up events
    wireModuleEvents();
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
window.toggleSettingsOptions = FormManager.toggleSettingsOptions.bind(FormManager);
window.togglePromptOptions = FormManager.togglePromptOptions.bind(FormManager);
window.toggleActivityLog = FormManager.toggleActivityLog.bind(FormManager);
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

// Message Logger
window.clearActivityLog = MessageLogger.clearLog.bind(MessageLogger);

// File Manager
window.refreshFileList = FileManager.refreshFileList.bind(FileManager);
window.downloadSelectedFiles = FileManager.downloadSelectedFiles.bind(FileManager);
window.deleteSelectedFiles = FileManager.deleteSelectedFiles.bind(FileManager);
window.toggleSelectAll = FileManager.toggleSelectAll.bind(FileManager);

// File manager functions (exposed in file-manager.js)
// window.toggleFileSelection, downloadSingleFile, deleteSingleFile, openLocalFile

// TTS Manager functions
window.refreshTTSProviders = TTSManager.loadProvidersInfo.bind(TTSManager);
window.refreshGPUStatus = TTSManager.loadGPUStatus.bind(TTSManager);
window.deleteVoicePrompt = TTSManager.deleteVoicePrompt.bind(TTSManager);

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
 * Show TTS configuration modal with provider selection
 */
async function showTTSModal(filename, filepath) {
    // Remove existing modal if present
    const existingModal = document.getElementById('ttsModal');
    if (existingModal) {
        existingModal.remove();
    }

    // Get providers info and voice prompts
    let providersInfo = {};
    let voicePrompts = [];
    let gpuStatus = { cuda_available: false };

    try {
        [providersInfo, voicePrompts, gpuStatus] = await Promise.all([
            ApiClient.getTTSProviders().catch(() => ({ providers: {} })),
            ApiClient.getTTSVoicePrompts().catch(() => ({ voice_prompts: [] })),
            ApiClient.getTTSGPUStatus().catch(() => ({ cuda_available: false }))
        ]);
        providersInfo = providersInfo.providers || {};
        voicePrompts = voicePrompts.voice_prompts || [];
    } catch {
        // TTS info load failed
    }

    const isChatterboxAvailable = providersInfo.chatterbox?.available || false;

    // Build voice prompts options
    const voicePromptsOptions = voicePrompts.map(vp =>
        `<option value="${DomHelpers.escapeHtml(vp.path)}">${DomHelpers.escapeHtml(vp.filename)}</option>`
    ).join('');

    // Create modal HTML with provider selection
    const modalHtml = `
        <div id="ttsModal" class="modal-overlay">
            <div class="modal-content">
                <div class="modal-header">
                    <h3>🎧 Generate Audiobook</h3>
                    <button class="close-btn" id="ttsModalClose">&times;</button>
                </div>
                <div class="modal-body">
                    <p style="margin: 0 0 20px 0; color: #a3adb3; font-size: 14px;">
                        Generate audio narration for: <strong style="color: #79CDDE;">${DomHelpers.escapeHtml(filename)}</strong>
                    </p>

                    <!-- Provider Selection -->
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px;">
                        <div class="form-group" style="margin-bottom: 0;">
                            <label style="font-size: 13px;">TTS Provider</label>
                            <select id="ttsModalProvider" class="form-control" style="font-size: 13px;">
                                <option value="edge-tts">Edge TTS (Cloud)</option>
                                <option value="chatterbox" ${!isChatterboxAvailable ? 'disabled' : ''}>
                                    Chatterbox TTS ${!isChatterboxAvailable ? '(Not Available)' : '(Local GPU)'}
                                </option>
                            </select>
                        </div>

                        <!-- GPU Status (shown when Chatterbox selected) -->
                        <div id="ttsModalGpuStatus" class="form-group" style="margin-bottom: 0; display: none;">
                            <label style="font-size: 13px;">GPU Status</label>
                            <div class="gpu-status ${gpuStatus.cuda_available ? 'gpu-available' : 'gpu-unavailable'}">
                                <span class="status-dot ${gpuStatus.cuda_available ? 'available' : 'unavailable'}"></span>
                                <span>${gpuStatus.cuda_available ? (gpuStatus.gpu_name || 'CUDA GPU') : 'CPU Mode'}</span>
                            </div>
                        </div>
                    </div>

                    <!-- Edge-TTS Options -->
                    <div id="ttsModalEdgeOptions">
                        <div style="display: grid; gap: 15px;">
                            <div class="form-group" style="margin-bottom: 0;">
                                <label style="font-size: 13px;">Target Language</label>
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
                            </div>

                            <div class="form-group" style="margin-bottom: 0;">
                                <label style="font-size: 13px;">Voice (optional)</label>
                                <input type="text" id="ttsModalVoice" class="form-control" placeholder="e.g., zh-CN-XiaoxiaoNeural" style="font-size: 13px;">
                                <small style="color: #6b7280;">Leave empty for auto-selection based on language</small>
                            </div>

                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                                <div class="form-group" style="margin-bottom: 0;">
                                    <label style="font-size: 13px;">Speech Rate</label>
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
                                    <label style="font-size: 13px;">Audio Format</label>
                                    <select id="ttsModalFormat" class="form-control" style="font-size: 13px;">
                                        <option value="opus" selected>Opus (compact)</option>
                                        <option value="mp3">MP3 (compatible)</option>
                                    </select>
                                </div>
                            </div>

                            <div class="form-group" style="margin-bottom: 0;">
                                <label style="font-size: 13px;">Audio Bitrate</label>
                                <select id="ttsModalBitrate" class="form-control" style="font-size: 13px;">
                                    <option value="48k">48k (smaller file)</option>
                                    <option value="64k" selected>64k (balanced)</option>
                                    <option value="96k">96k (higher quality)</option>
                                    <option value="128k">128k (best quality)</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    <!-- Chatterbox Options (hidden by default) -->
                    <div id="ttsModalChatterboxOptions" style="display: none;">
                        <div style="background: #2a2a2a; border-radius: 8px; padding: 15px; margin-bottom: 15px; border: 1px solid #fbbf24;">
                            <h4 style="margin: 0 0 12px 0; font-size: 14px; color: #fbbf24;">🎤 Voice Cloning</h4>
                            <div class="form-group" style="margin-bottom: 0;">
                                <label style="font-size: 13px;">Voice Prompt</label>
                                <select id="ttsModalVoicePrompt" class="form-control" style="font-size: 13px;">
                                    <option value="">Default voice (no cloning)</option>
                                    ${voicePromptsOptions}
                                </select>
                                <small style="color: #6b7280;">Select a previously uploaded voice sample</small>
                            </div>
                        </div>

                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                            <div class="form-group" style="margin-bottom: 0;">
                                <label style="font-size: 13px;">
                                    Exaggeration <span id="ttsModalExaggerationValue" style="color: #fbbf24;">0.50</span>
                                </label>
                                <input type="range" id="ttsModalExaggeration" min="0" max="1" step="0.05" value="0.5" class="tts-slider">
                                <small style="color: #6b7280;">Higher = more expressive</small>
                            </div>
                            <div class="form-group" style="margin-bottom: 0;">
                                <label style="font-size: 13px;">
                                    CFG Weight <span id="ttsModalCfgValue" style="color: #fbbf24;">0.50</span>
                                </label>
                                <input type="range" id="ttsModalCfgWeight" min="0" max="1" step="0.05" value="0.5" class="tts-slider">
                                <small style="color: #6b7280;">Prompt adherence</small>
                            </div>
                        </div>

                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                            <div class="form-group" style="margin-bottom: 0;">
                                <label style="font-size: 13px;">Target Language</label>
                                <select id="ttsModalChatterboxLang" class="form-control" style="font-size: 13px;">
                                    <option value="en">English</option>
                                    <option value="zh">Chinese</option>
                                    <option value="es">Spanish</option>
                                    <option value="fr">French</option>
                                    <option value="de">German</option>
                                    <option value="it">Italian</option>
                                    <option value="ja">Japanese</option>
                                    <option value="ko">Korean</option>
                                    <option value="pt">Portuguese</option>
                                    <option value="ru">Russian</option>
                                </select>
                            </div>
                            <div class="form-group" style="margin-bottom: 0;">
                                <label style="font-size: 13px;">Audio Format</label>
                                <select id="ttsModalChatterboxFormat" class="form-control" style="font-size: 13px;">
                                    <option value="wav">WAV (lossless)</option>
                                    <option value="mp3" selected>MP3 (compatible)</option>
                                    <option value="opus">Opus (compact)</option>
                                </select>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="modal-footer">
                    <button id="ttsModalCancel" class="btn btn-secondary">Cancel</button>
                    <button id="ttsModalGenerate" class="btn btn-primary" style="background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);">
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
    const closeBtn = document.getElementById('ttsModalClose');
    const cancelBtn = document.getElementById('ttsModalCancel');
    const generateBtn = document.getElementById('ttsModalGenerate');
    const providerSelect = document.getElementById('ttsModalProvider');
    const edgeOptions = document.getElementById('ttsModalEdgeOptions');
    const chatterboxOptions = document.getElementById('ttsModalChatterboxOptions');
    const gpuStatusDiv = document.getElementById('ttsModalGpuStatus');

    // Slider value updates
    const exaggerationSlider = document.getElementById('ttsModalExaggeration');
    const cfgSlider = document.getElementById('ttsModalCfgWeight');
    const exaggerationValue = document.getElementById('ttsModalExaggerationValue');
    const cfgValue = document.getElementById('ttsModalCfgValue');

    if (exaggerationSlider && exaggerationValue) {
        exaggerationSlider.addEventListener('input', () => {
            exaggerationValue.textContent = parseFloat(exaggerationSlider.value).toFixed(2);
        });
    }
    if (cfgSlider && cfgValue) {
        cfgSlider.addEventListener('input', () => {
            cfgValue.textContent = parseFloat(cfgSlider.value).toFixed(2);
        });
    }

    // Provider change handler
    providerSelect.addEventListener('change', () => {
        const isChatterbox = providerSelect.value === 'chatterbox';
        edgeOptions.style.display = isChatterbox ? 'none' : 'block';
        chatterboxOptions.style.display = isChatterbox ? 'block' : 'none';
        gpuStatusDiv.style.display = isChatterbox ? 'block' : 'none';
    });

    // Close handlers
    const closeModal = () => modal.remove();
    closeBtn.addEventListener('click', closeModal);
    cancelBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });
    const handleEscape = (e) => {
        if (e.key === 'Escape') {
            closeModal();
            document.removeEventListener('keydown', handleEscape);
        }
    };
    document.addEventListener('keydown', handleEscape);

    // Generate audio
    generateBtn.addEventListener('click', async () => {
        const provider = providerSelect.value;

        // Build config based on provider
        let config = {
            filename: filename,
            tts_provider: provider
        };

        if (provider === 'edge-tts') {
            config.target_language = document.getElementById('ttsModalLanguage').value;
            config.tts_voice = document.getElementById('ttsModalVoice').value;
            config.tts_rate = document.getElementById('ttsModalRate').value;
            config.tts_format = document.getElementById('ttsModalFormat').value;
            config.tts_bitrate = document.getElementById('ttsModalBitrate').value;
        } else {
            // Chatterbox
            config.target_language = document.getElementById('ttsModalChatterboxLang').value;
            config.tts_voice_prompt_path = document.getElementById('ttsModalVoicePrompt').value;
            config.tts_exaggeration = parseFloat(document.getElementById('ttsModalExaggeration').value);
            config.tts_cfg_weight = parseFloat(document.getElementById('ttsModalCfgWeight').value);
            config.tts_format = document.getElementById('ttsModalChatterboxFormat').value;
        }

        // Disable button and show loading
        generateBtn.disabled = true;
        generateBtn.textContent = '⏳ Starting...';

        try {
            const result = await ApiClient.generateTTS(config);

            MessageLogger.showMessage(`TTS generation started for ${filename}`, 'success');
            MessageLogger.addLog(`🎧 Started audiobook generation (${provider}): ${filename} (Job ID: ${result.job_id})`);

            // Close modal
            closeModal();

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
    LifecycleManager,
    TTSManager,
    StatusManager
};
