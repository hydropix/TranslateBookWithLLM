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

/**
 * Generate output filename based on pattern
 * @param {File} file - Original file
 * @param {string} pattern - Output pattern (e.g., "translated_{originalName}.{ext}")
 * @returns {string} Generated filename
 */
function generateOutputFilename(file, pattern) {
    const fileExtension = file.name.split('.').pop().toLowerCase();
    const originalNameWithoutExt = file.name.replace(/\.[^/.]+$/, "");

    return pattern
        .replace("{originalName}", originalNameWithoutExt)
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

export const FileUpload = {
    /**
     * Initialize file upload handlers
     */
    initialize() {
        this.setupDragDrop();
        this.setupFileInput();
    },

    /**
     * Set up drag and drop event handlers
     */
    setupDragDrop() {
        const uploadArea = DomHelpers.getElement('fileUpload');
        if (!uploadArea) {
            console.warn('File upload area not found');
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
                             "translated_{originalName}.{ext}";
        const outputFilename = generateOutputFilename(file, outputPattern);
        const fileExtension = file.name.split('.').pop().toLowerCase();

        MessageLogger.showMessage(`Uploading file: ${file.name}...`, 'info');

        try {
            // Upload file using ApiClient
            const uploadResult = await ApiClient.uploadFile(file);

            // Create file object
            const fileObject = {
                name: file.name,
                filePath: uploadResult.file_path,
                fileType: uploadResult.file_type,
                originalExtension: fileExtension,
                status: 'Queued',
                outputFilename: outputFilename,
                size: file.size,
                translationId: null,
                result: null,
                content: null
            };

            // Add to state
            const updatedFiles = [...filesToProcess, fileObject];
            StateManager.setState('files.toProcess', updatedFiles);

            MessageLogger.showMessage(
                `File '${file.name}' (${uploadResult.file_type}) uploaded. Path: ${uploadResult.file_path}`,
                'success'
            );

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
            // Add each file to the list
            filesToProcess.forEach(file => {
                const li = document.createElement('li');
                li.setAttribute('data-filename', file.name);

                const fileIcon = file.fileType === 'epub' ? '📚' :
                                (file.fileType === 'srt' ? '🎬' : '📄');

                li.textContent = `${fileIcon} ${file.name} (${(file.size / 1024).toFixed(2)} KB) `;

                const statusSpan = document.createElement('span');
                statusSpan.className = 'file-status';
                statusSpan.textContent = `(${file.status})`;
                li.appendChild(statusSpan);

                fileListContainer.appendChild(li);
            });

            // Show file info section
            DomHelpers.show(fileInfo);

            // Enable translate button if not batch active
            const isBatchActive = StateManager.getState('translation.isBatchActive') || false;
            if (translateBtn) {
                translateBtn.disabled = isBatchActive;
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
        this.notifyFileListChanged();
    },

    /**
     * Clear all files from queue
     */
    clearAll() {
        StateManager.setState('files.toProcess', []);
        this.notifyFileListChanged();
    }
};
