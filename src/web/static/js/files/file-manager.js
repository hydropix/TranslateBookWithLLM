/**
 * File Manager - File list management and operations
 *
 * Handles file list display, selection management, batch operations
 * (download/delete), and individual file actions.
 */

import { StateManager } from '../core/state-manager.js';
import { ApiClient } from '../core/api-client.js';
import { MessageLogger } from '../ui/message-logger.js';
import { DomHelpers } from '../ui/dom-helpers.js';

export const FileManager = {
    /**
     * Initialize file manager
     */
    initialize() {
        this.setupEventListeners();
        this.refreshFileList();
    },

    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Listen for file list changes
        window.addEventListener('fileListChanged', () => {
            this.refreshFileList();
        });

        // Select all checkbox
        const selectAllCheckbox = DomHelpers.getElement('selectAllFiles');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', () => {
                this.toggleSelectAll();
            });
        }

        // Batch download button
        const batchDownloadBtn = DomHelpers.getElement('batchDownloadBtn');
        if (batchDownloadBtn) {
            batchDownloadBtn.addEventListener('click', () => {
                this.downloadSelectedFiles();
            });
        }

        // Batch delete button
        const batchDeleteBtn = DomHelpers.getElement('batchDeleteBtn');
        if (batchDeleteBtn) {
            batchDeleteBtn.addEventListener('click', () => {
                this.deleteSelectedFiles();
            });
        }
    },

    /**
     * Refresh file list from server
     */
    async refreshFileList() {
        const loadingDiv = DomHelpers.getElement('fileListLoading');
        const containerDiv = DomHelpers.getElement('fileManagementContainer');
        const tableBody = DomHelpers.getElement('fileTableBody');
        const emptyDiv = DomHelpers.getElement('fileListEmpty');

        if (!tableBody) return;

        // Show loading, hide container (use inline style to override)
        if (loadingDiv) loadingDiv.style.display = 'block';
        if (containerDiv) containerDiv.style.display = 'none';

        try {
            const data = await ApiClient.getFileList();

            // Hide loading, show container (use inline style to override)
            if (loadingDiv) loadingDiv.style.display = 'none';
            if (containerDiv) containerDiv.style.display = 'block';

            // Clear existing table rows
            tableBody.innerHTML = '';

            // Clear selected files
            StateManager.setState('files.selected', new Set());

            // Reset "Select All" checkbox
            const selectAllCheckbox = DomHelpers.getElement('selectAllFiles');
            if (selectAllCheckbox) {
                selectAllCheckbox.checked = false;
            }

            this.updateFileSelectionButtons();

            if (data.files.length === 0) {
                if (emptyDiv) emptyDiv.style.display = 'block';
                const fileTable = containerDiv.querySelector('.file-table');
                if (fileTable) {
                    fileTable.style.display = 'none';
                }
            } else {
                if (emptyDiv) emptyDiv.style.display = 'none';
                const fileTable = containerDiv.querySelector('.file-table');
                if (fileTable) {
                    fileTable.style.display = 'table';
                }

                // Populate table with files
                data.files.forEach(file => {
                    const row = this.createFileRow(file);
                    tableBody.appendChild(row);
                });
            }

            // Update totals
            DomHelpers.setText('totalFileCount', data.total_files);
            DomHelpers.setText('totalFileSize', `${data.total_size_mb} MB`);

            // Store in state
            StateManager.setState('files.managed', data.files);

        } catch (error) {
            if (loadingDiv) loadingDiv.style.display = 'none';
            MessageLogger.showMessage(`Error loading file list: ${error.message}`, 'error');
        }
    },

    /**
     * Create file row element
     * @param {Object} file - File data object
     * @returns {HTMLElement} Table row element
     */
    createFileRow(file) {
        const row = document.createElement('tr');

        // Format date
        const modifiedDate = new Date(file.modified_date);
        const formattedDate = modifiedDate.toLocaleString();

        // Determine file icon
        const fileIcon = file.file_type === 'epub' ? '📚' :
                        file.file_type === 'srt' ? '🎬' :
                        file.file_type === 'txt' ? '📄' :
                        file.file_type === 'opus' || file.file_type === 'mp3' ? '🎵' : '📎';

        // Check if file supports TTS (text-based files only, not audio files)
        const supportsTTS = ['epub', 'txt', 'srt'].includes(file.file_type);

        row.innerHTML = `
            <td>
                <input type="checkbox" class="file-checkbox" data-filename="${DomHelpers.escapeHtml(file.filename)}">
            </td>
            <td>
                <span class="clickable-filename" data-filename="${DomHelpers.escapeHtml(file.filename)}" data-action="open" title="Click to open file">
                    ${fileIcon} ${DomHelpers.escapeHtml(file.filename)}
                </span>
            </td>
            <td>${file.file_type.toUpperCase()}</td>
            <td>${file.size_mb} MB</td>
            <td>${formattedDate}</td>
            <td style="text-align: center;">
                ${supportsTTS ? `<button class="file-action-btn audiobook" data-filename="${DomHelpers.escapeHtml(file.filename)}" data-filepath="${DomHelpers.escapeHtml(file.file_path)}" data-action="audiobook" title="Generate Audiobook (TTS)">
                    🎧
                </button>` : ''}
                <button class="file-action-btn download" data-filename="${DomHelpers.escapeHtml(file.filename)}" data-action="download" title="Download">
                    📥
                </button>
                <button class="file-action-btn delete" data-filename="${DomHelpers.escapeHtml(file.filename)}" data-action="delete" title="Delete">
                    🗑️
                </button>
            </td>
        `;

        // Add event listeners
        const checkbox = row.querySelector('.file-checkbox');
        if (checkbox) {
            checkbox.addEventListener('change', () => this.toggleFileSelection(file.filename));
        }

        const openLink = row.querySelector('[data-action="open"]');
        if (openLink) {
            openLink.addEventListener('click', () => this.openLocalFile(file.filename));
        }

        const downloadBtn = row.querySelector('[data-action="download"]');
        if (downloadBtn) {
            downloadBtn.addEventListener('click', () => this.downloadSingleFile(file.filename));
        }

        const deleteBtn = row.querySelector('[data-action="delete"]');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', () => this.deleteSingleFile(file.filename));
        }

        const audiobookBtn = row.querySelector('[data-action="audiobook"]');
        if (audiobookBtn) {
            const filepath = audiobookBtn.getAttribute('data-filepath');
            audiobookBtn.addEventListener('click', () => window.createAudiobook(file.filename, filepath));
        }

        return row;
    },

    /**
     * Toggle file selection
     * @param {string} filename - Filename to toggle
     */
    toggleFileSelection(filename) {
        const selectedFiles = StateManager.getState('files.selected');

        if (selectedFiles.has(filename)) {
            selectedFiles.delete(filename);
        } else {
            selectedFiles.add(filename);
        }

        StateManager.setState('files.selected', selectedFiles);
        this.updateFileSelectionButtons();
    },

    /**
     * Select all files
     */
    selectAllFiles() {
        const checkboxes = DomHelpers.getElements('.file-checkbox');
        const selectedFiles = new Set();

        checkboxes.forEach(checkbox => {
            checkbox.checked = true;
            const filename = checkbox.getAttribute('data-filename');
            selectedFiles.add(filename);
        });

        StateManager.setState('files.selected', selectedFiles);
        this.updateFileSelectionButtons();
    },

    /**
     * Deselect all files
     */
    deselectAllFiles() {
        const checkboxes = DomHelpers.getElements('.file-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = false;
        });

        StateManager.setState('files.selected', new Set());
        this.updateFileSelectionButtons();
    },

    /**
     * Toggle select all
     */
    toggleSelectAll() {
        const checkboxes = DomHelpers.getElements('.file-checkbox');
        const selectAllFiles = DomHelpers.getElement('selectAllFiles');

        // Use the Select All checkbox state
        const isChecked = selectAllFiles.checked;

        if (isChecked) {
            this.selectAllFiles();
        } else {
            this.deselectAllFiles();
        }
    },

    /**
     * Update file selection button states
     */
    updateFileSelectionButtons() {
        const selectedFiles = StateManager.getState('files.selected');
        const hasSelection = selectedFiles.size > 0;

        // Update button states
        DomHelpers.setDisabled('batchDownloadBtn', !hasSelection);
        DomHelpers.setDisabled('batchDeleteBtn', !hasSelection);

        // Update "Select All" checkbox state based on actual selection
        const checkboxes = DomHelpers.getElements('.file-checkbox');
        const selectAllCheckbox = DomHelpers.getElement('selectAllFiles');
        if (selectAllCheckbox && checkboxes.length > 0) {
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
            selectAllCheckbox.checked = allChecked;
        }

        // Update button text with count
        if (hasSelection) {
            DomHelpers.setText('batchDownloadBtn', `📥 Download Selected (${selectedFiles.size})`);
            DomHelpers.setText('batchDeleteBtn', `🗑️ Delete Selected (${selectedFiles.size})`);
        } else {
            DomHelpers.setText('batchDownloadBtn', `📥 Download Selected`);
            DomHelpers.setText('batchDeleteBtn', `🗑️ Delete Selected`);
        }
    },

    /**
     * Download a single file
     * @param {string} filename - Filename to download
     */
    async downloadSingleFile(filename) {
        window.location.href = ApiClient.getFileDownloadUrl(filename);
    },

    /**
     * Delete a single file
     * @param {string} filename - Filename to delete
     */
    async deleteSingleFile(filename) {
        if (!confirm(`Are you sure you want to delete "${filename}"?`)) {
            return;
        }

        try {
            const data = await ApiClient.deleteFile(filename);
            MessageLogger.showMessage(data.message, 'success');
            this.refreshFileList();
        } catch (error) {
            MessageLogger.showMessage(`Error deleting file: ${error.message}`, 'error');
        }
    },

    /**
     * Download selected files as ZIP
     */
    async downloadSelectedFiles() {
        const selectedFiles = StateManager.getState('files.selected');

        if (selectedFiles.size === 0) {
            MessageLogger.showMessage('No files selected for download', 'error');
            return;
        }

        try {
            const response = await fetch(`${ApiClient.getBaseUrl()}/api/files/batch/download`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    filenames: Array.from(selectedFiles)
                })
            });

            if (response.ok) {
                // Download the zip file
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = `translated_files_${new Date().getTime()}.zip`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);

                MessageLogger.showMessage(`Downloaded ${selectedFiles.size} files as zip`, 'success');
            } else {
                const data = await response.json();
                MessageLogger.showMessage(data.error || 'Failed to download files', 'error');
            }
        } catch (error) {
            MessageLogger.showMessage(`Error downloading files: ${error.message}`, 'error');
        }
    },

    /**
     * Delete selected files
     */
    async deleteSelectedFiles() {
        const selectedFiles = StateManager.getState('files.selected');

        if (selectedFiles.size === 0) {
            MessageLogger.showMessage('No files selected for deletion', 'error');
            return;
        }

        if (!confirm(`Are you sure you want to delete ${selectedFiles.size} file(s)?`)) {
            return;
        }

        try {
            const response = await fetch(`${ApiClient.getBaseUrl()}/api/files/batch/delete`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    filenames: Array.from(selectedFiles)
                })
            });

            const data = await response.json();

            if (response.ok) {
                let message = `Deleted ${data.total_deleted} file(s)`;
                if (data.failed.length > 0) {
                    message += `. Failed to delete ${data.failed.length} file(s)`;
                }
                MessageLogger.showMessage(message, data.failed.length > 0 ? 'info' : 'success');
                this.refreshFileList();
            } else {
                MessageLogger.showMessage(data.error || 'Failed to delete files', 'error');
            }
        } catch (error) {
            MessageLogger.showMessage(`Error deleting files: ${error.message}`, 'error');
        }
    },

    /**
     * Open file locally (using system default application)
     * @param {string} filename - Filename to open
     */
    async openLocalFile(filename) {
        try {
            const data = await ApiClient.openLocalFile(filename);
            MessageLogger.showMessage(`File opened: ${filename}`, 'success');
            MessageLogger.addLog(`📂 Opened file: ${filename}`);
        } catch (error) {
            MessageLogger.showMessage(`Error opening file: ${error.message}`, 'error');
        }
    }
};

// Expose functions for onclick handlers in HTML
window.toggleFileSelection = (filename) => FileManager.toggleFileSelection(filename);
window.downloadSingleFile = (filename) => FileManager.downloadSingleFile(filename);
window.deleteSingleFile = (filename) => FileManager.deleteSingleFile(filename);
window.openLocalFile = (filename) => FileManager.openLocalFile(filename);
