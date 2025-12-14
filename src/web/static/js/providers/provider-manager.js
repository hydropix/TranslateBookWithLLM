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
 * Fallback OpenRouter models list (used when API fetch fails)
 * Sorted by cost: free/cheap first
 */
const OPENROUTER_FALLBACK_MODELS = [
    // Free/Cheap models
    { value: 'google/gemini-2.0-flash-exp:free', label: 'Gemini 2.0 Flash (Free)' },
    { value: 'google/gemini-2.0-flash-001', label: 'Gemini 2.0 Flash' },
    { value: 'meta-llama/llama-3.3-70b-instruct', label: 'Llama 3.3 70B' },
    { value: 'qwen/qwen-2.5-72b-instruct', label: 'Qwen 2.5 72B' },
    { value: 'mistralai/mistral-small-24b-instruct-2501', label: 'Mistral Small 24B' },
    // Mid-tier models
    { value: 'anthropic/claude-3-5-haiku-20241022', label: 'Claude 3.5 Haiku' },
    { value: 'openai/gpt-4o-mini', label: 'GPT-4o Mini' },
    { value: 'google/gemini-1.5-pro', label: 'Gemini 1.5 Pro' },
    { value: 'deepseek/deepseek-chat', label: 'DeepSeek Chat' },
    // Premium models
    { value: 'anthropic/claude-sonnet-4', label: 'Claude Sonnet 4' },
    { value: 'openai/gpt-4o', label: 'GPT-4o' },
    { value: 'anthropic/claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet' }
];

/**
 * Auto-retry configuration for Ollama
 */
const OLLAMA_RETRY_INTERVAL = 3000; // 3 seconds
const OLLAMA_MAX_SILENT_RETRIES = 5; // Show message after 5 failed attempts
let ollamaRetryTimer = null;
let ollamaRetryCount = 0;

/**
 * Format price for display (per 1M tokens)
 * @param {number} price - Price per 1M tokens
 * @returns {string} Formatted price string
 */
function formatPrice(price) {
    if (price === 0) return 'Free';
    if (price < 0.01) return '<$0.01';
    if (price < 1) return `$${price.toFixed(2)}`;
    return `$${price.toFixed(2)}`;
}

/**
 * Populate model select with options
 * @param {Array} models - Array of model objects or strings
 * @param {string} defaultModel - Default model to select
 * @param {string} provider - Provider type ('ollama', 'gemini', 'openai', 'openrouter')
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
    } else if (provider === 'openrouter') {
        models.forEach(model => {
            const option = document.createElement('option');
            // Handle both API response format (id) and fallback format (value)
            const modelId = model.id || model.value;
            option.value = modelId;

            // Format label with pricing info if available
            if (model.pricing && model.pricing.prompt_per_million !== undefined) {
                const inputPrice = formatPrice(model.pricing.prompt_per_million);
                const outputPrice = formatPrice(model.pricing.completion_per_million);
                option.textContent = `${model.name || modelId} (In: ${inputPrice}/M, Out: ${outputPrice}/M)`;
                option.title = `Context: ${model.context_length || 'N/A'} tokens`;
            } else {
                // Fallback format
                option.textContent = model.label || model.name || modelId;
            }

            if (modelId === defaultModel) option.selected = true;
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
        const openrouterSettings = DomHelpers.getElement('openrouterSettings');

        // Show/hide provider-specific settings (use inline style for elements with inline display:none)
        if (provider === 'ollama') {
            DomHelpers.show('ollamaSettings');
            if (geminiSettings) geminiSettings.style.display = 'none';
            if (openaiSettings) openaiSettings.style.display = 'none';
            if (openrouterSettings) openrouterSettings.style.display = 'none';
            if (loadModels) this.loadOllamaModels();
        } else if (provider === 'gemini') {
            DomHelpers.hide('ollamaSettings');
            if (geminiSettings) geminiSettings.style.display = 'block';
            if (openaiSettings) openaiSettings.style.display = 'none';
            if (openrouterSettings) openrouterSettings.style.display = 'none';
            if (loadModels) this.loadGeminiModels();
        } else if (provider === 'openai') {
            DomHelpers.hide('ollamaSettings');
            if (geminiSettings) geminiSettings.style.display = 'none';
            if (openaiSettings) openaiSettings.style.display = 'block';
            if (openrouterSettings) openrouterSettings.style.display = 'none';
            if (loadModels) this.loadOpenAIModels();
        } else if (provider === 'openrouter') {
            DomHelpers.hide('ollamaSettings');
            if (geminiSettings) geminiSettings.style.display = 'none';
            if (openaiSettings) openaiSettings.style.display = 'none';
            if (openrouterSettings) openrouterSettings.style.display = 'block';
            if (loadModels) this.loadOpenRouterModels();
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
        } else if (provider === 'openrouter') {
            this.loadOpenRouterModels();
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
     * Load OpenRouter models dynamically from API (text-only models, sorted by price)
     */
    async loadOpenRouterModels() {
        const modelSelect = DomHelpers.getElement('model');
        if (!modelSelect) return;

        modelSelect.innerHTML = '<option value="">Loading OpenRouter models...</option>';

        try {
            const apiKey = DomHelpers.getValue('openrouterApiKey')?.trim();
            const data = await ApiClient.getModels('openrouter', { apiKey });

            if (data.models && data.models.length > 0) {
                MessageLogger.showMessage('', '');
                populateModelSelect(data.models, data.default, 'openrouter');
                MessageLogger.addLog(`✅ ${data.count} OpenRouter text models loaded (sorted by price, cheapest first)`);
                ModelDetector.checkAndShowRecommendation();

                // Update available models in state
                StateManager.setState('models.availableModels', data.models.map(m => m.id));
            } else {
                // Use fallback list
                const errorMessage = data.error || 'Could not load models from OpenRouter API';
                MessageLogger.showMessage(`⚠️ ${errorMessage}. Using fallback list.`, 'warning');
                populateModelSelect(OPENROUTER_FALLBACK_MODELS, 'anthropic/claude-sonnet-4', 'openrouter');
                MessageLogger.addLog(`⚠️ Using fallback OpenRouter models list`);

                // Update available models in state
                StateManager.setState('models.availableModels', OPENROUTER_FALLBACK_MODELS.map(m => m.value));
            }

        } catch (error) {
            // Use fallback list on error
            MessageLogger.showMessage(`⚠️ Error fetching OpenRouter models. Using fallback list.`, 'warning');
            MessageLogger.addLog(`⚠️ OpenRouter API error: ${error.message}. Using fallback list.`);
            populateModelSelect(OPENROUTER_FALLBACK_MODELS, 'anthropic/claude-sonnet-4', 'openrouter');

            // Update available models in state
            StateManager.setState('models.availableModels', OPENROUTER_FALLBACK_MODELS.map(m => m.value));
        }
    },

    /**
     * Get current provider
     * @returns {string} Current provider ('ollama', 'gemini', 'openai', 'openrouter')
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
