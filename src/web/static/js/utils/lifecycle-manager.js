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

const SERVER_SESSION_KEY = 'tbl_server_session_id';

export const LifecycleManager = {
    /**
     * Initialize lifecycle manager
     */
    initialize() {
        this.setupPageLoadHandler();
        this.setupBeforeUnloadHandler();
        this.setupPageHideHandler();
        this.setupVisibilityChangeHandler();
        this.startStateConsistencyCheck();
    },

    /**
     * Set up page load handler
     */
    setupPageLoadHandler() {
        window.addEventListener('load', async () => {
            try {
                // Health check
                const healthData = await ApiClient.healthCheck();
                MessageLogger.addLog('Server health check OK.');

                if (healthData.supported_formats) {
                    MessageLogger.addLog(`Supported file formats: ${healthData.supported_formats.join(', ')}`);
                }

                // Check if server was restarted
                await this.checkServerRestart(healthData);

                // Initialize WebSocket connection
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
     * Check if server was restarted and clean up stale state
     * @param {Object} healthData - Health check response data
     */
    async checkServerRestart(healthData) {
        try {
            // Get server session ID (could be startup timestamp or unique ID)
            const serverSessionId = healthData.session_id || healthData.startup_time;

            if (!serverSessionId) {
                // Server doesn't provide session ID, skip check
                return;
            }

            const lastSessionId = localStorage.getItem(SERVER_SESSION_KEY);

            if (lastSessionId && lastSessionId !== serverSessionId) {
                // Server was restarted! Clean up translation state only
                console.warn('Server restart detected. Cleaning up translation state...');
                MessageLogger.addLog('⚠️ Server restart detected. Clearing active translation state.');

                // Clear translation state (the translation job no longer exists)
                const TRANSLATION_STATE_STORAGE_KEY = 'tbl_translation_state';
                localStorage.removeItem(TRANSLATION_STATE_STORAGE_KEY);

                // Reset translation state in memory
                StateManager.setState('translation.currentJob', null);
                StateManager.setState('translation.isBatchActive', false);
                StateManager.setState('translation.activeJobs', []);
                StateManager.setState('translation.hasActive', false);

                // Note: We keep the file queue (tbl_file_queue) as files might still exist on disk
                // The FileUpload module will verify which files still exist
            }

            // Store current session ID
            localStorage.setItem(SERVER_SESSION_KEY, serverSessionId);

        } catch (error) {
            console.warn('Error checking server restart:', error);
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

    /**
     * Set up beforeunload handler
     * Note: No confirmation popup needed - checkpoint system saves all progress automatically
     */
    setupBeforeUnloadHandler() {
        // No-op: checkpoint system handles saving, no need to warn user
    },

    /**
     * Set up pagehide handler (interrupt translation if user confirms closure)
     */
    setupPageHideHandler() {
        window.addEventListener('pagehide', (e) => {
            const isBatchActive = StateManager.getState('translation.isBatchActive');
            const currentJob = StateManager.getState('translation.currentJob');

            // If there's an active translation, interrupt it before page closes
            if (isBatchActive && currentJob && currentJob.translationId) {
                // Use sendBeacon for reliable delivery even during page unload
                const interruptUrl = `${ApiClient.API_BASE_URL}/api/translation/${currentJob.translationId}/interrupt`;

                // sendBeacon is specifically designed to work during page unload
                // It queues the request and sends it even after the page is gone
                if (navigator.sendBeacon) {
                    // Create a Blob with proper content type for POST request
                    const blob = new Blob(['{}'], { type: 'application/json' });
                    navigator.sendBeacon(interruptUrl, blob);
                } else {
                    // Fallback: try synchronous XMLHttpRequest (older browsers)
                    try {
                        const xhr = new XMLHttpRequest();
                        xhr.open('POST', interruptUrl, false); // false = synchronous
                        xhr.setRequestHeader('Content-Type', 'application/json');
                        xhr.send('{}');
                    } catch (error) {
                        console.error('Error interrupting translation on page close:', error);
                    }
                }
            }
        });
    },

    /**
     * Set up page visibility change handler
     */
    setupVisibilityChangeHandler() {
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                console.log('Page hidden');
            } else {
                console.log('Page visible');
                // Refresh state when page becomes visible again
                this.checkStateConsistency();
            }
        });
    },

    /**
     * Periodic state consistency check
     * Runs to detect and fix UI state inconsistencies
     */
    async checkStateConsistency() {
        const isBatchActive = StateManager.getState('translation.isBatchActive');
        const currentJob = StateManager.getState('translation.currentJob');

        // Only check if we think there's an active batch
        if (!isBatchActive || !currentJob) {
            return;
        }

        const tidToCheck = currentJob.translationId;

        try {
            const data = await ApiClient.getTranslationStatus(tidToCheck);
            const serverStatus = data.status;

            // Check if server says the job is done but UI still shows it as active
            if (serverStatus === 'completed' || serverStatus === 'error' || serverStatus === 'interrupted') {
                console.warn(`Server reports job ${tidToCheck} is ${serverStatus}, but UI still shows active. Syncing state.`);
                MessageLogger.addLog(`🔄 Detected state desync: job ${serverStatus} on server but UI still active. Syncing...`);

                // Trigger the appropriate UI update via event
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
            // Job doesn't exist anymore on server
            if (error.message && error.message.includes('404')) {
                console.warn(`Job ${tidToCheck} not found on server. Resetting UI.`);
                MessageLogger.addLog(`⚠️ Translation job no longer exists on server. Resetting UI.`);

                // Reset UI via event
                window.dispatchEvent(new CustomEvent('resetUIToIdle'));
            } else {
                console.error('Error checking state consistency:', error);
                // Don't reset on network errors - could just be temporary
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
