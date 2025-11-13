/**
 * Validators - Input validation utilities
 *
 * Provides validation functions for forms and user inputs
 */

import { MessageLogger } from '../ui/message-logger.js';
import { DomHelpers } from '../ui/dom-helpers.js';

export const Validators = {
    /**
     * Show validation error message
     * @param {string} message - Error message
     * @returns {boolean} Always returns false for chaining
     */
    showError(message) {
        MessageLogger.showMessage(message, 'error');
        return false;
    },

    /**
     * Validate that a value is not empty
     * @param {string} value - Value to validate
     * @param {string} fieldName - Field name for error message
     * @returns {boolean} True if valid
     */
    required(value, fieldName) {
        if (!value || value.trim() === '') {
            return this.showError(`${fieldName} is required.`);
        }
        return true;
    },

    /**
     * Validate language selection
     * @param {string} sourceLanguage - Source language
     * @param {string} targetLanguage - Target language
     * @returns {boolean} True if valid
     */
    validateLanguages(sourceLanguage, targetLanguage) {
        if (!this.required(sourceLanguage, 'Source language')) return false;
        if (!this.required(targetLanguage, 'Target language')) return false;

        if (sourceLanguage.toLowerCase() === targetLanguage.toLowerCase()) {
            return this.showError('Source and target languages must be different.');
        }

        return true;
    },

    /**
     * Validate model selection
     * @param {string} model - Model name
     * @returns {boolean} True if valid
     */
    validateModel(model) {
        return this.required(model, 'Model');
    },

    /**
     * Validate API endpoint
     * @param {string} endpoint - API endpoint URL
     * @returns {boolean} True if valid
     */
    validateApiEndpoint(endpoint) {
        if (!this.required(endpoint, 'API Endpoint')) return false;

        try {
            new URL(endpoint);
            return true;
        } catch {
            return this.showError('API Endpoint must be a valid URL.');
        }
    },

    /**
     * Validate provider API key
     * @param {string} provider - Provider name
     * @param {string} apiKey - API key
     * @returns {boolean} True if valid
     */
    validateProviderApiKey(provider, apiKey) {
        if (provider === 'gemini') {
            if (!apiKey || apiKey.trim() === '') {
                return this.showError('Gemini API key is required when using Gemini provider.');
            }
        }

        if (provider === 'openai') {
            if (!apiKey || apiKey.trim() === '') {
                return this.showError('OpenAI API key is required when using OpenAI provider.');
            }
        }

        return true;
    },

    /**
     * Validate number in range
     * @param {number} value - Value to validate
     * @param {number} min - Minimum value
     * @param {number} max - Maximum value
     * @param {string} fieldName - Field name for error message
     * @returns {boolean} True if valid
     */
    validateRange(value, min, max, fieldName) {
        if (isNaN(value)) {
            return this.showError(`${fieldName} must be a number.`);
        }

        if (value < min || value > max) {
            return this.showError(`${fieldName} must be between ${min} and ${max}.`);
        }

        return true;
    },

    /**
     * Validate file selection
     * @param {Array} files - Files array
     * @returns {boolean} True if valid
     */
    validateFileSelection(files) {
        if (!files || files.length === 0) {
            return this.showError('Please select at least one file to translate.');
        }

        return true;
    },

    /**
     * Validate batch configuration before starting translation
     * @param {Object} formValues - Form values from FormManager
     * @param {Array} files - Files to process
     * @returns {boolean} True if valid
     */
    validateBatchConfig(formValues, files) {
        // Validate files
        if (!this.validateFileSelection(files)) return false;

        // Validate languages
        if (!this.validateLanguages(formValues.sourceLanguage, formValues.targetLanguage)) {
            return false;
        }

        // Validate model
        if (!this.validateModel(formValues.model)) return false;

        // Validate provider-specific requirements
        if (!this.validateProviderApiKey(formValues.provider, formValues.apiKey)) {
            return false;
        }

        // Validate API endpoint for Ollama and OpenAI
        if (formValues.provider === 'ollama' || formValues.provider === 'openai') {
            if (!this.validateApiEndpoint(formValues.apiEndpoint)) {
                return false;
            }
        }

        return true;
    }
};
