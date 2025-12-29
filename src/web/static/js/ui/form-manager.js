/**
 * Form Manager - Form configuration and settings management
 *
 * Handles form state, custom language toggles, advanced settings,
 * default configuration loading, and form reset functionality.
 */

import { StateManager } from '../core/state-manager.js';
import { ApiClient } from '../core/api-client.js';
import { DomHelpers } from './dom-helpers.js';
import { MessageLogger } from './message-logger.js';
import { ApiKeyUtils } from '../utils/api-key-utils.js';

/**
 * Set default language in select/input
 * @param {string} selectId - Select element ID
 * @param {string} customInputId - Custom input element ID
 * @param {string} defaultLanguage - Default language value
 */
function setDefaultLanguage(selectId, customInputId, defaultLanguage) {
    const select = DomHelpers.getElement(selectId);
    const customInput = DomHelpers.getElement(customInputId);

    if (!select || !customInput) return;

    // Check if the default language is in the dropdown options (excluding "Other")
    let languageFound = false;
    for (let option of select.options) {
        // Skip "Other" option - we only want to match actual language values
        if (option.value === 'Other') continue;

        if (option.value.toLowerCase() === defaultLanguage.toLowerCase()) {
            select.value = option.value;
            languageFound = true;
            DomHelpers.hide(customInput);
            break;
        }
    }

    // If language not found in dropdown, use "Other" and set custom input
    if (!languageFound) {
        select.value = 'Other';
        customInput.value = defaultLanguage;
        // Show the custom input - need both class removal AND style change
        // because HTML has inline style="display: none"
        customInput.classList.remove('hidden');
        customInput.style.display = 'block';
    }
}

