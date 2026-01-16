/**
 * Lifecycle Manager - Page lifecycle and connection management
 *
 * Handles page initialization, cleanup, visibility changes,
 * and connection state management.
 */

import { StateManager } from '../core/state-manager.js';
import { ApiClient } from '../core/api-client.js';
import { WebSocketManager } from '../core/websocket-manager.js';
import { MessageLogger } from '../ui/message-logger.js';

// Storage configuration with versioning
const STORAGE_VERSION = 1;
const SERVER_SESSION_KEY = `tbl_server_session_id_v${STORAGE_VERSION}`;
const TRANSLATION_STATE_STORAGE_KEY = `tbl_translation_state_v${STORAGE_VERSION}`;

export const LifecycleManager = {
    /**
     * Initialize lifecycle manager
     */
    initialize() {
        // Clean up old storage versions
        this.cleanupOldStorageVersions();

        this.setupPageLoadHandler();
        this.setupBeforeUnloadHandler();
        this.setupPageHideHandler();
        this.setupVisibilityChangeHandler();
        this.startStateConsistencyCheck();
    },

    /**
     * Clean up old localStorage versions
     */
    cleanupOldStorageVersions() {
        try {
            // Remove old non-versioned keys
            const oldKeys = [
                'tbl_server_session_id',
                'tbl_translation_state'
            ];

            oldKeys.forEach(oldKey => {
                if (localStorage.getItem(oldKey)) {
                    localStorage.removeItem(oldKey);
                }
            });

            // Remove any other versions (future-proofing)
            for (let i = 0; i < STORAGE_VERSION; i++) {
                const oldSessionKey = `tbl_server_session_id_v${i}`;
                const oldTranslationKey = `tbl_translation_state_v${i}`;

                if (localStorage.getItem(oldSessionKey)) {
                    localStorage.removeItem(oldSessionKey);
                }
                if (localStorage.getItem(oldTranslationKey)) {
                    localStorage.removeItem(oldTranslationKey);
                }
            }
        } catch (error) {
            console.warn('Failed to cleanup old storage versions:', error);
        }
    },

    /**
     * Set up page load handler
     */
    setupPageLoadHandler() {
        window.addEventListener('load', async () => {
            try {
                const healthData = await ApiClient.healthCheck();
                MessageLogger.addLog('Server health check OK.');

                if (healthData.supported_formats) {
                    MessageLogger.addLog(`Supported file formats: ${healthData.supported_formats.join(', ')}`);
                }

                this.initializeConnection();

            } catch (error) {
                MessageLogger.showMessage(
                    `⚠️ Server unavailable at ${ApiClient.API_BASE_URL}. Ensure Python server is running. ${error.message}`,
                    'error'
                );
                MessageLogger.addLog(`❌ Failed to connect to server or load config: ${error.message}`);
            }
        });
    },

    /**
     * Get server session check promise (to be called early in initialization)
     * This ensures server restart detection happens BEFORE state restoration
     * @returns {Promise<boolean>} True if server was restarted
     */
    async getServerSessionCheck() {
        try {
            const healthData = await ApiClient.healthCheck();
            return await this.checkServerRestart(healthData);
        } catch (error) {
            console.warn('Could not check server session:', error);
            return false;
        }
    },

    /**
     * Check if server was restarted and clean up stale state
     * @param {Object} healthData - Health check response data
     * @returns {boolean} True if server was restarted
     */
    async checkServerRestart(healthData) {
        try {
            const serverSessionId = healthData.session_id || healthData.startup_time;

            if (!serverSessionId) {
                return false;
            }

            const lastSessionId = localStorage.getItem(SERVER_SESSION_KEY);

            if (lastSessionId && lastSessionId !== String(serverSessionId)) {
                MessageLogger.addLog('⚠️ Server restart detected. Clearing active translation state.');

                localStorage.removeItem(TRANSLATION_STATE_STORAGE_KEY);

                StateManager.setState('translation.currentJob', null);
                StateManager.setState('translation.isBatchActive', false);
                StateManager.setState('translation.activeJobs', []);
                StateManager.setState('translation.hasActive', false);

                try {
                    const progressSection = document.getElementById('progressSection');
                    const interruptBtn = document.getElementById('interruptBtn');
                    const translateBtn = document.getElementById('translateBtn');

                    if (progressSection) progressSection.style.display = 'none';
                    if (interruptBtn) interruptBtn.style.display = 'none';
                    if (translateBtn) {
                        translateBtn.disabled = false;
                        translateBtn.innerHTML = '▶️ Start Translation Batch';
                    }
                } catch (uiError) {
                    console.warn('Could not reset UI elements:', uiError);
                }

                localStorage.setItem(SERVER_SESSION_KEY, String(serverSessionId));

                return true;
            }

            localStorage.setItem(SERVER_SESSION_KEY, String(serverSessionId));

            return false;

        } catch (error) {
            console.error('Error checking server restart:', error);
            MessageLogger.addLog('⚠️ Could not verify server session state');
            return false;
        }
    },

    /**
     * Initialize WebSocket connection
     */
    initializeConnection() {
        if (typeof WebSocketManager !== 'undefined') {
            WebSocketManager.connect();
        } else {
            console.warn('WebSocketManager not available');
        }
    },

    setupBeforeUnloadHandler() {
    },

    setupPageHideHandler() {
        window.addEventListener('pagehide', (e) => {
            const isBatchActive = StateManager.getState('translation.isBatchActive');
            const currentJob = StateManager.getState('translation.currentJob');

            if (isBatchActive && currentJob && currentJob.translationId) {
                const interruptUrl = `${ApiClient.API_BASE_URL}/api/translation/${currentJob.translationId}/interrupt`;

                if (navigator.sendBeacon) {
                    const blob = new Blob(['{}'], { type: 'application/json' });
                    navigator.sendBeacon(interruptUrl, blob);
                } else {
                    try {
                        const xhr = new XMLHttpRequest();
                        xhr.open('POST', interruptUrl, false);
                        xhr.setRequestHeader('Content-Type', 'application/json');
                        xhr.send('{}');
                    } catch (error) {
                        console.error('Error interrupting translation on page close:', error);
                    }
                }
            }
        });
    },

    setupVisibilityChangeHandler() {
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.checkStateConsistency();
            }
        });
    },

    async checkStateConsistency() {
        const isBatchActive = StateManager.getState('translation.isBatchActive');
        const currentJob = StateManager.getState('translation.currentJob');

        if (!isBatchActive || !currentJob) {
            return;
        }

        const tidToCheck = currentJob.translationId;

        try {
            const data = await ApiClient.getTranslationStatus(tidToCheck);
            const serverStatus = data.status;

            if (serverStatus === 'completed' || serverStatus === 'error' || serverStatus === 'interrupted') {
                MessageLogger.addLog(`🔄 Detected state desync: job ${serverStatus} on server but UI still active. Syncing...`);

                window.dispatchEvent(new CustomEvent('translationUpdate', {
                    detail: {
                        translation_id: tidToCheck,
                        status: serverStatus,
                        result: data.result_preview || `[${serverStatus}]`,
                        error: data.error
                    }
                }));
            }
        } catch (error) {
            if (error.message && error.message.includes('404')) {
                MessageLogger.addLog(`⚠️ Translation job no longer exists on server. Resetting UI.`);
                window.dispatchEvent(new CustomEvent('resetUIToIdle'));
            } else {
                console.error('Error checking state consistency:', error);
            }
        }
    },

    /**
     * Start periodic state consistency checks (every 10 seconds)
     */
    startStateConsistencyCheck() {
        setInterval(() => {
            this.checkStateConsistency();
        }, 10000);
    }
};
