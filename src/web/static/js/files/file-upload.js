/**
 * File Upload - File upload and drag-drop handling
 *
 * Handles file selection, drag & drop, and upload to server.
 * Manages output filename generation and file queue management.
 */

import { StateManager } from '../core/state-manager.js';
import { ApiClient } from '../core/api-client.js';
import { MessageLogger } from '../ui/message-logger.js';
import { DomHelpers } from '../ui/dom-helpers.js';
import { StatusManager } from '../utils/status-manager.js';

const FILE_QUEUE_STORAGE_KEY = 'tbl_file_queue';

// Track the last uploaded file for language synchronization
let lastUploadedFileName = null;

/**
 * Generate output filename based on pattern
 * @param {File} file - Original file
 * @param {string} pattern - Output pattern (e.g., "{originalName} ({targetLang}).{ext}")
 * @returns {string} Generated filename
 */
function generateOutputFilename(file, pattern) {
    const fileExtension = file.name.split('.').pop().toLowerCase();
    const originalNameWithoutExt = file.name.replace(/\.[^/.]+$/, "");

    // Get target language from the form
    const targetLangSelect = DomHelpers.getElement('targetLang');
    const customTargetLang = DomHelpers.getElement('customTargetLang');
    let targetLang = targetLangSelect?.value || '';

    // If "Other" is selected, use the custom input value
    if (targetLang === 'Other') {
        targetLang = customTargetLang?.value?.trim() || '';
    }

    // Use "Translated" as fallback if no language specified
    if (!targetLang) {
        targetLang = 'Translated';
    }

    return pattern
        .replace("{originalName}", originalNameWithoutExt)
        .replace("{targetLang}", targetLang)
        .replace("{ext}", fileExtension);
}

/**
 * Detect file type from extension
 * @param {string} filename - Filename
 * @returns {string} File type ('txt', 'epub', 'srt')
 */
function detectFileType(filename) {
    const extension = filename.split('.').pop().toLowerCase();

    if (extension === 'epub') return 'epub';
    if (extension === 'srt') return 'srt';
    return 'txt';
}

/**
 * Set language in select dropdown (case-insensitive match)
 * @param {string} selectId - Select element ID
 * @param {string} languageValue - Language value to set
 * @returns {boolean} True if language was set successfully (actual language, not "Other")
 */
function setLanguageInSelect(selectId, languageValue) {
    const select = DomHelpers.getElement(selectId);
    if (!select) {
        return false;
    }

    // Skip "Other" as a language value - it's not a real language
    if (languageValue === 'Other') {
        return false;
    }

    // Try to find matching option (case-insensitive), excluding "Other"
    let matchedOption = null;
    for (let i = 0; i < select.options.length; i++) {
        const option = select.options[i];
        // Skip "Other" option - we only match actual languages
        if (option.value === 'Other') continue;

        if (option.value && option.value.toLowerCase() === languageValue.toLowerCase()) {
            matchedOption = option;
            break;
        }
    }

    if (matchedOption) {
        // Set the value and trigger change events
        select.value = matchedOption.value;
        select.selectedIndex = Array.from(select.options).indexOf(matchedOption);

        // Trigger events to ensure reactivity
        select.dispatchEvent(new Event('input', { bubbles: true }));
        select.dispatchEvent(new Event('change', { bubbles: true }));

        return true;
    }

    return false;
}

