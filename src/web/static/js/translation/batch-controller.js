/**
 * Batch Controller - Batch translation orchestration
 *
 * Manages batch translation queue processing, configuration validation,
 * and sequential file translation.
 */

import { StateManager } from '../core/state-manager.js';
import { ApiClient } from '../core/api-client.js';
import { MessageLogger } from '../ui/message-logger.js';
import { DomHelpers } from '../ui/dom-helpers.js';
import { Validators } from '../utils/validators.js';
import { ProgressManager } from './progress-manager.js';

/**
 * Validation helper for early failures
 * @param {string} message - Error message
 */
function earlyValidationFail(message) {
    MessageLogger.showMessage(message, 'error');
    MessageLogger.addLog(`❌ Validation failed: ${message}`);
    return false;
}

/**
 * Get API key value from field, handling .env configured keys
 * If field is empty but configured in .env, returns special marker for backend
 * @param {string} fieldId - Field ID
 * @returns {string} API key value or '__USE_ENV__' marker
 */
function getApiKeyValue(fieldId) {
    const field = DomHelpers.getElement(fieldId);
    if (!field) return '';

    const value = field.value.trim();

    // If user entered a value, use it
    if (value) {
        return value;
    }

    // If field is empty but .env has a key configured, tell backend to use .env key
    if (field.dataset.envConfigured === 'true') {
        return '__USE_ENV__';
    }

    return '';
}

/**
 * Get translation configuration from form
 * @param {Object} file - File to translate
 * @returns {Object} Translation configuration
 */
function getTranslationConfig(file) {
    let sourceLanguageVal = DomHelpers.getValue('sourceLang');
    if (sourceLanguageVal === 'Other') {
        sourceLanguageVal = DomHelpers.getValue('customSourceLang').trim();
    }

    let targetLanguageVal = DomHelpers.getValue('targetLang');
    if (targetLanguageVal === 'Other') {
        targetLanguageVal = DomHelpers.getValue('customTargetLang').trim();
    }

    const provider = DomHelpers.getValue('llmProvider');

    const config = {
        source_language: sourceLanguageVal,
        target_language: targetLanguageVal,
        model: DomHelpers.getValue('model'),
        llm_api_endpoint: provider === 'openai' ?
                         DomHelpers.getValue('openaiEndpoint') :
                         DomHelpers.getValue('apiEndpoint'),
        llm_provider: provider,
        gemini_api_key: provider === 'gemini' ? getApiKeyValue('geminiApiKey') : '',
        openai_api_key: provider === 'openai' ? getApiKeyValue('openaiApiKey') : '',
        openrouter_api_key: provider === 'openrouter' ? getApiKeyValue('openrouterApiKey') : '',
        chunk_size: parseInt(DomHelpers.getValue('chunkSize')),
        timeout: parseInt(DomHelpers.getValue('timeout')),
        context_window: parseInt(DomHelpers.getValue('contextWindow')),
        max_attempts: parseInt(DomHelpers.getValue('maxAttempts')),
        retry_delay: parseInt(DomHelpers.getValue('retryDelay')),
        output_filename: file.outputFilename,
        file_type: file.fileType,
        fast_mode: DomHelpers.getElement('fastMode')?.checked || false
    };

    // Handle file input based on type
    if (file.fileType === 'epub' || file.fileType === 'srt') {
        config.file_path = file.filePath;
    } else {
        // Text file
        if (file.content) {
            config.text = file.content;
        } else {
            config.file_path = file.filePath;
        }
    }

    return config;
}

/**
 * Update file status in the display
 * @param {string} filename - File name
 * @param {string} status - New status
 * @param {string} translationId - Optional translation ID
 */
function updateFileStatusInList(filename, status, translationId = null) {
    const filesToProcess = StateManager.getState('files.toProcess') || [];
    const fileIndex = filesToProcess.findIndex(f => f.name === filename);

    if (fileIndex !== -1) {
        filesToProcess[fileIndex].status = status;
        if (translationId) {
            filesToProcess[fileIndex].translationId = translationId;
        }
        StateManager.setState('files.toProcess', filesToProcess);
    }

    // Emit event for UI update
    const event = new CustomEvent('fileStatusChanged', { detail: { filename, status, translationId } });
    window.dispatchEvent(event);
}

