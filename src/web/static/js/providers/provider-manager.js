/**
 * Provider Manager - LLM provider switching and model loading
 *
 * Manages switching between different LLM providers (Ollama, Gemini, OpenAI)
 * and loading available models for each provider.
 */

import { StateManager } from '../core/state-manager.js';
import { ApiClient } from '../core/api-client.js';
import { MessageLogger } from '../ui/message-logger.js';
import { DomHelpers } from '../ui/dom-helpers.js';
import { ModelDetector } from './model-detector.js';

/**
 * Common OpenAI models list
 */
const OPENAI_MODELS = [
    { value: 'gpt-4o', label: 'GPT-4o (Latest)' },
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
    { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
    { value: 'gpt-4', label: 'GPT-4' },
    { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' }
];

/**
 * Auto-retry configuration for Ollama
 */
const OLLAMA_RETRY_INTERVAL = 3000; // 3 seconds
const OLLAMA_MAX_SILENT_RETRIES = 5; // Show message after 5 failed attempts
let ollamaRetryTimer = null;
let ollamaRetryCount = 0;

/**
 * Populate model select with options
 * @param {Array} models - Array of model objects or strings
 * @param {string} defaultModel - Default model to select
 * @param {string} provider - Provider type ('ollama', 'gemini', 'openai')
 */
function populateModelSelect(models, defaultModel = null, provider = 'ollama') {
    const modelSelect = DomHelpers.getElement('model');
    if (!modelSelect) return;

    modelSelect.innerHTML = '';

    if (provider === 'gemini') {
        models.forEach(model => {
            const option = document.createElement('option');
            option.value = model.name;
            option.textContent = `${model.displayName || model.name} - ${model.description || ''}`;
            option.title = `Input: ${model.inputTokenLimit || 'N/A'} tokens, Output: ${model.outputTokenLimit || 'N/A'} tokens`;
            if (model.name === defaultModel) option.selected = true;
            modelSelect.appendChild(option);
        });
    } else if (provider === 'openai') {
        models.forEach(model => {
            const option = document.createElement('option');
            option.value = model.value;
            option.textContent = model.label;
            modelSelect.appendChild(option);
        });
    } else {
        // Ollama - models are strings
        models.forEach(modelName => {
            const option = document.createElement('option');
            option.value = modelName;
            option.textContent = modelName;
            if (modelName === defaultModel) option.selected = true;
            modelSelect.appendChild(option);
        });
    }
}

export const ProviderManager = {
    /**
     * Initialize provider manager
     */
    initialize() {
        const providerSelect = DomHelpers.getElement('llmProvider');

        if (providerSelect) {
            providerSelect.addEventListener('change', () => {
                // Stop any ongoing Ollama retries when switching providers
                this.stopOllamaAutoRetry();
                this.toggleProviderSettings();
            });
        }

        // Show initial provider settings and load models immediately
        this.toggleProviderSettings(true);
    },

    /**
     * Toggle provider-specific settings visibility
     * @param {boolean} loadModels - Whether to load models (default: true)
     */
    toggleProviderSettings(loadModels = true) {
        const provider = DomHelpers.getValue('llmProvider');

        // Update state
        StateManager.setState('ui.currentProvider', provider);

        // Get provider settings elements
        const ollamaSettings = DomHelpers.getElement('ollamaSettings');
        const geminiSettings = DomHelpers.getElement('geminiSettings');
        const openaiSettings = DomHelpers.getElement('openaiSettings');

        // Show/hide provider-specific settings (use inline style for elements with inline display:none)
        if (provider === 'ollama') {
            DomHelpers.show('ollamaSettings');
            if (geminiSettings) geminiSettings.style.display = 'none';
            if (openaiSettings) openaiSettings.style.display = 'none';
            if (loadModels) this.loadOllamaModels();
        } else if (provider === 'gemini') {
            DomHelpers.hide('ollamaSettings');
            if (geminiSettings) geminiSettings.style.display = 'block';
            if (openaiSettings) openaiSettings.style.display = 'none';
            if (loadModels) this.loadGeminiModels();
        } else if (provider === 'openai') {
            DomHelpers.hide('ollamaSettings');
            if (geminiSettings) geminiSettings.style.display = 'none';
            if (openaiSettings) openaiSettings.style.display = 'block';
            if (loadModels) this.loadOpenAIModels();
        }
    },

    /**
     * Refresh models for current provider
     */
    refreshModels() {
        const provider = DomHelpers.getValue('llmProvider');

        if (provider === 'ollama') {
            this.loadOllamaModels();
        } else if (provider === 'gemini') {
            this.loadGeminiModels();
        } else if (provider === 'openai') {
            this.loadOpenAIModels();
        }
    },

    /**
     * Load Ollama models with auto-retry on failure
     */
    async loadOllamaModels() {
        const modelSelect = DomHelpers.getElement('model');
        if (!modelSelect) return;

        // Cancel any pending request
        const currentRequest = StateManager.getState('models.currentLoadRequest');
        if (currentRequest) {
            currentRequest.cancelled = true;
        }

        // Create new request tracker
        const thisRequest = { cancelled: false };
        StateManager.setState('models.currentLoadRequest', thisRequest);

        modelSelect.innerHTML = '<option value="">Loading models...</option>';

        try {
            const apiEndpoint = DomHelpers.getValue('apiEndpoint');
            const data = await ApiClient.getModels('ollama', { apiEndpoint });

            // Check if request was cancelled
            if (thisRequest.cancelled) {
                console.log('Model load request was cancelled');
                return;
            }

            // Verify provider hasn't changed
            const currentProvider = DomHelpers.getValue('llmProvider');
            if (currentProvider !== 'ollama') {
                console.log('Provider changed during model load, ignoring Ollama response');
                return;
            }

            if (data.models && data.models.length > 0) {
                // Success - stop auto-retry
                this.stopOllamaAutoRetry();

                MessageLogger.showMessage('', '');
                populateModelSelect(data.models, data.default, 'ollama');
                MessageLogger.addLog(`✅ ${data.count} LLM model(s) loaded. Default: ${data.default}`);
                ModelDetector.checkAndShowRecommendation();

                // Update available models in state
                StateManager.setState('models.availableModels', data.models);
            } else {
                // No models available - start auto-retry
                const errorMessage = data.error || 'No LLM models available. Ensure Ollama is running and accessible.';

                // Show message only after several retries
                if (ollamaRetryCount >= OLLAMA_MAX_SILENT_RETRIES) {
                    MessageLogger.showMessage(`⚠️ ${errorMessage}`, 'error');
                    MessageLogger.addLog(`⚠️ No models available from Ollama at ${apiEndpoint} (auto-retrying every ${OLLAMA_RETRY_INTERVAL/1000}s...)`);
                }

                modelSelect.innerHTML = '<option value="">Waiting for Ollama...</option>';
                this.startOllamaAutoRetry();
            }

        } catch (error) {
            if (!thisRequest.cancelled) {
                // Connection error - start auto-retry
                if (ollamaRetryCount >= OLLAMA_MAX_SILENT_RETRIES) {
                    MessageLogger.showMessage(`⚠️ Waiting for Ollama to start...`, 'warning');
                    MessageLogger.addLog(`⚠️ Ollama not accessible, auto-retrying every ${OLLAMA_RETRY_INTERVAL/1000}s...`);
                }

                modelSelect.innerHTML = '<option value="">Waiting for Ollama...</option>';
                this.startOllamaAutoRetry();
            }
        } finally {
            // Clear request tracker if it's still ours
            if (StateManager.getState('models.currentLoadRequest') === thisRequest) {
                StateManager.setState('models.currentLoadRequest', null);
            }
        }
    },

    /**
     * Start auto-retry mechanism for Ollama
     */
    startOllamaAutoRetry() {
        // Don't start if already running
        if (ollamaRetryTimer) {
            return;
        }

        ollamaRetryCount++;

        ollamaRetryTimer = setTimeout(() => {
            ollamaRetryTimer = null;

            // Only retry if still on Ollama provider
            const currentProvider = DomHelpers.getValue('llmProvider');
            if (currentProvider === 'ollama') {
                console.log(`Auto-retrying Ollama connection (attempt ${ollamaRetryCount})...`);
                this.loadOllamaModels();
            }
        }, OLLAMA_RETRY_INTERVAL);
    },

    /**
     * Stop auto-retry mechanism for Ollama
     */
    stopOllamaAutoRetry() {
        if (ollamaRetryTimer) {
            clearTimeout(ollamaRetryTimer);
            ollamaRetryTimer = null;
        }
        ollamaRetryCount = 0;
    },

    /**
     * Load Gemini models
     */
    async loadGeminiModels() {
        const modelSelect = DomHelpers.getElement('model');
        if (!modelSelect) return;

        modelSelect.innerHTML = '<option value="">Loading Gemini models...</option>';

        try {
            const apiKey = DomHelpers.getValue('geminiApiKey').trim();
            const data = await ApiClient.getModels('gemini', { apiKey });

            if (data.models && data.models.length > 0) {
                MessageLogger.showMessage('', '');
                populateModelSelect(data.models, data.default, 'gemini');
                MessageLogger.addLog(`✅ ${data.count} Gemini model(s) loaded (excluding thinking models)`);
                ModelDetector.checkAndShowRecommendation();

                // Update available models in state
                StateManager.setState('models.availableModels', data.models);
            } else {
                const errorMessage = data.error || 'No Gemini models available.';
                MessageLogger.showMessage(`⚠️ ${errorMessage}`, 'error');
                modelSelect.innerHTML = '<option value="">No models available</option>';
                MessageLogger.addLog(`⚠️ No Gemini models available`);
            }

        } catch (error) {
            MessageLogger.showMessage(`❌ Error fetching Gemini models: ${error.message}`, 'error');
            MessageLogger.addLog(`❌ Failed to retrieve Gemini model list: ${error.message}`);
            modelSelect.innerHTML = '<option value="">Error loading models</option>';
        }
    },

    /**
     * Load OpenAI models (static list)
     */
    async loadOpenAIModels() {
        const modelSelect = DomHelpers.getElement('model');
        if (!modelSelect) return;

        populateModelSelect(OPENAI_MODELS, null, 'openai');
        MessageLogger.addLog(`✅ OpenAI models loaded (common models)`);
        ModelDetector.checkAndShowRecommendation();

        // Update available models in state
        StateManager.setState('models.availableModels', OPENAI_MODELS.map(m => m.value));
    },

    /**
     * Get current provider
     * @returns {string} Current provider ('ollama', 'gemini', 'openai')
     */
    getCurrentProvider() {
        return StateManager.getState('ui.currentProvider') || DomHelpers.getValue('llmProvider');
    },

    /**
     * Get current model
     * @returns {string} Current model name
     */
    getCurrentModel() {
        return StateManager.getState('ui.currentModel') || DomHelpers.getValue('model');
    },

    /**
     * Set current model
     * @param {string} modelName - Model name to set
     */
    setCurrentModel(modelName) {
        DomHelpers.setValue('model', modelName);
        StateManager.setState('ui.currentModel', modelName);
        ModelDetector.checkAndShowRecommendation();
    }
};