export const FileUpload = {
    /**
     * Initialize file upload handlers
     */
    initialize() {
        this.setupDragDrop();
        this.setupFileInput();
        this.setupLanguageSyncListeners();
        this.setupDefaultConfigListener();
        // Restore file queue from localStorage synchronously first
        // This ensures files are available immediately on page load
        this.restoreFileQueueSync();
        // Then verify files exist on server after a delay
        setTimeout(() => this.verifyAndCleanupFileQueue(), 1000);
    },

    /**
     * Set up listener for default config loaded event
     * This ensures file languages are synced after FormManager loads defaults
     */
    setupDefaultConfigListener() {
        // Listen for the event (in case it fires after this setup)
        window.addEventListener('defaultConfigLoaded', () => {
            this.syncPendingFileLanguages();
        });

        // Also check after a delay in case the event already fired
        // (FormManager.initialize runs before FileUpload.initialize)
        setTimeout(() => {
            this.syncPendingFileLanguages();
        }, 500);
    },

    /**
     * Set up listeners to sync language changes with the last uploaded file
     */
    setupLanguageSyncListeners() {
        const sourceLangSelect = DomHelpers.getElement('sourceLang');
        const targetLangSelect = DomHelpers.getElement('targetLang');
        const customSourceLang = DomHelpers.getElement('customSourceLang');
        const customTargetLang = DomHelpers.getElement('customTargetLang');

        // Sync source language changes
        if (sourceLangSelect) {
            sourceLangSelect.addEventListener('change', () => {
                // If Auto-detect is selected (empty value), trigger language detection
                if (sourceLangSelect.value === '') {
                    this._triggerAutoDetection();
                } else {
                    this._syncLanguageToLastFile('source');
                }
            });
        }
        if (customSourceLang) {
            customSourceLang.addEventListener('input', () => {
                this._syncLanguageToLastFile('source');
            });
        }

        // Sync target language changes
        if (targetLangSelect) {
            targetLangSelect.addEventListener('change', () => {
                this._syncLanguageToLastFile('target');
            });
        }
        if (customTargetLang) {
            customTargetLang.addEventListener('input', () => {
                this._syncLanguageToLastFile('target');
            });
        }
    },

    /**
     * Sync language selection to the last uploaded file
     * @param {string} type - 'source' or 'target'
     */
    _syncLanguageToLastFile(type) {
        if (!lastUploadedFileName) return;

        const filesToProcess = StateManager.getState('files.toProcess') || [];
        const fileIndex = filesToProcess.findIndex(f => f.name === lastUploadedFileName);

        if (fileIndex === -1) {
            // File no longer in queue, reset tracking
            lastUploadedFileName = null;
            return;
        }

        const file = filesToProcess[fileIndex];

        // Only sync if file is still queued (not started)
        if (file.status !== 'Queued') return;

        if (type === 'source') {
            file.sourceLanguage = this._getCurrentSourceLanguage();
        } else {
            file.targetLanguage = this._getCurrentTargetLanguage();
        }

        StateManager.setState('files.toProcess', filesToProcess);
        this._saveFileQueue();
        this.updateFileDisplay();
    },

    /**
     * Trigger automatic language detection on the last uploaded file
     * Called when user selects "Auto-detect" in the source language dropdown
     */
    async _triggerAutoDetection() {
        if (!lastUploadedFileName) {
            MessageLogger.showMessage('No file uploaded yet. Upload a file to auto-detect its language.', 'info');
            return;
        }

        const filesToProcess = StateManager.getState('files.toProcess') || [];
        const file = filesToProcess.find(f => f.name === lastUploadedFileName);

        if (!file) {
            MessageLogger.showMessage('File not found in queue.', 'error');
            return;
        }

        if (!file.filePath) {
            MessageLogger.showMessage('File path not available for language detection.', 'error');
            return;
        }

        // Check if we already have a detected language with good confidence
        if (file.detectedLanguage && file.languageConfidence >= 0.7) {
            const success = setLanguageInSelect('sourceLang', file.detectedLanguage);
            if (success) {
                MessageLogger.showMessage(
                    `Using previously detected language: ${file.detectedLanguage} ` +
                    `(${(file.languageConfidence * 100).toFixed(0)}% confidence)`,
                    'success'
                );
            }
            return;
        }

        // Call the API to detect language
        MessageLogger.showMessage(`Detecting language for ${file.name}...`, 'info');

        try {
            const result = await ApiClient.detectLanguage(file.filePath);

            if (result.success && result.detected_language) {
                // Update file object with detected language
                file.detectedLanguage = result.detected_language;
                file.languageConfidence = result.language_confidence;

                // Only auto-set if confidence >= 70%
                if (result.language_confidence >= 0.7) {
                    file.sourceLanguage = result.detected_language;
                    const success = setLanguageInSelect('sourceLang', result.detected_language);

                    if (!success) {
                        MessageLogger.showMessage(
                            `Language detected but not in list: ${result.detected_language}`,
                            'info'
                        );
                    }
                } else {
                    MessageLogger.showMessage(
                        `Low confidence detection: ${result.detected_language} ` +
                        `(${(result.language_confidence * 100).toFixed(0)}% confidence). ` +
                        `Please select the source language manually.`,
                        'warning'
                    );
                }

                // Update state
                StateManager.setState('files.toProcess', filesToProcess);
                this._saveFileQueue();
                this.updateFileDisplay();
            } else {
                MessageLogger.showMessage('Could not detect language from file content.', 'warning');
            }
        } catch (error) {
            MessageLogger.showMessage(`Language detection failed: ${error.message}`, 'error');
        }
    },

    /**
     * Get the name of the last uploaded file
     * @returns {string|null} Last uploaded filename
     */
    getLastUploadedFileName() {
        return lastUploadedFileName;
    },

    /**
     * Clear the last uploaded file tracking
     */
    clearLastUploadedFile() {
        lastUploadedFileName = null;
    },

    /**
     * Set a file as the active file for editing
     * Syncs the file's language parameters TO the UI (file → interface)
     * @param {string} filename - Name of the file to set as active
     */
    setActiveFile(filename) {
        const filesToProcess = StateManager.getState('files.toProcess') || [];
        const file = filesToProcess.find(f => f.name === filename);

        if (!file) {
            return false;
        }

        // Only allow setting as active if file is still Queued
        if (file.status !== 'Queued') {
            MessageLogger.showMessage(`Cannot edit file '${filename}' - it's already being processed.`, 'info');
            return false;
        }

        // Update the active file tracking
        lastUploadedFileName = filename;

        // Sync file parameters TO the interface (file → UI)
        this._syncFileToInterface(file);

        // Update display to reflect new active file
        this.updateFileDisplay();

        return true;
    },

    /**
     * Sync file language parameters to the UI interface
     * This is the reverse direction: file → interface
     * @param {Object} file - File object with sourceLanguage and targetLanguage
     * @private
     */
    _syncFileToInterface(file) {
        // Sync source language
        if (file.sourceLanguage) {
            const success = setLanguageInSelect('sourceLang', file.sourceLanguage);
            if (!success) {
                // Language not in list or is "Other", set to "Other" and show custom input
                const sourceLangSelect = DomHelpers.getElement('sourceLang');
                const customSourceLang = DomHelpers.getElement('customSourceLang');
                const sourceContainer = DomHelpers.getElement('customSourceLangContainer');
                if (sourceLangSelect) {
                    sourceLangSelect.value = 'Other';
                    // Trigger change event to ensure FormManager shows the container
                    sourceLangSelect.dispatchEvent(new Event('change', { bubbles: true }));
                }
                // Also show the container directly (in case event handler is not yet set up)
                if (sourceContainer) {
                    sourceContainer.style.display = 'block';
                }
                // Only fill custom input if it's not literally "Other"
                if (customSourceLang && file.sourceLanguage !== 'Other') {
                    customSourceLang.value = file.sourceLanguage;
                }
            }
        }

        // Sync target language
        if (file.targetLanguage) {
            const success = setLanguageInSelect('targetLang', file.targetLanguage);
            if (!success) {
                // Language not in list or is "Other", set to "Other" and show custom input
                const targetLangSelect = DomHelpers.getElement('targetLang');
                const customTargetLang = DomHelpers.getElement('customTargetLang');
                const targetContainer = DomHelpers.getElement('customTargetLangContainer');
                if (targetLangSelect) {
                    targetLangSelect.value = 'Other';
                    // Trigger change event to ensure FormManager shows the container
                    targetLangSelect.dispatchEvent(new Event('change', { bubbles: true }));
                }
                // Also show the container directly (in case event handler is not yet set up)
                if (targetContainer) {
                    targetContainer.style.display = 'block';
                }
                // Only fill custom input if it's not literally "Other"
                if (customTargetLang && file.targetLanguage !== 'Other') {
                    customTargetLang.value = file.targetLanguage;
                }
            }
        }
    },

    /**
     * Pre-populate a language field during restore
     * If the language is not in the standard list, set select to "Other" and show container
     * @param {string} selectId - Select element ID
     * @param {string} inputId - Custom input element ID
     * @param {string} containerId - Container element ID
     * @param {string} languageValue - Language value to set
     * @private
     */
    _prePopulateLanguageField(selectId, inputId, containerId, languageValue) {
        if (!languageValue) return;

        const select = DomHelpers.getElement(selectId);
        const input = DomHelpers.getElement(inputId);
        const container = DomHelpers.getElement(containerId);

        if (!select || !input) return;

        // Check if language is in the dropdown (case-insensitive)
        let foundInList = false;
        for (const option of select.options) {
            if (option.value === 'Other' || !option.value) continue;
            if (option.value.toLowerCase() === languageValue.toLowerCase()) {
                foundInList = true;
                break;
            }
        }

        if (!foundInList) {
            // Language not in list - set to "Other" and populate custom field
            select.value = 'Other';
            input.value = languageValue;
            if (container) {
                container.style.display = 'block';
            }
        }
    },

    /**
     * Save file queue to localStorage
     * @private
     */
    _saveFileQueue() {
        try {
            const filesToProcess = StateManager.getState('files.toProcess') || [];
            // Save only serializable data (exclude File objects)
            const serializableFiles = filesToProcess.map(f => ({
                name: f.name,
                filePath: f.filePath,
                fileType: f.fileType,
                originalExtension: f.originalExtension,
                status: f.status,
                outputFilename: f.outputFilename,
                size: f.size,
                sourceLanguage: f.sourceLanguage,
                targetLanguage: f.targetLanguage,
                translationId: f.translationId,
                detectedLanguage: f.detectedLanguage,
                languageConfidence: f.languageConfidence,
                thumbnail: f.thumbnail
            }));
            localStorage.setItem(FILE_QUEUE_STORAGE_KEY, JSON.stringify(serializableFiles));
        } catch {
            // Failed to save file queue
        }
    },

    /**
     * Restore file queue from localStorage synchronously (no server verification)
     * This ensures files appear immediately on page load
     */
    restoreFileQueueSync() {
        try {
            const stored = localStorage.getItem(FILE_QUEUE_STORAGE_KEY);
            if (!stored) return;

            const savedFiles = JSON.parse(stored);
            if (!Array.isArray(savedFiles) || savedFiles.length === 0) return;

            // Restore files to state immediately (reset status to Queued for non-completed files)
            const filesToRestore = savedFiles.map(f => ({
                ...f,
                status: f.status === 'Completed' ? 'Completed' : 'Queued'
            }));

            StateManager.setState('files.toProcess', filesToRestore);
            this.updateFileDisplay();

            // Find the last queued file and sync its languages to the interface
            const lastQueuedFile = [...filesToRestore].reverse().find(f => f.status === 'Queued');
            if (lastQueuedFile) {
                lastUploadedFileName = lastQueuedFile.name;
                // Store file for deferred sync (will be called after FormManager loads defaults)
                this._pendingFileSync = lastQueuedFile;

                // Pre-populate custom language fields and select "Other" if needed
                // This ensures the UI state is correct before any other initialization
                this._prePopulateLanguageField(
                    'sourceLang',
                    'customSourceLang',
                    'customSourceLangContainer',
                    lastQueuedFile.sourceLanguage
                );
                this._prePopulateLanguageField(
                    'targetLang',
                    'customTargetLang',
                    'customTargetLangContainer',
                    lastQueuedFile.targetLanguage
                );
            }
        } catch {
            // Failed to restore file queue
        }
    },

    /**
     * Sync pending file languages to interface (called after FormManager.loadDefaultConfig)
     * This ensures file languages override browser-detected defaults
     */
    syncPendingFileLanguages() {
        // Get the last queued file from state if _pendingFileSync is not set
        // This handles the case where the event fired before restoreFileQueueSync ran
        let fileToSync = this._pendingFileSync;

        if (!fileToSync) {
            const filesToProcess = StateManager.getState('files.toProcess') || [];
            const lastQueuedFile = [...filesToProcess].reverse().find(f => f.status === 'Queued');
            if (lastQueuedFile) {
                fileToSync = lastQueuedFile;
            }
        }

        if (fileToSync) {
            this._syncFileToInterface(fileToSync);
            this._pendingFileSync = null;
        }
    },

    /**
     * Verify and cleanup file queue after restoration
     * This runs after a delay to verify files still exist on server
     */
    async verifyAndCleanupFileQueue() {
        try {
            const filesToProcess = StateManager.getState('files.toProcess') || [];
            if (filesToProcess.length === 0) return;

            // Get file paths to verify
            const filePaths = filesToProcess.map(f => f.filePath);

            // Verify which files still exist on the server
            const verification = await ApiClient.verifyUploadedFiles(filePaths);

            // Filter to only existing files
            const existingFilePaths = new Set(verification.existing || []);
            const validFiles = filesToProcess.filter(f => existingFilePaths.has(f.filePath));

            // Update state if any files were removed
            if (validFiles.length !== filesToProcess.length) {
                StateManager.setState('files.toProcess', validFiles);
                this.notifyFileListChanged();
            }
        } catch {
            // Failed to verify file queue
        }
    },

    /**
     * Restore file queue from localStorage and verify files exist
     * @deprecated Use restoreFileQueueSync() followed by verifyAndCleanupFileQueue() instead
     */
    async restoreFileQueue() {
        try {
            const stored = localStorage.getItem(FILE_QUEUE_STORAGE_KEY);
            if (!stored) return;

            const savedFiles = JSON.parse(stored);
            if (!Array.isArray(savedFiles) || savedFiles.length === 0) return;

            // Get file paths to verify
            const filePaths = savedFiles.map(f => f.filePath);

            // Verify which files still exist on the server
            const verification = await ApiClient.verifyUploadedFiles(filePaths);

            // Filter to only existing files
            const existingFilePaths = new Set(verification.existing || []);
            const restoredFiles = savedFiles.filter(f => existingFilePaths.has(f.filePath));

            if (restoredFiles.length > 0) {
                // Restore files to state (reset status to Queued for non-completed files)
                const filesToRestore = restoredFiles.map(f => ({
                    ...f,
                    status: f.status === 'Completed' ? 'Completed' : 'Queued'
                }));

                StateManager.setState('files.toProcess', filesToRestore);
                this.notifyFileListChanged();
            }

            // Update localStorage with only existing files
            this._saveFileQueue();

        } catch {
            // Failed to restore file queue
        }
    },

    /**
     * Get current source language from form
     * @returns {string} Current source language (empty string if not set)
     */
    _getCurrentSourceLanguage() {
        let sourceLanguageVal = DomHelpers.getValue('sourceLang');
        if (sourceLanguageVal === 'Other') {
            sourceLanguageVal = DomHelpers.getValue('customSourceLang').trim();
        }
        return sourceLanguageVal || '';
    },

    /**
     * Get current target language from form
     * @returns {string} Current target language (empty string if not set)
     */
    _getCurrentTargetLanguage() {
        let targetLanguageVal = DomHelpers.getValue('targetLang');
        if (targetLanguageVal === 'Other') {
            targetLanguageVal = DomHelpers.getValue('customTargetLang').trim();
        }
        return targetLanguageVal || '';
    },

    /**
     * Set up drag and drop event handlers
     */
    setupDragDrop() {
        const uploadArea = DomHelpers.getElement('fileUpload');
        if (!uploadArea) {
            return;
        }

        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            DomHelpers.addClass(uploadArea, 'dragging');
        });

        uploadArea.addEventListener('dragleave', () => {
            DomHelpers.removeClass(uploadArea, 'dragging');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            DomHelpers.removeClass(uploadArea, 'dragging');

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleFiles(Array.from(files));
            }
        });
    },

    /**
     * Set up file input change handler
     */
    setupFileInput() {
        const fileInput = DomHelpers.getElement('fileInput');
        if (fileInput) {
            fileInput.addEventListener('change', (e) => {
                this.handleFileSelect(e);
            });
        }
    },

    /**
     * Handle file selection from input
     * @param {Event} event - Change event from file input
     */
    handleFileSelect(event) {
        const files = event.target.files;
        if (files.length > 0) {
            this.handleFiles(Array.from(files));
            // Clear input so same file can be selected again
            DomHelpers.setValue('fileInput', '');
        }
    },

    /**
     * Handle multiple files (from drag-drop or file input)
     * @param {File[]} files - Array of files
     */
    async handleFiles(files) {
        for (const file of files) {
            await this.addFileToQueue(file);
        }

        // Trigger UI update
        this.notifyFileListChanged();
    },

    /**
     * Add a file to the processing queue
     * @param {File} file - File to add
     */
    async addFileToQueue(file) {
        // Get current files from state
        const filesToProcess = StateManager.getState('files.toProcess') || [];

        // Check for duplicates
        if (filesToProcess.find(f => f.name === file.name)) {
            MessageLogger.showMessage(`File '${file.name}' is already in the list.`, 'info');
            return;
        }

        // Get output filename pattern
        const outputPattern = DomHelpers.getValue('outputFilenamePattern') ||
                             "{originalName} ({targetLang}).{ext}";
        const outputFilename = generateOutputFilename(file, outputPattern);
        const fileExtension = file.name.split('.').pop().toLowerCase();

        MessageLogger.showMessage(`Uploading file: ${file.name}...`, 'info');

        try {
            // Upload file using ApiClient
            const uploadResult = await ApiClient.uploadFile(file);

            // Determine initial source language:
            // - Use detected language if confidence >= 70%
            // - Otherwise use current form value
            let initialSourceLanguage;
            if (uploadResult.detected_language && uploadResult.language_confidence >= 0.7) {
                initialSourceLanguage = uploadResult.detected_language;
            } else {
                initialSourceLanguage = this._getCurrentSourceLanguage();
            }

            // Create file object
            const fileObject = {
                name: file.name,
                filePath: uploadResult.file_path,
                fileType: uploadResult.file_type,
                originalExtension: fileExtension,
                status: 'Queued',
                outputFilename: outputFilename,
                size: file.size,
                sourceLanguage: initialSourceLanguage,
                targetLanguage: this._getCurrentTargetLanguage(),
                translationId: null,
                result: null,
                content: null,
                detectedLanguage: uploadResult.detected_language || null,
                languageConfidence: uploadResult.language_confidence || null,
                thumbnail: uploadResult.thumbnail || null  // EPUB cover thumbnail
            };

            // Add to state
            const updatedFiles = [...filesToProcess, fileObject];
            StateManager.setState('files.toProcess', updatedFiles);

            // Track this as the last uploaded file for language sync
            lastUploadedFileName = file.name;

            // Auto-update source language field if detected with good confidence
            if (uploadResult.detected_language && uploadResult.language_confidence >= 0.7) {
                const sourceLangInput = DomHelpers.getElement('sourceLang');

                if (sourceLangInput) {
                    // Update the form to match the detected language - silent when successful
                    const success = setLanguageInSelect('sourceLang', uploadResult.detected_language);

                    if (!success) {
                        MessageLogger.showMessage(
                            `File '${file.name}' (${uploadResult.file_type}) uploaded. ` +
                            `Language detected but not in list: ${uploadResult.detected_language}`,
                            'info'
                        );
                    }
                }
            }

        } catch (error) {
            MessageLogger.showMessage(
                `Failed to upload file '${file.name}': ${error.message}`,
                'error'
            );
        }
    },

    /**
     * Update file display in the UI
     */
    updateFileDisplay() {
        const filesToProcess = StateManager.getState('files.toProcess') || [];
        const fileListContainer = DomHelpers.getElement('fileListContainer');
        const fileInfo = DomHelpers.getElement('fileInfo');
        const translateBtn = DomHelpers.getElement('translateBtn');

        if (!fileListContainer) return;

        // Clear existing list
        fileListContainer.innerHTML = '';

        if (filesToProcess.length > 0) {
            // Display files in reverse order (newest first) but keep execution order unchanged
            const displayFiles = [...filesToProcess].reverse();
            displayFiles.forEach(file => {
                const li = document.createElement('li');
                li.setAttribute('data-filename', file.name);

                // Mark the last uploaded file as active (editable via language selectors)
                const isActiveFile = file.name === lastUploadedFileName && file.status === 'Queued';
                li.className = isActiveFile ? 'file-item file-active' : 'file-item';

                // Add click handler to set file as active (only for Queued files)
                if (file.status === 'Queued') {
                    li.style.cursor = 'pointer';
                    li.onclick = () => {
                        this.setActiveFile(file.name);
                    };
                }

                // Icon/thumbnail container
                const iconContainer = document.createElement('span');
                iconContainer.className = 'file-icon';

                if (file.fileType === 'epub' && file.thumbnail) {
                    // Show thumbnail
                    const img = document.createElement('img');
                    img.src = `/api/thumbnails/${encodeURIComponent(file.thumbnail)}`;
                    img.alt = 'Cover';
                    img.className = 'epub-thumbnail';

                    // Fallback to generic SVG on error
                    img.onerror = () => {
                        iconContainer.innerHTML = this._createGenericEPUBIcon();
                    };

                    iconContainer.appendChild(img);
                } else {
                    // Generic icons
                    iconContainer.innerHTML = this._getFileIcon(file.fileType);
                }

                li.appendChild(iconContainer);

                // File info
                const infoSpan = document.createElement('span');
                infoSpan.className = 'file-info';

                // Create file name and size
                const fileNameText = document.createTextNode(`${file.name} (${(file.size / 1024).toFixed(2)} KB) `);
                infoSpan.appendChild(fileNameText);

                // Add language pair display (read-only)
                if (file.sourceLanguage && file.targetLanguage) {
                    const langSpan = document.createElement('span');
                    langSpan.className = 'file-languages';
                    langSpan.style.fontSize = '0.85em';
                    langSpan.style.color = '#6b7280';
                    langSpan.textContent = `[${file.sourceLanguage} → ${file.targetLanguage}] `;
                    infoSpan.appendChild(langSpan);
                }

                const statusSpan = document.createElement('span');
                statusSpan.className = 'file-status';
                statusSpan.textContent = `(${file.status})`;

                infoSpan.appendChild(statusSpan);

                // Add "Active" badge for the current editable file
                if (isActiveFile) {
                    const activeBadge = document.createElement('span');
                    activeBadge.className = 'file-active-badge';
                    activeBadge.innerHTML = '<span class="material-symbols-outlined" style="font-size: 12px;">edit</span> Active';
                    infoSpan.appendChild(activeBadge);
                }

                li.appendChild(infoSpan);

                // Remove button
                const removeBtn = document.createElement('button');
                removeBtn.className = 'file-remove-btn';
                removeBtn.title = 'Remove file';
                removeBtn.innerHTML = '<span class="material-symbols-outlined">close</span>';
                removeBtn.onclick = (e) => {
                    e.stopPropagation();
                    this.removeFile(file.name);
                };
                li.appendChild(removeBtn);

                fileListContainer.appendChild(li);
            });

            // Show file info section
            DomHelpers.show(fileInfo);

            // Enable translate button if not batch active and LLM is connected
            const isBatchActive = StateManager.getState('translation.isBatchActive') || false;
            if (translateBtn) {
                translateBtn.disabled = isBatchActive || !StatusManager.isConnected();
            }
        } else {
            // Hide file info section
            DomHelpers.hide(fileInfo);

            // Disable translate button
            if (translateBtn) {
                translateBtn.disabled = true;
            }
        }
    },

    /**
     * Notify that file list has changed (triggers UI update)
     */
    notifyFileListChanged() {
        // Update display immediately
        this.updateFileDisplay();

        // Persist to localStorage
        this._saveFileQueue();

        // Emit event so other modules can react
        const event = new CustomEvent('fileListChanged');
        window.dispatchEvent(event);
    },

    /**
     * Remove a file from the queue by name
     * @param {string} filename - Name of file to remove
     */
    removeFile(filename) {
        const filesToProcess = StateManager.getState('files.toProcess') || [];
        const updatedFiles = filesToProcess.filter(f => f.name !== filename);
        StateManager.setState('files.toProcess', updatedFiles);

        // If removing the last uploaded file, clear tracking
        if (filename === lastUploadedFileName) {
            lastUploadedFileName = null;
        }

        this.notifyFileListChanged();
    },

    /**
     * Clear all files from queue
     */
    clearAll() {
        StateManager.setState('files.toProcess', []);
        lastUploadedFileName = null;
        this.notifyFileListChanged();
    },

    /**
     * Get file icon based on file type
     * @param {string} fileType - File type ('txt', 'epub', 'srt')
     * @returns {string} HTML string for icon
     */
    _getFileIcon(fileType) {
        if (fileType === 'epub') {
            return this._createGenericEPUBIcon();
        } else if (fileType === 'srt') {
            return '🎬';
        }
        return '📄';
    },

    /**
     * Create generic EPUB icon as SVG
     * @returns {string} SVG HTML string
     */
    _createGenericEPUBIcon() {
        return `
            <svg class="generic-epub-icon" viewBox="0 0 48 64" xmlns="http://www.w3.org/2000/svg">
                <!-- Book cover -->
                <rect x="8" y="4" width="32" height="56" rx="2"
                      fill="#5a8ee8" stroke="#3676d8" stroke-width="2"/>
                <!-- Book spine line -->
                <path d="M8 12 L40 12" stroke="#3676d8" stroke-width="1.5"/>
                <!-- Text lines -->
                <path d="M12 20 L36 20 M12 28 L36 28 M12 36 L30 36"
                      stroke="white" stroke-width="2" stroke-linecap="round" opacity="0.8"/>
                <!-- EPUB badge -->
                <circle cx="24" cy="48" r="4" fill="white" opacity="0.9"/>
                <text x="24" y="51" text-anchor="middle" font-size="5"
                      fill="#3676d8" font-weight="bold">E</text>
            </svg>
        `;
    }
};