export const FormManager = {
    /**
     * Initialize form manager
     */
    initialize() {
        this.setupEventListeners();
        this.loadDefaultConfig();
    },

    /**
     * Set up event listeners for form elements
     */
    setupEventListeners() {
        // Source language change
        const sourceLang = DomHelpers.getElement('sourceLang');
        if (sourceLang) {
            sourceLang.addEventListener('change', (e) => {
                this.checkCustomSourceLanguage(e.target);
            });
        }

        // Target language change
        const targetLang = DomHelpers.getElement('targetLang');
        if (targetLang) {
            targetLang.addEventListener('change', (e) => {
                this.checkCustomTargetLanguage(e.target);
            });
        }

        // Advanced settings toggle
        const advancedIcon = DomHelpers.getElement('advancedIcon');
        if (advancedIcon) {
            advancedIcon.addEventListener('click', () => {
                this.toggleAdvanced();
            });
        }

        // Fast mode checkbox
        const fastMode = DomHelpers.getElement('fastMode');
        if (fastMode) {
            fastMode.addEventListener('change', (e) => {
                this.handleFastModeToggle(e.target.checked);
            });
        }

        // TTS enabled checkbox
        const ttsEnabled = DomHelpers.getElement('ttsEnabled');
        if (ttsEnabled) {
            ttsEnabled.addEventListener('change', (e) => {
                this.handleTtsToggle(e.target.checked);
            });
        }

        // Reset button
        const resetBtn = DomHelpers.getElement('resetBtn');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                this.resetForm();
            });
        }
    },

    /**
     * Check if custom source language input should be shown
     * @param {HTMLSelectElement} selectElement - Source language select element
     */
    checkCustomSourceLanguage(selectElement) {
        const customLangInput = DomHelpers.getElement('customSourceLang');
        if (!customLangInput) return;

        if (selectElement.value === 'Other') {
            customLangInput.classList.remove('hidden');
            customLangInput.style.display = 'block';
            customLangInput.focus();
        } else {
            customLangInput.classList.add('hidden');
            customLangInput.style.display = 'none';
        }
    },

    /**
     * Check if custom target language input should be shown
     * @param {HTMLSelectElement} selectElement - Target language select element
     */
    checkCustomTargetLanguage(selectElement) {
        const customLangInput = DomHelpers.getElement('customTargetLang');
        if (!customLangInput) return;

        if (selectElement.value === 'Other') {
            customLangInput.classList.remove('hidden');
            customLangInput.style.display = 'block';
            customLangInput.focus();
        } else {
            customLangInput.classList.add('hidden');
            customLangInput.style.display = 'none';
        }
    },


    /**
     * Toggle advanced settings panel
     */
    toggleAdvanced() {
        const settings = DomHelpers.getElement('advancedSettings');
        const icon = DomHelpers.getElement('advancedIcon');

        if (!settings || !icon) return;

        const isHidden = settings.classList.toggle('hidden');
        DomHelpers.setText(icon, isHidden ? '▼' : '▲');

        // Update state
        StateManager.setState('ui.isAdvancedOpen', !isHidden);
    },

    /**
     * Toggle prompt options panel
     */
    togglePromptOptions() {
        const section = DomHelpers.getElement('promptOptionsSection');
        const icon = DomHelpers.getElement('promptOptionsIcon');

        if (!section || !icon) return;

        const isHidden = section.classList.toggle('hidden');
        icon.style.transform = isHidden ? 'rotate(0deg)' : 'rotate(180deg)';

        // Update state
        StateManager.setState('ui.isPromptOptionsOpen', !isHidden);
    },

    /**
     * Handle fast mode toggle
     * @param {boolean} isChecked - Whether fast mode is checked
     */
    handleFastModeToggle(isChecked) {
        const fastModeInfo = DomHelpers.getElement('fastModeInfo');

        // Use inline style to override display:none
        if (fastModeInfo) {
            if (isChecked) {
                fastModeInfo.style.display = 'block';
            } else {
                fastModeInfo.style.display = 'none';
            }
        }

        // Re-check model size when fast mode changes
        // This will be handled by model-detector.js when it's created
        window.dispatchEvent(new CustomEvent('fastModeChanged', { detail: { enabled: isChecked } }));
    },

    /**
     * Handle TTS toggle
     * @param {boolean} isChecked - Whether TTS is enabled
     */
    handleTtsToggle(isChecked) {
        const ttsOptions = DomHelpers.getElement('ttsOptions');

        if (ttsOptions) {
            if (isChecked) {
                ttsOptions.style.display = 'block';
            } else {
                ttsOptions.style.display = 'none';
            }
        }

        // Dispatch event for other components
        window.dispatchEvent(new CustomEvent('ttsChanged', { detail: { enabled: isChecked } }));
    },

    /**
     * Load default configuration from server
     */
    async loadDefaultConfig() {
        try {
            const config = await ApiClient.getConfig();

            // Set default languages
            if (config.default_source_language) {
                setDefaultLanguage('sourceLang', 'customSourceLang', config.default_source_language);
            }
            if (config.default_target_language) {
                setDefaultLanguage('targetLang', 'customTargetLang', config.default_target_language);
            }

            // Set other configuration values
            if (config.api_endpoint) {
                DomHelpers.setValue('apiEndpoint', config.api_endpoint);
            }
            if (config.chunk_size) {
                DomHelpers.setValue('chunkSize', config.chunk_size);
            }
            if (config.timeout) {
                DomHelpers.setValue('timeout', config.timeout);
            }
            if (config.context_window) {
                DomHelpers.setValue('contextWindow', config.context_window);
            }
            if (config.max_attempts) {
                DomHelpers.setValue('maxAttempts', config.max_attempts);
            }
            if (config.retry_delay) {
                DomHelpers.setValue('retryDelay', config.retry_delay);
            }
            // Handle API keys - show indicator if configured in .env, otherwise keep placeholder
            ApiKeyUtils.setupField('geminiApiKey', config.gemini_api_key_configured, config.gemini_api_key);
            ApiKeyUtils.setupField('openaiApiKey', config.openai_api_key_configured, config.openai_api_key);
            ApiKeyUtils.setupField('openrouterApiKey', config.openrouter_api_key_configured, config.openrouter_api_key);

            // Store in state
            StateManager.setState('ui.defaultConfig', config);

        } catch (error) {
            console.error('Error loading default configuration:', error);
            MessageLogger.showMessage('Failed to load default configuration', 'warning');
        }
    },

    /**
     * Reset form to default state
     */
    async resetForm() {
        // Get current files to process
        const filesToProcess = StateManager.getState('files.toProcess');
        const currentJob = StateManager.getState('translation.currentJob');
        const isBatchActive = StateManager.getState('translation.isBatchActive');

        // First, interrupt current translation if active
        if (currentJob && currentJob.translationId && isBatchActive) {
            MessageLogger.addLog("🛑 Interrupting current translation before clearing files...");
            try {
                await ApiClient.interruptTranslation(currentJob.translationId);
            } catch (error) {
                console.error('Error interrupting translation:', error);
            }
        }

        // Collect file paths to delete from server
        const uploadedFilePaths = filesToProcess
            .filter(file => file.filePath)
            .map(file => file.filePath);

        // Clear client-side state
        StateManager.setState('files.toProcess', []);
        StateManager.setState('translation.currentJob', null);
        StateManager.setState('translation.isBatchActive', false);

        // Reset file input
        DomHelpers.setValue('fileInput', '');

        // Hide progress section
        DomHelpers.hide('progressSection');

        // Reset buttons
        DomHelpers.setText('translateBtn', '▶️ Start Translation Batch');
        DomHelpers.setDisabled('translateBtn', true);
        DomHelpers.hide('interruptBtn');
        DomHelpers.setDisabled('interruptBtn', false);

        // Reset language selectors
        DomHelpers.hide('customSourceLang');
        DomHelpers.hide('customTargetLang');
        DomHelpers.getElement('sourceLang').selectedIndex = 0;
        DomHelpers.getElement('targetLang').selectedIndex = 0;

        // Reset stats and progress
        DomHelpers.show('statsGrid');
        this.updateProgress(0);
        MessageLogger.showMessage('', '');

        // Delete uploaded files from server
        if (uploadedFilePaths.length > 0) {
            MessageLogger.addLog(`🗑️ Deleting ${uploadedFilePaths.length} uploaded file(s) from server...`);
            try {
                const result = await ApiClient.clearUploads(uploadedFilePaths);

                MessageLogger.addLog(`✅ Successfully deleted ${result.total_deleted} uploaded file(s).`);
                if (result.failed && result.failed.length > 0) {
                    MessageLogger.addLog(`⚠️ Failed to delete ${result.failed.length} file(s).`);
                }
            } catch (error) {
                console.error('Error deleting uploaded files:', error);
                MessageLogger.addLog("⚠️ Error occurred while deleting uploaded files.");
            }
        }

        MessageLogger.addLog("Form and file list reset.");

        // Trigger UI update
        window.dispatchEvent(new CustomEvent('formReset'));
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
     * Get form configuration for translation
     * @returns {Object} Translation configuration object
     */
    getTranslationConfig() {
        // Get source language
        let sourceLanguageVal = DomHelpers.getValue('sourceLang');
        if (sourceLanguageVal === 'Other') {
            sourceLanguageVal = DomHelpers.getValue('customSourceLang').trim();
        }

        // Get target language
        let targetLanguageVal = DomHelpers.getValue('targetLang');
        if (targetLanguageVal === 'Other') {
            targetLanguageVal = DomHelpers.getValue('customTargetLang').trim();
        }

        // Get provider and model
        const provider = DomHelpers.getValue('llmProvider');
        const model = DomHelpers.getValue('model');

        // Get API endpoint based on provider
        let apiEndpoint;
        if (provider === 'openai') {
            apiEndpoint = DomHelpers.getValue('openaiEndpoint');
        } else {
            apiEndpoint = DomHelpers.getValue('apiEndpoint');
        }

        // Get API keys - use helper to handle .env configured keys
        const geminiApiKey = provider === 'gemini' ? ApiKeyUtils.getValue('geminiApiKey') : '';
        const openaiApiKey = provider === 'openai' ? ApiKeyUtils.getValue('openaiApiKey') : '';
        const openrouterApiKey = provider === 'openrouter' ? ApiKeyUtils.getValue('openrouterApiKey') : '';

        // Get TTS configuration
        const ttsEnabled = DomHelpers.getElement('ttsEnabled')?.checked || false;

        return {
            source_language: sourceLanguageVal,
            target_language: targetLanguageVal,
            model: model,
            llm_api_endpoint: apiEndpoint,
            llm_provider: provider,
            gemini_api_key: geminiApiKey,
            openai_api_key: openaiApiKey,
            openrouter_api_key: openrouterApiKey,
            chunk_size: parseInt(DomHelpers.getValue('chunkSize')),
            timeout: parseInt(DomHelpers.getValue('timeout')),
            context_window: parseInt(DomHelpers.getValue('contextWindow')),
            max_attempts: parseInt(DomHelpers.getValue('maxAttempts')),
            retry_delay: parseInt(DomHelpers.getValue('retryDelay')),
            fast_mode: DomHelpers.getElement('fastMode')?.checked || false,
            // Prompt options (optional system prompt instructions)
            prompt_options: {
                preserve_technical_content: DomHelpers.getElement('preserveTechnicalContent')?.checked || false,
                text_cleanup: DomHelpers.getElement('textCleanup')?.checked || false,
                refine: DomHelpers.getElement('refineTranslation')?.checked || false
            },
            // TTS configuration
            tts_enabled: ttsEnabled,
            tts_voice: ttsEnabled ? (DomHelpers.getValue('ttsVoice') || '') : '',
            tts_rate: ttsEnabled ? (DomHelpers.getValue('ttsRate') || '+0%') : '+0%',
            tts_format: ttsEnabled ? (DomHelpers.getValue('ttsFormat') || 'opus') : 'opus',
            tts_bitrate: ttsEnabled ? (DomHelpers.getValue('ttsBitrate') || '64k') : '64k'
        };
    },

    /**
     * Validate form configuration
     * @returns {Object} { valid: boolean, message: string }
     */
    validateConfig() {
        const config = this.getTranslationConfig();

        if (!config.source_language) {
            return { valid: false, message: 'Please specify the source language.' };
        }

        if (!config.target_language) {
            return { valid: false, message: 'Please specify the target language.' };
        }

        if (!config.model) {
            return { valid: false, message: 'Please select an LLM model.' };
        }

        if (!config.llm_api_endpoint) {
            return { valid: false, message: 'API endpoint cannot be empty.' };
        }

        // Validate API keys for cloud providers using shared utility
        const apiKeyValidation = ApiKeyUtils.validateForProvider(config.llm_provider, config.llm_api_endpoint);
        if (!apiKeyValidation.valid) {
            return apiKeyValidation;
        }

        return { valid: true, message: '' };
    }
};