export const BatchController = {
    /**
     * Start batch translation
     */
    async startBatchTranslation() {
        const isBatchActive = StateManager.getState('translation.isBatchActive') || false;
        const filesToProcess = StateManager.getState('files.toProcess') || [];

        if (isBatchActive || filesToProcess.length === 0) return;

        // Validate configuration
        let sourceLanguageVal = DomHelpers.getValue('sourceLang');
        if (sourceLanguageVal === 'Other') {
            sourceLanguageVal = DomHelpers.getValue('customSourceLang').trim();
            if (!sourceLanguageVal) {
                return earlyValidationFail('Please specify the custom source language for the batch.');
            }
        }

        let targetLanguageVal = DomHelpers.getValue('targetLang');
        if (targetLanguageVal === 'Other') {
            targetLanguageVal = DomHelpers.getValue('customTargetLang').trim();
            if (!targetLanguageVal) {
                return earlyValidationFail('Please specify the custom target language for the batch.');
            }
        }

        const selectedModel = DomHelpers.getValue('model');
        if (!selectedModel) {
            return earlyValidationFail('Please select an LLM model for the batch.');
        }

        const provider = DomHelpers.getValue('llmProvider');
        if (provider === 'ollama') {
            const ollamaApiEndpoint = DomHelpers.getValue('apiEndpoint').trim();
            if (!ollamaApiEndpoint) {
                return earlyValidationFail('Ollama API Endpoint cannot be empty for the batch.');
            }
        }

        // Mark batch as active
        StateManager.setState('translation.isBatchActive', true);

        // Count queued files
        const queuedFilesCount = filesToProcess.filter(f => f.status === 'Queued').length;

        // Update UI
        const translateBtn = DomHelpers.getElement('translateBtn');
        if (translateBtn) {
            translateBtn.disabled = true;
            translateBtn.innerHTML = '⏳ Batch in Progress...';
        }

        const interruptBtn = DomHelpers.getElement('interruptBtn');
        if (interruptBtn) {
            DomHelpers.show('interruptBtn');
            interruptBtn.disabled = false;
        }

        MessageLogger.addLog(`🚀 Batch translation started for ${queuedFilesCount} file(s).`);
        MessageLogger.showMessage(`Batch of ${queuedFilesCount} file(s) initiated.`, 'info');

        // Start processing queue
        this.processNextFileInQueue();
    },

    /**
     * Process next file in queue
     */
    async processNextFileInQueue() {
        const currentJob = StateManager.getState('translation.currentJob');
        if (currentJob) return; // Already processing

        const filesToProcess = StateManager.getState('files.toProcess') || [];
        const fileToTranslate = filesToProcess.find(f => f.status === 'Queued');

        if (!fileToTranslate) {
            // Batch completed
            StateManager.setState('translation.isBatchActive', false);
            StateManager.setState('translation.currentJob', null);

            const translateBtn = DomHelpers.getElement('translateBtn');
            if (translateBtn) {
                translateBtn.disabled = filesToProcess.length === 0;
                translateBtn.innerHTML = '▶️ Start Translation Batch';
            }

            DomHelpers.hide('interruptBtn');

            MessageLogger.showMessage('✅ Batch translation completed for all files!', 'success');
            MessageLogger.addLog('🏁 All files in the batch have been processed.');
            DomHelpers.setText('currentFileProgressTitle', `📊 Batch Completed`);
            return;
        }

        // Reset progress for new file
        ProgressManager.reset();

        // Reset translation preview
        const lastTranslationPreview = DomHelpers.getElement('lastTranslationPreview');
        if (lastTranslationPreview) {
            lastTranslationPreview.innerHTML = '<div style="color: #6b7280; font-style: italic; padding: 10px;">No translation yet...</div>';
        }

        // Show/hide stats based on file type
        if (fileToTranslate.fileType === 'epub') {
            DomHelpers.hide('statsGrid');
        } else {
            DomHelpers.show('statsGrid');
        }

        // Update UI
        DomHelpers.setText('currentFileProgressTitle', `📊 Translating: ${fileToTranslate.name}`);
        ProgressManager.show();
        MessageLogger.addLog(`▶️ Starting translation for: ${fileToTranslate.name} (${fileToTranslate.fileType.toUpperCase()})`);
        updateFileStatusInList(fileToTranslate.name, 'Preparing...');

        // Validate API keys for cloud providers
        // Key is valid if: user entered a value OR key is configured in .env
        const provider = DomHelpers.getValue('llmProvider');

        if (provider === 'gemini') {
            const apiKeyValue = getApiKeyValue('geminiApiKey');
            if (!apiKeyValue) {
                MessageLogger.addLog('❌ Error: Gemini API key is required when using Gemini provider');
                MessageLogger.showMessage('Please enter your Gemini API key', 'error');
                updateFileStatusInList(fileToTranslate.name, 'Error: Missing API key');
                StateManager.setState('translation.currentJob', null);
                this.processNextFileInQueue();
                return;
            }
        }

        if (provider === 'openai') {
            const apiKeyValue = getApiKeyValue('openaiApiKey');
            // Check if it's a local endpoint (LM Studio) - no API key required
            const openaiEndpoint = DomHelpers.getValue('openaiEndpoint') || '';
            const isLocalEndpoint = openaiEndpoint.includes('localhost') || openaiEndpoint.includes('127.0.0.1');

            if (!apiKeyValue && !isLocalEndpoint) {
                MessageLogger.addLog('❌ Error: OpenAI API key is required when using OpenAI provider');
                MessageLogger.showMessage('Please enter your OpenAI API key', 'error');
                updateFileStatusInList(fileToTranslate.name, 'Error: Missing API key');
                StateManager.setState('translation.currentJob', null);
                this.processNextFileInQueue();
                return;
            }
        }

        if (provider === 'openrouter') {
            const apiKeyValue = getApiKeyValue('openrouterApiKey');
            if (!apiKeyValue) {
                MessageLogger.addLog('❌ Error: OpenRouter API key is required when using OpenRouter provider');
                MessageLogger.showMessage('Please enter your OpenRouter API key', 'error');
                updateFileStatusInList(fileToTranslate.name, 'Error: Missing API key');
                StateManager.setState('translation.currentJob', null);
                this.processNextFileInQueue();
                return;
            }
        }

        // Validate file path
        if (!fileToTranslate.filePath && !fileToTranslate.content) {
            MessageLogger.addLog(`❌ Critical Error: File ${fileToTranslate.name} has no server path or content`);
            MessageLogger.showMessage(`Cannot process ${fileToTranslate.name}: file path missing.`, 'error');
            updateFileStatusInList(fileToTranslate.name, 'Path Error');
            StateManager.setState('translation.currentJob', null);
            this.processNextFileInQueue();
            return;
        }

        // Get translation config
        const config = getTranslationConfig(fileToTranslate);

        try {
            // Start translation
            const data = await ApiClient.startTranslation(config);

            // Update state
            StateManager.setState('translation.currentJob', {
                fileRef: fileToTranslate,
                translationId: data.translation_id
            });

            fileToTranslate.translationId = data.translation_id;
            updateFileStatusInList(fileToTranslate.name, 'Submitted', data.translation_id);

            // Emit event
            const event = new CustomEvent('translationStarted', { detail: { file: fileToTranslate, translationId: data.translation_id } });
            window.dispatchEvent(event);

        } catch (error) {
            MessageLogger.addLog(`❌ Error initiating translation for ${fileToTranslate.name}: ${error.message}`);
            MessageLogger.showMessage(`Error starting ${fileToTranslate.name}: ${error.message}`, 'error');
            updateFileStatusInList(fileToTranslate.name, 'Initiation Error');
            StateManager.setState('translation.currentJob', null);
            this.processNextFileInQueue();
        }
    },

    /**
     * Stop batch translation
     */
    stopBatch() {
        StateManager.setState('translation.isBatchActive', false);
        StateManager.setState('translation.currentJob', null);

        const translateBtn = DomHelpers.getElement('translateBtn');
        if (translateBtn) {
            translateBtn.disabled = false;
            translateBtn.innerHTML = '▶️ Start Translation Batch';
        }

        DomHelpers.hide('interruptBtn');

        MessageLogger.addLog('⏹️ Batch translation stopped');
        MessageLogger.showMessage('Batch translation stopped', 'info');
    }
};
