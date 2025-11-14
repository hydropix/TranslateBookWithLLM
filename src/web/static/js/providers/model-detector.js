/**
 * Model Detector - Detect model size and show recommendations
 *
 * Analyzes model names to determine parameter size and recommends
 * fast mode for models ≤12B parameters when translating EPUBs.
 */

import { DomHelpers } from '../ui/dom-helpers.js';

/**
 * Extract parameter size from model name
 * @param {string} modelName - Model name (e.g., "mistral-small:7b", "llama-12b")
 * @returns {number|null} Size in billions of parameters, or null if not detected
 */
function extractModelSize(modelName) {
    if (!modelName) return null;

    const lowerName = modelName.toLowerCase();

    // Pattern to detect model size (e.g., "7b", "12b", "3b", "1.5b")
    const sizeMatch = lowerName.match(/(\d+(?:\.\d+)?)b/);

    if (sizeMatch) {
        return parseFloat(sizeMatch[1]);
    }

    return null;
}

/**
 * Determine if a model is considered "small" (≤12B parameters)
 * @param {string} modelName - Model name
 * @returns {boolean} True if model is small
 */
function isSmallModel(modelName) {
    const size = extractModelSize(modelName);

    if (size === null) {
        return false; // Unknown size, assume not small
    }

    return size <= 12;
}

export const ModelDetector = {
    /**
     * Check if model is small and show recommendation for fast mode
     * Called when model selection changes or fast mode checkbox changes
     */
    checkAndShowRecommendation() {
        const modelSelect = DomHelpers.getElement('model');
        const fastModeCheckbox = DomHelpers.getElement('fastMode');
        const recommendationDiv = DomHelpers.getElement('smallModelRecommendation');

        if (!modelSelect || !fastModeCheckbox || !recommendationDiv) {
            console.warn('Model detector: Required elements not found');
            return;
        }

        const modelName = DomHelpers.getValue('model');
        const isFastModeEnabled = fastModeCheckbox.checked;

        // Show recommendation if small model and not already in fast mode (use inline style)
        if (isSmallModel(modelName) && !isFastModeEnabled) {
            if (recommendationDiv) recommendationDiv.style.display = 'block';
        } else {
            if (recommendationDiv) recommendationDiv.style.display = 'none';
        }
    },

    /**
     * Get model size in billions of parameters
     * @param {string} modelName - Model name
     * @returns {number|null} Size in billions, or null if unknown
     */
    getModelSize(modelName) {
        return extractModelSize(modelName);
    },

    /**
     * Check if a model is small (≤12B parameters)
     * @param {string} modelName - Model name
     * @returns {boolean} True if model is small
     */
    isSmallModel(modelName) {
        return isSmallModel(modelName);
    },

    /**
     * Get recommendation message for a given model
     * @param {string} modelName - Model name
     * @returns {string|null} Recommendation message, or null if no recommendation
     */
    getRecommendation(modelName) {
        const size = extractModelSize(modelName);

        if (size === null) {
            return null;
        }

        if (size <= 12) {
            return `This model (${size}B parameters) may struggle with complex EPUB formatting. ` +
                   `Consider enabling "Fast Mode" for better results.`;
        }

        return null;
    },

    /**
     * Initialize model detector event listeners
     */
    initialize() {
        const modelSelect = DomHelpers.getElement('model');
        const simpleModeCheckbox = DomHelpers.getElement('simpleMode');

        if (modelSelect) {
            modelSelect.addEventListener('change', () => {
                this.checkAndShowRecommendation();
            });
        }

        if (fastModeCheckbox) {
            fastModeCheckbox.addEventListener('change', () => {
                this.checkAndShowRecommendation();
            });
        }
    }
};
