/**
 * Settings Manager - User preferences persistence
 *
 * Handles saving/loading user preferences via:
 * 1. localStorage for quick preferences (last model, provider, languages)
 * 2. Server API for sensitive data (API keys saved to .env)
 */

import { ApiClient } from './api-client.js';
import { DomHelpers } from '../ui/dom-helpers.js';
import { MessageLogger } from '../ui/message-logger.js';

const STORAGE_KEY = 'tbl_user_preferences';

/**
 * Flag to prevent localStorage from overriding .env default model
 * Set to true once the .env model has been applied
 */
let envModelApplied = false;

/**
 * Settings that are saved to localStorage (non-sensitive)
 */
const LOCAL_SETTINGS = [
    'lastProvider',
    'lastModel',
    'lastSourceLanguage',
    'lastTargetLanguage',
    'lastApiEndpoint'
];

/**
 * Settings that are saved to .env via API (sensitive)
 */
const ENV_SETTINGS_MAP = {
    'geminiApiKey': 'GEMINI_API_KEY',
    'openaiApiKey': 'OPENAI_API_KEY',
    'openrouterApiKey': 'OPENROUTER_API_KEY'
};

export const SettingsManager = {
    /**
     * Initialize settings manager - load saved preferences
     */
    initialize() {
        this.loadLocalPreferences();
    },

    /**
     * Get all local preferences from localStorage
     * @returns {Object} Saved preferences
     */
    getLocalPreferences() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            return stored ? JSON.parse(stored) : {};
        } catch (e) {
            console.error('Error reading preferences:', e);
            return {};
        }
    },

    /**
     * Save preferences to localStorage
     * @param {Object} prefs - Preferences to save
     */
    saveLocalPreferences(prefs) {
        try {
            const current = this.getLocalPreferences();
            const updated = { ...current, ...prefs };
            localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
        } catch (e) {
            console.error('Error saving preferences:', e);
        }
    },

    /**
     * Load and apply saved local preferences to the form
     */
    loadLocalPreferences() {
        const prefs = this.getLocalPreferences();

        // Apply last provider
        if (prefs.lastProvider) {
            const providerSelect = DomHelpers.getElement('llmProvider');
            if (providerSelect) {
                providerSelect.value = prefs.lastProvider;
                // Trigger change event to show correct settings panel
                providerSelect.dispatchEvent(new Event('change'));
            }
        }

        // Apply last model (after models are loaded)
        if (prefs.lastModel) {
            // Store for later application after models load
            window.__pendingModelSelection = prefs.lastModel;
        }

        // Apply last languages
        if (prefs.lastSourceLanguage) {
            this._setLanguage('sourceLang', 'customSourceLang', prefs.lastSourceLanguage);
        }
        if (prefs.lastTargetLanguage) {
            this._setLanguage('targetLang', 'customTargetLang', prefs.lastTargetLanguage);
        }

        // Apply last API endpoint
        if (prefs.lastApiEndpoint) {
            DomHelpers.setValue('apiEndpoint', prefs.lastApiEndpoint);
        }
    },

    /**
     * Set language in select/custom input
     * @private
     */
    _setLanguage(selectId, customInputId, value) {
        const select = DomHelpers.getElement(selectId);
        const customInput = DomHelpers.getElement(customInputId);

        if (!select) return;

        // Check if value exists in options
        let found = false;
        for (let option of select.options) {
            if (option.value.toLowerCase() === value.toLowerCase()) {
                select.value = option.value;
                found = true;
                break;
            }
        }

        if (!found && customInput) {
            select.value = 'Other';
            customInput.value = value;
            DomHelpers.show(customInput);
        }
    },

    /**
     * Save current form state to local preferences
     */
    saveCurrentState() {
        const prefs = {
            lastProvider: DomHelpers.getValue('llmProvider'),
            lastModel: DomHelpers.getValue('model'),
            lastSourceLanguage: this._getLanguageValue('sourceLang', 'customSourceLang'),
            lastTargetLanguage: this._getLanguageValue('targetLang', 'customTargetLang'),
            lastApiEndpoint: DomHelpers.getValue('apiEndpoint')
        };

        this.saveLocalPreferences(prefs);
    },

    /**
     * Get language value from select or custom input
     * @private
     */
    _getLanguageValue(selectId, customInputId) {
        const selectVal = DomHelpers.getValue(selectId);
        if (selectVal === 'Other') {
            return DomHelpers.getValue(customInputId) || selectVal;
        }
        return selectVal;
    },

    /**
     * Save API key to .env file via server
     * @param {string} provider - Provider name (gemini, openai, openrouter)
     * @param {string} apiKey - The API key to save
     * @returns {Promise<boolean>} Success status
     */
    async saveApiKey(provider, apiKey) {
        const keyMap = {
            'gemini': 'GEMINI_API_KEY',
            'openai': 'OPENAI_API_KEY',
            'openrouter': 'OPENROUTER_API_KEY'
        };

        const envKey = keyMap[provider];
        if (!envKey) {
            console.error('Unknown provider:', provider);
            return false;
        }

        try {
            const result = await ApiClient.saveSettings({ [envKey]: apiKey });
            if (result.success) {
                MessageLogger.addLog(`API key saved for ${provider}`);
                return true;
            }
            return false;
        } catch (e) {
            console.error('Error saving API key:', e);
            MessageLogger.addLog(`Failed to save API key: ${e.message}`, 'error');
            return false;
        }
    },

    /**
     * Save all current settings (both local and to .env)
     * @param {boolean} includeApiKeys - Whether to save API keys to .env
     * @returns {Promise<Object>} Result with success status
     */
    async saveAllSettings(includeApiKeys = false) {
        // Save local preferences
        this.saveCurrentState();

        if (includeApiKeys) {
            // Collect API keys to save
            const envSettings = {};
            const provider = DomHelpers.getValue('llmProvider');

            if (provider === 'gemini') {
                const key = DomHelpers.getValue('geminiApiKey');
                if (key) envSettings['GEMINI_API_KEY'] = key;
            } else if (provider === 'openai') {
                const key = DomHelpers.getValue('openaiApiKey');
                if (key) envSettings['OPENAI_API_KEY'] = key;
            } else if (provider === 'openrouter') {
                const key = DomHelpers.getValue('openrouterApiKey');
                if (key) envSettings['OPENROUTER_API_KEY'] = key;
            }

            // Also save provider and model as defaults
            envSettings['LLM_PROVIDER'] = provider;
            const model = DomHelpers.getValue('model');
            if (model) {
                // Save to provider-specific model variable
                if (provider === 'openrouter') {
                    envSettings['OPENROUTER_MODEL'] = model;
                } else if (provider === 'gemini') {
                    envSettings['GEMINI_MODEL'] = model;
                } else {
                    // Ollama and OpenAI use DEFAULT_MODEL
                    envSettings['DEFAULT_MODEL'] = model;
                }
            }

            // Save languages
            const srcLang = this._getLanguageValue('sourceLang', 'customSourceLang');
            const tgtLang = this._getLanguageValue('targetLang', 'customTargetLang');
            if (srcLang) envSettings['DEFAULT_SOURCE_LANGUAGE'] = srcLang;
            if (tgtLang) envSettings['DEFAULT_TARGET_LANGUAGE'] = tgtLang;

            if (Object.keys(envSettings).length > 0) {
                try {
                    const result = await ApiClient.saveSettings(envSettings);
                    // Reset the lock since user explicitly saved their choice
                    this.resetEnvModelApplied();
                    return { success: true, savedToEnv: result.saved_keys };
                } catch (e) {
                    console.error('Error saving to .env:', e);
                    return { success: false, error: e.message };
                }
            }
        }

        return { success: true, savedToEnv: [] };
    },

    /**
     * Apply pending model selection after models are loaded
     * Called by provider-manager after loading models
     */
    applyPendingModelSelection() {
        // Don't apply localStorage preference if .env model was already applied
        if (envModelApplied) {
            console.log('⏭️ Skipping localStorage model - .env model already applied');
            delete window.__pendingModelSelection;
            return;
        }

        if (window.__pendingModelSelection) {
            const modelSelect = DomHelpers.getElement('model');
            if (modelSelect && modelSelect.options.length > 0) {
                // Check if the model exists in options
                let found = false;
                for (let option of modelSelect.options) {
                    if (option.value === window.__pendingModelSelection) {
                        modelSelect.value = window.__pendingModelSelection;
                        found = true;
                        console.log(`✅ Applied saved model preference: ${window.__pendingModelSelection}`);
                        break;
                    }
                }
                if (found) {
                    delete window.__pendingModelSelection;
                }
            }
        }
    },

    /**
     * Mark that the .env default model has been applied
     * This prevents localStorage from overriding it
     */
    markEnvModelApplied() {
        envModelApplied = true;
        console.log('🔒 .env default model locked in');
    },

    /**
     * Reset the envModelApplied flag
     * Called after user explicitly saves settings to .env
     */
    resetEnvModelApplied() {
        envModelApplied = false;
        console.log('🔓 .env model lock reset - user saved new settings');
    },

    /**
     * Check if .env model was already applied
     * @returns {boolean}
     */
    isEnvModelApplied() {
        return envModelApplied;
    }
};

// Auto-save preferences when leaving page
if (typeof window !== 'undefined') {
    window.addEventListener('beforeunload', () => {
        SettingsManager.saveCurrentState();
    });
}
