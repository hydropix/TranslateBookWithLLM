/**
 * API Client - Centralized API communication layer
 *
 * Provides a clean abstraction for all backend API calls
 * with consistent error handling and response processing.
 */

let API_BASE_URL = window.location.origin;

/**
 * Handle API errors consistently
 * @param {Response} response - Fetch response
 * @returns {Promise<Object>} Parsed error data
 */
async function handleApiError(response) {
    let errorData;
    try {
        errorData = await response.json();
    } catch {
        errorData = { error: `HTTP ${response.status}: ${response.statusText}` };
    }
    throw new Error(errorData.error || errorData.message || `Request failed with status ${response.status}`);
}

/**
 * Make API request with error handling
 * @param {string} endpoint - API endpoint path
 * @param {Object} [options] - Fetch options
 * @returns {Promise<Object>} Response data
 */
async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const response = await fetch(url, {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        ...options
    });

    if (!response.ok) {
        await handleApiError(response);
    }

    // Handle non-JSON responses (like file downloads)
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
        return await response.json();
    }

    return response;
}

/**
 * API Client interface
 */
export const ApiClient = {
    /**
     * Set the base URL for API requests
     * @param {string} url - Base URL
     */
    setBaseUrl(url) {
        API_BASE_URL = url;
    },

    /**
     * Get current base URL
     * @returns {string} Current base URL
     */
    getBaseUrl() {
        return API_BASE_URL;
    },

    // ========================================
    // Health & Configuration
    // ========================================

    /**
     * Check server health
     * @returns {Promise<Object>} Health status
     */
    async healthCheck() {
        return await apiRequest('/api/health');
    },

    /**
     * Get server configuration
     * @returns {Promise<Object>} Configuration object
     */
    async getConfig() {
        return await apiRequest('/api/config');
    },

    // ========================================
    // Translation Operations
    // ========================================

    /**
     * Start a new translation
     * @param {Object} config - Translation configuration
     * @returns {Promise<Object>} Translation job info
     */
    async startTranslation(config) {
        return await apiRequest('/api/translate', {
            method: 'POST',
            body: JSON.stringify(config)
        });
    },

    /**
     * Get translation status
     * @param {string} translationId - Translation ID
     * @returns {Promise<Object>} Translation status
     */
    async getTranslationStatus(translationId) {
        return await apiRequest(`/api/translation/${translationId}`);
    },

    /**
     * Get all active translations
     * @returns {Promise<Object>} Active translations list
     */
    async getActiveTranslations() {
        return await apiRequest('/api/translations');
    },

    /**
     * Interrupt a translation
     * @param {string} translationId - Translation ID
     * @returns {Promise<Object>} Interruption result
     */
    async interruptTranslation(translationId) {
        return await apiRequest(`/api/translation/${translationId}/interrupt`, {
            method: 'POST'
        });
    },

    // ========================================
    // File Upload & Management
    // ========================================

    /**
     * Upload a file
     * @param {File} file - File to upload
     * @returns {Promise<Object>} Upload result with file_path and file_type
     */
    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE_URL}/api/upload`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            await handleApiError(response);
        }

        return await response.json();
    },

    /**
     * Get list of managed files
     * @returns {Promise<Object>} Files list
     */
    async getFileList() {
        return await apiRequest('/api/files');
    },

    /**
     * Download a single file
     * @param {string} filename - Filename to download
     * @returns {string} Download URL
     */
    getFileDownloadUrl(filename) {
        return `${API_BASE_URL}/api/files/${encodeURIComponent(filename)}`;
    },

    /**
     * Delete a single file
     * @param {string} filename - Filename to delete
     * @returns {Promise<Object>} Delete result
     */
    async deleteFile(filename) {
        return await apiRequest(`/api/files/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });
    },

    /**
     * Batch download files as zip
     * @param {string[]} filenames - Array of filenames
     * @returns {Promise<Blob>} Zip file blob
     */
    async batchDownloadFiles(filenames) {
        const response = await apiRequest('/api/files/batch/download', {
            method: 'POST',
            body: JSON.stringify({ filenames })
        });

        return await response.blob();
    },

    /**
     * Batch delete files
     * @param {string[]} filenames - Array of filenames
     * @returns {Promise<Object>} Delete result
     */
    async batchDeleteFiles(filenames) {
        return await apiRequest('/api/files/batch/delete', {
            method: 'POST',
            body: JSON.stringify({ filenames })
        });
    },

    /**
     * Open a local file
     * @param {string} filename - Filename to open
     * @returns {Promise<Object>} Open result
     */
    async openLocalFile(filename) {
        return await apiRequest(`/api/files/${encodeURIComponent(filename)}/open`, {
            method: 'POST'
        });
    },

    /**
     * Clear uploaded files
     * @param {string[]} filePaths - Array of file paths to delete
     * @returns {Promise<Object>} Clear result
     */
    async clearUploadedFiles(filePaths) {
        return await apiRequest('/api/uploads/clear', {
            method: 'POST',
            body: JSON.stringify({ file_paths: filePaths })
        });
    },

    // ========================================
    // Model Management
    // ========================================

    /**
     * Get available models for a provider
     * @param {string} provider - Provider name ('ollama', 'gemini', 'openai', 'openrouter')
     * @param {Object} [options] - Additional options (api_endpoint, api_key)
     * @returns {Promise<Object>} Models list
     */
    async getModels(provider, options = {}) {
        const params = new URLSearchParams();

        if (provider === 'gemini' && options.apiKey) {
            params.append('provider', 'gemini');
            params.append('api_key', options.apiKey);
        } else if (provider === 'openai') {
            params.append('provider', 'openai');
        } else if (provider === 'openrouter') {
            params.append('provider', 'openrouter');
            if (options.apiKey) {
                params.append('api_key', options.apiKey);
            }
        } else {
            // Ollama
            if (options.apiEndpoint) {
                params.append('api_endpoint', options.apiEndpoint);
            }
        }

        return await apiRequest(`/api/models?${params.toString()}`);
    },

    // ========================================
    // Resumable Jobs
    // ========================================

    /**
     * Get resumable jobs list
     * @returns {Promise<Object>} Resumable jobs
     */
    async getResumableJobs() {
        return await apiRequest('/api/resumable');
    },

    /**
     * Resume a paused job
     * @param {string} translationId - Translation ID to resume
     * @returns {Promise<Object>} Resume result
     */
    async resumeJob(translationId) {
        return await apiRequest(`/api/resume/${translationId}`, {
            method: 'POST'
        });
    },

    /**
     * Delete a checkpoint
     * @param {string} translationId - Translation ID
     * @returns {Promise<Object>} Delete result
     */
    async deleteCheckpoint(translationId) {
        return await apiRequest(`/api/checkpoint/${translationId}`, {
            method: 'DELETE'
        });
    }
};

// Make API client available globally for debugging
if (typeof window !== 'undefined') {
    window.__API_CLIENT__ = ApiClient;
}
