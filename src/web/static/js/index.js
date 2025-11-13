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
        ProviderManager.refreshModels();
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
