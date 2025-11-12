let filesToProcess = [];
let currentProcessingJob = null;
let isBatchActive = false;

// Global state for active translations tracking
let activeTranslationsState = {
    hasActive: false,
    activeJobs: []
};

const API_BASE_URL = window.location.origin;
const socket = io();

socket.on('connect', () => {
    console.log('WebSocket connected to:', API_BASE_URL);
    addLog('✅ WebSocket connection to server established.');
});
socket.on('disconnect', () => {
    console.log('WebSocket disconnected.');
    addLog('❌ WebSocket connection lost.');
    if (isBatchActive && currentProcessingJob) {
        showMessage('Connection lost. Translation may continue on server. Refresh page to check status.', 'warning');
        // Don't reset UI immediately - translation might still be running on server
        // User can manually refresh to check actual state
    }
});

socket.on('translation_update', (data) => {
    if (currentProcessingJob && data.translation_id === currentProcessingJob.translationId) {
        handleTranslationUpdate(data);

        // Handle structured log entries for translation preview
        if (data.log_entry && data.log_entry.type === 'llm_response' && data.log_entry.data && data.log_entry.data.response) {
            updateTranslationPreview(data.log_entry.data.response);
        }
    }
});

socket.on('file_list_changed', (data) => {
    console.log('File list changed:', data.reason, '-', data.filename);
    // Automatically refresh the file management list
    refreshFileList();
});

socket.on('checkpoint_created', (data) => {
    console.log('Checkpoint created:', data);
    addLog(`⏸️ ${data.message || 'Checkpoint created'}`);
    // Immediately show and refresh the resumable jobs UI
    loadResumableJobs();
});

/**
 * Check and update active translations state
 * This function is called whenever translation state might have changed
 */
async function updateActiveTranslationsState() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/translations`);
        const data = await response.json();
        const activeJobs = (data.translations || []).filter(
            t => t.status === 'running' || t.status === 'queued'
        );

        const wasActive = activeTranslationsState.hasActive;
        activeTranslationsState.hasActive = activeJobs.length > 0;
        activeTranslationsState.activeJobs = activeJobs;

        // If state changed, update UI
        if (wasActive !== activeTranslationsState.hasActive) {
            console.log('Active translation state changed:', activeTranslationsState.hasActive);
            updateResumeButtonsState();
        }

        return activeTranslationsState;
    } catch (error) {
        console.error('Error updating active translations state:', error);
        return activeTranslationsState;
    }
}

/**
 * Update the state of all resume buttons based on active translations
 */
function updateResumeButtonsState() {
    const resumeButtons = document.querySelectorAll('button[onclick^="resumeJob"]');
    const hasActive = activeTranslationsState.hasActive;

    resumeButtons.forEach(button => {
        if (hasActive) {
            button.disabled = true;
            button.style.opacity = '0.5';
            button.style.cursor = 'not-allowed';
            button.title = '⚠️ Impossible: une traduction est déjà en cours';
        } else {
            button.disabled = false;
            button.style.opacity = '1';
            button.style.cursor = 'pointer';
            button.title = 'Reprendre cette traduction';
        }
    });

    // Update warning banner
    updateResumableJobsWarningBanner();
}

/**
 * Update or create the warning banner in resumable jobs section
 */
function updateResumableJobsWarningBanner() {
    const listContainer = document.getElementById('resumableJobsList');
    if (!listContainer) return;

    const existingBanner = listContainer.querySelector('.active-translation-warning');
    const hasActive = activeTranslationsState.hasActive;

    if (hasActive) {
        const activeNames = activeTranslationsState.activeJobs.map(t => t.output_filename || 'Unknown').join(', ');
        const bannerHtml = `
            <div class="active-translation-warning" style="background: #fef3c7; border: 1px solid #f59e0b; padding: 12px; margin-bottom: 15px; border-radius: 6px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 20px;">⚠️</span>
                    <div style="flex: 1;">
                        <strong style="color: #92400e;">Traduction active en cours</strong>
                        <p style="margin: 5px 0 0 0; font-size: 13px; color: #78350f;">
                            Les reprises sont désactivées. Traduction(s) active(s): ${escapeHtml(activeNames)}
                        </p>
                    </div>
                </div>
            </div>
        `;

        if (existingBanner) {
            existingBanner.outerHTML = bannerHtml;
        } else {
            // Insert at the beginning of the container
            listContainer.insertAdjacentHTML('afterbegin', bannerHtml);
        }
    } else if (existingBanner) {
        // Remove banner if no active translations
        existingBanner.remove();
    }
}

function updateFileStatusInList(fileName, newStatus, translationId = null) {
    const fileListItem = document.querySelector(`#fileListContainer li[data-filename="${fileName}"] .file-status`);
    if (fileListItem) {
        fileListItem.textContent = `(${newStatus})`;
    }
    const fileObj = filesToProcess.find(f => f.name === fileName);
    if (fileObj) {
        fileObj.status = newStatus;
        if (translationId) fileObj.translationId = translationId;
    }
}

function finishCurrentFileTranslationUI(statusMessage, messageType, resultData) {
    if (!currentProcessingJob) return;

    const currentFile = currentProcessingJob.fileRef;
    currentFile.status = resultData.status || 'unknown_error';
    currentFile.result = resultData.result;

    // Output section removed

    showMessage(statusMessage, messageType);
    updateFileStatusInList(currentFile.name, resultData.status === 'completed' ? 'Completed' : (resultData.status === 'interrupted' ? 'Interrupted' : 'Error'));

    // Remove file from filesToProcess if translation completed or was interrupted
    if (resultData.status === 'completed' || resultData.status === 'interrupted') {
        removeFileFromProcessingList(currentFile.name);
    }

    currentProcessingJob = null;

    // Only continue to next file if translation completed successfully (NOT if interrupted)
    if (resultData.status === 'completed') {
        processNextFileInQueue();
    } else if (resultData.status === 'interrupted') {
        // User stopped the translation - stop the entire batch
        addLog('🛑 Batch processing stopped by user.');
        resetUIToIdle();
    } else {
        // Error case - continue to next file
        processNextFileInQueue();
    }
}

function handleTranslationUpdate(data) {
    if (!currentProcessingJob || data.translation_id !== currentProcessingJob.translationId) {
        // Received update for a job that's not current - possible state inconsistency
        if (data.translation_id && !currentProcessingJob) {
            console.warn('Received translation update but no current job. Possible state desync.');
            // Check if we should reset UI
            if (data.status === 'completed' || data.status === 'error' || data.status === 'interrupted') {
                console.log('Translation finished, ensuring UI is in idle state');
                resetUIToIdle();
            }
        }
        return;
    }

    const currentFile = currentProcessingJob.fileRef;

    if (data.log) addLog(`[${currentFile.name}] ${data.log}`);
    if (data.progress !== undefined) updateProgress(data.progress);

    if (data.stats) {
        if (currentFile.fileType === 'epub') {
            document.getElementById('statsGrid').style.display = 'none';
        } else if (currentFile.fileType === 'srt') {
            document.getElementById('statsGrid').style.display = '';
            document.getElementById('totalChunks').textContent = data.stats.total_subtitles || '0';
            document.getElementById('completedChunks').textContent = data.stats.completed_subtitles || '0';
            document.getElementById('failedChunks').textContent = data.stats.failed_subtitles || '0';
        } else {
            document.getElementById('statsGrid').style.display = '';
            document.getElementById('totalChunks').textContent = data.stats.total_chunks || '0';
            document.getElementById('completedChunks').textContent = data.stats.completed_chunks || '0';
            document.getElementById('failedChunks').textContent = data.stats.failed_chunks || '0';
        }
        
        if (data.stats.elapsed_time !== undefined) {
            document.getElementById('elapsedTime').textContent = data.stats.elapsed_time.toFixed(1) + 's';
        }
    }

    if (data.status === 'completed') {
        finishCurrentFileTranslationUI(`✅ ${currentFile.name}: Translation completed!`, 'success', data);
        // Update active translations state when translation completes
        updateActiveTranslationsState();
    } else if (data.status === 'interrupted') {
        finishCurrentFileTranslationUI(`ℹ️ ${currentFile.name}: Translation interrupted.`, 'info', data);
        // Update active translations state when translation is interrupted
        updateActiveTranslationsState();
    } else if (data.status === 'error') {
        finishCurrentFileTranslationUI(`❌ ${currentFile.name}: Error - ${data.error || 'Unknown error.'}`, 'error', data);
        // Update active translations state when translation errors
        updateActiveTranslationsState();
    } else if (data.status === 'running') {
         document.getElementById('progressSection').classList.remove('hidden');
         document.getElementById('currentFileProgressTitle').textContent = `📊 Translating: ${currentFile.name}`;
         
         if (currentFile.fileType === 'epub') {
             showMessage(`Translating EPUB file: ${currentFile.name}... This may take some time.`, 'info');
             document.getElementById('statsGrid').style.display = 'none';
         } else if (currentFile.fileType === 'srt') {
             showMessage(`Translating SRT subtitle file: ${currentFile.name}...`, 'info');
             document.getElementById('statsGrid').style.display = '';
         } else {
             showMessage(`Translation in progress for ${currentFile.name}...`, 'info');
             document.getElementById('statsGrid').style.display = '';
         }
         
         updateFileStatusInList(currentFile.name, 'Processing');
    }
}

// Prevent accidental page closure during active translation
window.addEventListener('beforeunload', (e) => {
    if (isBatchActive && currentProcessingJob) {
        // Modern browsers require both preventDefault and returnValue
        const confirmationMessage = 'Une traduction est en cours. Êtes-vous sûr de vouloir quitter cette page ?';

        e.preventDefault();
        e.returnValue = confirmationMessage;

        return confirmationMessage;
    }
});

// Handle actual page unload - interrupt translation if user confirms closure
window.addEventListener('pagehide', (e) => {
    // If there's an active translation, interrupt it before page closes
    if (isBatchActive && currentProcessingJob && currentProcessingJob.translationId) {
        // Use sendBeacon for reliable delivery even during page unload
        const interruptUrl = `${API_BASE_URL}/api/translation/${currentProcessingJob.translationId}/interrupt`;

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

/**
 * Periodic state consistency check
 * Runs every 10 seconds to detect and fix UI state inconsistencies
 */
async function checkStateConsistency() {
    // Only check if we think there's an active batch
    if (!isBatchActive || !currentProcessingJob) {
        return;
    }

    const tidToCheck = currentProcessingJob.translationId;

    try {
        const response = await fetch(`${API_BASE_URL}/api/translation/${tidToCheck}`);
        if (!response.ok) {
            // Job doesn't exist anymore on server
            console.warn(`Job ${tidToCheck} not found on server. Resetting UI.`);
            addLog(`⚠️ Translation job no longer exists on server. Resetting UI.`);
            resetUIToIdle();
            return;
        }

        const data = await response.json();
        const serverStatus = data.status;

        // Check if server says the job is done but UI still shows it as active
        if (serverStatus === 'completed' || serverStatus === 'error' || serverStatus === 'interrupted') {
            console.warn(`Server reports job ${tidToCheck} is ${serverStatus}, but UI still shows active. Syncing state.`);
            addLog(`🔄 Detected state desync: job ${serverStatus} on server but UI still active. Syncing...`);

            // Trigger the appropriate UI update
            handleTranslationUpdate({
                translation_id: tidToCheck,
                status: serverStatus,
                result: data.result_preview || `[${serverStatus}]`,
                error: data.error
            });
        }
    } catch (error) {
        console.error('Error checking state consistency:', error);
        // Don't reset on network errors - could just be temporary
    }
}

// Start periodic state consistency checks (every 10 seconds)
setInterval(checkStateConsistency, 10000);

window.addEventListener('load', async () => {
    // Set up event listener for provider change
    document.getElementById('llmProvider').addEventListener('change', toggleProviderSettings);

    try {
        const response = await fetch(`${API_BASE_URL}/api/health`);
        if (!response.ok) throw new Error('Server health check failed');
        const healthData = await response.json();
        addLog('Server health check OK.');

        if (healthData.supported_formats) {
            addLog(`Supported file formats: ${healthData.supported_formats.join(', ')}`);
        }

        // Initialize provider settings first
        toggleProviderSettings();

        const configResponse = await fetch(`${API_BASE_URL}/api/config`);
        if (configResponse.ok) {
            const defaultConfig = await configResponse.json();
            document.getElementById('apiEndpoint').value = defaultConfig.api_endpoint || 'http://localhost:11434/api/generate';
            document.getElementById('chunkSize').value = defaultConfig.chunk_size || 25;
            document.getElementById('timeout').value = defaultConfig.timeout || 180;
            document.getElementById('contextWindow').value = defaultConfig.context_window || 4096;
            document.getElementById('maxAttempts').value = defaultConfig.max_attempts || 2;
            document.getElementById('retryDelay').value = defaultConfig.retry_delay || 2;
            document.getElementById('outputFilenamePattern').value = "translated_{originalName}.{ext}";

            // Load Gemini API key from environment if available
            if (defaultConfig.gemini_api_key) {
                document.getElementById('geminiApiKey').value = defaultConfig.gemini_api_key;
            }
        }
    } catch (error) {
        showMessage(`⚠️ Server unavailable at ${API_BASE_URL}. Ensure Python server is running. ${error.message}`, 'error');
        addLog(`❌ Failed to connect to server or load config: ${error.message}`);
    }
});

function toggleProviderSettings() {
    const provider = document.getElementById('llmProvider').value;
    const ollamaSettings = document.getElementById('ollamaSettings');
    const geminiSettings = document.getElementById('geminiSettings');
    const openaiSettings = document.getElementById('openaiSettings');
    const modelSelect = document.getElementById('model');

    // console.log(`[DEBUG] toggleProviderSettings called with provider: ${provider}`);

    if (provider === 'ollama') {
        ollamaSettings.style.display = 'block';
        geminiSettings.style.display = 'none';
        openaiSettings.style.display = 'none';
        loadAvailableModels();
    } else if (provider === 'gemini') {
        ollamaSettings.style.display = 'none';
        geminiSettings.style.display = 'block';
        openaiSettings.style.display = 'none';
        loadGeminiModels();
    } else if (provider === 'openai') {
        ollamaSettings.style.display = 'none';
        geminiSettings.style.display = 'none';
        openaiSettings.style.display = 'block';
        loadOpenAIModels();
    }
}

function refreshModels() {
    const provider = document.getElementById('llmProvider').value;
    if (provider === 'ollama') {
        loadAvailableModels();
    } else if (provider === 'gemini') {
        loadGeminiModels();
    } else if (provider === 'openai') {
        loadOpenAIModels();
    }
}

// Track the current request to prevent race conditions
let currentModelLoadRequest = null;

async function loadGeminiModels() {
    const modelSelect = document.getElementById('model');
    modelSelect.innerHTML = '<option value="">Loading Gemini models...</option>';

    try {
        const apiKey = document.getElementById('geminiApiKey').value.trim();
        const response = await fetch(`${API_BASE_URL}/api/models?provider=gemini&api_key=${encodeURIComponent(apiKey)}`);

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.error || `HTTP error ${response.status}`);
        }

        const data = await response.json();

        modelSelect.innerHTML = '';

        if (data.models && data.models.length > 0) {
            showMessage('', '');

            data.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.name;
                option.textContent = `${model.displayName || model.name} - ${model.description || ''}`;
                option.title = `Input: ${model.inputTokenLimit || 'N/A'} tokens, Output: ${model.outputTokenLimit || 'N/A'} tokens`;
                if (model.name === data.default) option.selected = true;
                modelSelect.appendChild(option);
            });

            addLog(`✅ ${data.count} Gemini model(s) loaded (excluding thinking models)`);
            checkModelSizeAndShowRecommendation();
        } else {
            const errorMessage = data.error || 'No Gemini models available.';
            showMessage(`⚠️ ${errorMessage}`, 'error');
            modelSelect.innerHTML = '<option value="">No models available</option>';
            addLog(`⚠️ No Gemini models available`);
        }
    } catch (error) {
        showMessage(`❌ Error fetching Gemini models: ${error.message}`, 'error');
        addLog(`❌ Failed to retrieve Gemini model list: ${error.message}`);
        modelSelect.innerHTML = '<option value="">Error loading models</option>';
    }
}

async function loadOpenAIModels() {
    const modelSelect = document.getElementById('model');
    modelSelect.innerHTML = '';

    // Common OpenAI models
    const commonModels = [
        { value: 'gpt-4o', label: 'GPT-4o (Latest)' },
        { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
        { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
        { value: 'gpt-4', label: 'GPT-4' },
        { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' }
    ];

    commonModels.forEach(model => {
        const option = document.createElement('option');
        option.value = model.value;
        option.textContent = model.label;
        modelSelect.appendChild(option);
    });

    addLog(`✅ OpenAI models loaded (common models)`);
    checkModelSizeAndShowRecommendation();
}

async function loadAvailableModels() {
    const provider = document.getElementById('llmProvider').value;
    if (provider === 'gemini' || provider === 'openai') {
        return; // Gemini and OpenAI models are loaded separately
    }
    
    // Cancel any pending request
    if (currentModelLoadRequest) {
        currentModelLoadRequest.cancelled = true;
    }
    
    // Create a new request tracker
    const thisRequest = { cancelled: false };
    currentModelLoadRequest = thisRequest;
    
    const modelSelect = document.getElementById('model');
    modelSelect.innerHTML = '<option value="">Loading models...</option>';
    try {
        const currentApiEp = document.getElementById('apiEndpoint').value;
        const response = await fetch(`${API_BASE_URL}/api/models?api_endpoint=${encodeURIComponent(currentApiEp)}`);
        
        // Check if this request was cancelled while in flight
        if (thisRequest.cancelled) {
            console.log('Model load request was cancelled');
            return;
        }
        
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.error || `HTTP error ${response.status}`);
        }
        const data = await response.json();
        
        // Double-check the provider hasn't changed and request wasn't cancelled
        if (thisRequest.cancelled) {
            return;
        }
        const currentProvider = document.getElementById('llmProvider').value;
        if (currentProvider !== 'ollama') {
            console.log('Provider changed during model load, ignoring Ollama response');
            return;
        }
        
        modelSelect.innerHTML = '';

        if (data.models && data.models.length > 0) {
            showMessage('', '');

            data.models.forEach(modelName => {
                const option = document.createElement('option');
                option.value = modelName; option.textContent = modelName;
                if (modelName === data.default) option.selected = true;
                modelSelect.appendChild(option);
            });
            addLog(`✅ ${data.count} LLM model(s) loaded. Default: ${data.default}`);
            checkModelSizeAndShowRecommendation();
        } else {
            const errorMessage = data.error || 'No LLM models available. Ensure Ollama is running and accessible.';
            showMessage(`⚠️ ${errorMessage}`, 'error');

            modelSelect.innerHTML = '<option value="">Check connection !</option>';
            addLog(`⚠️ No models available from Ollama at ${currentApiEp}`);
        }
    } catch (error) {
        // Check if cancelled
        if (!thisRequest.cancelled) {
            showMessage(`❌ Error fetching models: ${error.message}`, 'error');
            addLog(`❌ Failed to retrieve model list: ${error.message}`);
            modelSelect.innerHTML = '<option value="">Error loading models - Check Ollama</option>';
        }
    } finally {
        // Clear the request tracker if it's still ours
        if (currentModelLoadRequest === thisRequest) {
            currentModelLoadRequest = null;
        }
    }
}

const fileUploadArea = document.getElementById('fileUpload');
fileUploadArea.addEventListener('dragover', (e) => { e.preventDefault(); fileUploadArea.classList.add('dragging'); });
fileUploadArea.addEventListener('dragleave', () => fileUploadArea.classList.remove('dragging'));
fileUploadArea.addEventListener('drop', (e) => {
    e.preventDefault(); fileUploadArea.classList.remove('dragging');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        Array.from(files).forEach(file => {
            addFileToList(file); 
        });
        updateFileDisplay();
    }
});

function toggleAdvanced() {
    const settings = document.getElementById('advancedSettings');
    document.getElementById('advancedIcon').textContent = settings.classList.toggle('hidden') ? '▼' : '▲';
}
function checkCustomSourceLanguage(selectElement) {
    const customLangInput = document.getElementById('customSourceLang');
    customLangInput.style.display = (selectElement.value === 'Other') ? 'block' : 'none';
    if (selectElement.value === 'Other') customLangInput.focus();
}
function checkCustomTargetLanguage(selectElement) {
    const customLangInput = document.getElementById('customTargetLang');
    customLangInput.style.display = (selectElement.value === 'Other') ? 'block' : 'none';
    if (selectElement.value === 'Other') customLangInput.focus();
}

function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
        Array.from(files).forEach(file => {
            addFileToList(file); 
        });
        updateFileDisplay();
    }
     document.getElementById('fileInput').value = '';
}

async function addFileToList(file) {
    if (filesToProcess.find(f => f.name === file.name)) {
        showMessage(`File '${file.name}' is already in the list.`, 'info');
        return;
    }
    
    const fileExtension = file.name.split('.').pop().toLowerCase();
    const originalNameWithoutExt = file.name.replace(/\.[^/.]+$/, "");
    const outputPattern = document.getElementById('outputFilenamePattern').value || "translated_{originalName}.{ext}";
    
    let processingFileType = 'txt'; 
    if (fileExtension === 'epub') {
        processingFileType = 'epub';
    } else if (fileExtension === 'srt') {
        processingFileType = 'srt';
    }
    
    const outputFilename = outputPattern
        .replace("{originalName}", originalNameWithoutExt)
        .replace("{ext}", fileExtension); 

    showMessage(`Uploading file: ${file.name}...`, 'info');
        
    const formData = new FormData();
    formData.append('file', file);
        
    try {
        const response = await fetch(`${API_BASE_URL}/api/upload`, {
            method: 'POST',
            body: formData
        });
            
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || `Upload failed: ${response.statusText}`);
        }
            
        const uploadResult = await response.json();
            
        filesToProcess.push({
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
        });
            
        showMessage(`File '${file.name}' (${uploadResult.file_type}) uploaded. Path: ${uploadResult.file_path}`, 'success');
        updateFileDisplay();
            
    } catch (error) {
        showMessage(`Failed to upload file '${file.name}': ${error.message}`, 'error');
    }
}

function updateFileDisplay() {
    const fileListContainer = document.getElementById('fileListContainer');
    fileListContainer.innerHTML = '';

    if (filesToProcess.length > 0) {
        filesToProcess.forEach(file => {
            const li = document.createElement('li');
            li.setAttribute('data-filename', file.name);
            
            const fileIcon = file.fileType === 'epub' ? '📚' : (file.fileType === 'srt' ? '🎬' : '📄');
            li.textContent = `${fileIcon} ${file.name} (${(file.size / 1024).toFixed(2)} KB) `;
            
            const statusSpan = document.createElement('span');
            statusSpan.className = 'file-status';
            statusSpan.textContent = `(${file.status})`;
            li.appendChild(statusSpan);
            fileListContainer.appendChild(li);
        });
        document.getElementById('fileInfo').classList.remove('hidden');
        document.getElementById('translateBtn').disabled = isBatchActive;
    } else {
        document.getElementById('fileInfo').classList.add('hidden');
        document.getElementById('translateBtn').disabled = true;
    }
}

function removeFileFromProcessingList(filename) {
    // Remove file from filesToProcess array
    const fileIndex = filesToProcess.findIndex(f => f.name === filename);
    if (fileIndex !== -1) {
        filesToProcess.splice(fileIndex, 1);
        updateFileDisplay();
        addLog(`🗑️ Removed ${filename} from file list (source file cleaned up)`);
    }
}

async function resetFiles() {
    // First, interrupt current translation if active
    if (currentProcessingJob && currentProcessingJob.translationId && isBatchActive) {
        addLog("🛑 Interrupting current translation before clearing files...");
        try {
            await fetch(`/api/translation/${currentProcessingJob.translationId}/interrupt`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
        } catch (error) {
            console.error('Error interrupting translation:', error);
        }
    }

    // Collect file paths to delete from server
    const uploadedFilePaths = filesToProcess
        .filter(file => file.filePath)
        .map(file => file.filePath);

    // Clear client-side arrays and state
    filesToProcess = [];
    currentProcessingJob = null;
    isBatchActive = false;

    document.getElementById('fileInput').value = '';
    updateFileDisplay();

    document.getElementById('progressSection').classList.add('hidden');
    // Don't clear the log automatically anymore
    // document.getElementById('logContainer').innerHTML = '';
    document.getElementById('translateBtn').innerHTML = '▶️ Start Translation Batch';
    document.getElementById('translateBtn').disabled = true;
    document.getElementById('interruptBtn').classList.add('hidden');
    document.getElementById('interruptBtn').disabled = false;

    document.getElementById('customSourceLang').style.display = 'none';
    document.getElementById('customTargetLang').style.display = 'none';
    document.getElementById('sourceLang').selectedIndex = 0;
    document.getElementById('targetLang').selectedIndex = 0;
    document.getElementById('statsGrid').style.display = '';
    updateProgress(0);
    showMessage('', '');
    
    // Delete uploaded files from server
    if (uploadedFilePaths.length > 0) {
        addLog(`🗑️ Deleting ${uploadedFilePaths.length} uploaded file(s) from server...`);
        try {
            const response = await fetch('/api/uploads/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_paths: uploadedFilePaths })
            });
            
            if (response.ok) {
                const result = await response.json();
                addLog(`✅ Successfully deleted ${result.total_deleted} uploaded file(s).`);
                if (result.failed && result.failed.length > 0) {
                    addLog(`⚠️ Failed to delete ${result.failed.length} file(s).`);
                }
            } else {
                addLog("⚠️ Failed to delete some uploaded files from server.");
            }
        } catch (error) {
            console.error('Error deleting uploaded files:', error);
            addLog("⚠️ Error occurred while deleting uploaded files.");
        }
    }
    
    addLog("Form and file list reset.");
}

function showMessage(text, type) {
    const messagesDiv = document.getElementById('messages');
    messagesDiv.innerHTML = text ? `<div class="message ${type}">${text}</div>` : '';
}
function updateTranslationPreview(response) {
    const lastTranslationPreview = document.getElementById('lastTranslationPreview');

    // Extract text between <TRANSLATION> tags from the response
    const translateMatch = response.match(/<TRANSLATION>([\s\S]*?)<\/TRANSLATION>/);
    if (translateMatch) {
        let translatedText = translateMatch[1].trim();

        // Remove placeholder tags (⟦TAG0⟧, ⟦TAG1⟧, etc.) for cleaner preview
        translatedText = translatedText.replace(/⟦TAG\d+⟧/g, '');

        // Update the last translation preview section with just the translated text
        lastTranslationPreview.innerHTML = `<div style="background: #ffffff; border-left: 3px solid #22c55e; padding: 15px; color: #000000; white-space: pre-wrap; line-height: 1.6;">${escapeHtml(translatedText)}</div>`;
    }
}

function addLog(message) {
    const logContainer = document.getElementById('logContainer');
    const timestamp = new Date().toLocaleTimeString();

    // Filter out technical/verbose messages - only show important logs and errors
    const shouldSkip =
        message.includes('LLM Request') ||
        message.includes('LLM Response') ||
        message.includes('🔍 Input file path:') ||
        message.includes('🔍 Resolved path:') ||
        message.includes('🔍 Parent directory:') ||
        message.includes('📋 Path parts:') ||
        message.includes('📋 Parent directory name:') ||
        message.includes('📋 Expected uploads directory:') ||
        message.includes('🔍 File is confirmed') ||
        message.includes('🔍 File is NOT in uploads') ||
        message.includes('🗑️ Cleaned up uploaded source file:') ||
        message.includes('ℹ️ Skipped cleanup') ||
        message.includes('🧹 Starting cleanup check') ||
        message.includes('📁 File path in config:') ||
        message.includes('🔍 Debug -');

    if (shouldSkip) {
        return; // Don't add this message to the log
    }

    // Add to activity log
    logContainer.innerHTML += `<div class="log-entry">
        <span class="log-timestamp">[${timestamp}]</span> ${message}
    </div>`;

    logContainer.scrollTop = logContainer.scrollHeight;
}

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function earlyValidationFail(message) {
    showMessage(message, 'error');
    isBatchActive = false;
    document.getElementById('translateBtn').disabled = filesToProcess.length === 0;
    document.getElementById('translateBtn').innerHTML = '▶️ Start Translation Batch';
    document.getElementById('interruptBtn').classList.add('hidden');
    return false;
}

async function startBatchTranslation() {
    if (isBatchActive || filesToProcess.length === 0) return;

    let sourceLanguageVal = document.getElementById('sourceLang').value;
    if (sourceLanguageVal === 'Other') {
        sourceLanguageVal = document.getElementById('customSourceLang').value.trim();
        if (!sourceLanguageVal) return earlyValidationFail('Please specify the custom source language for the batch.');
    }
    let targetLanguageVal = document.getElementById('targetLang').value;
    if (targetLanguageVal === 'Other') {
        targetLanguageVal = document.getElementById('customTargetLang').value.trim();
        if (!targetLanguageVal) return earlyValidationFail('Please specify the custom target language for the batch.');
    }
    const selectedModel = document.getElementById('model').value;
    if (!selectedModel) return earlyValidationFail('Please select an LLM model for the batch.');
    const ollamaApiEndpoint = document.getElementById('apiEndpoint').value.trim();
    if (!ollamaApiEndpoint) return earlyValidationFail('Ollama API Endpoint cannot be empty for the batch.');

    isBatchActive = true;

    // Count how many files are queued for processing
    const queuedFilesCount = filesToProcess.filter(f => f.status === 'Queued').length;

    document.getElementById('translateBtn').disabled = true;
    document.getElementById('translateBtn').innerHTML = '⏳ Batch in Progress...';
    document.getElementById('interruptBtn').classList.remove('hidden');
    document.getElementById('interruptBtn').disabled = false;

    // Don't clear the log when starting a new batch
    // document.getElementById('logContainer').innerHTML = '';

    addLog(`🚀 Batch translation started for ${queuedFilesCount} file(s).`);
    showMessage(`Batch of ${queuedFilesCount} file(s) initiated.`, 'info');

    processNextFileInQueue();
}

async function processNextFileInQueue() {
    if (currentProcessingJob) return;

    // Find next file with 'Queued' status in filesToProcess (instead of using translationQueue)
    const fileToTranslate = filesToProcess.find(f => f.status === 'Queued');

    if (!fileToTranslate) {
        // No more queued files - batch completed
        isBatchActive = false;
        document.getElementById('translateBtn').disabled = filesToProcess.length === 0;
        document.getElementById('translateBtn').innerHTML = '▶️ Start Translation Batch';
        document.getElementById('interruptBtn').classList.add('hidden');
        showMessage('✅ Batch translation completed for all files!', 'success');
        addLog('🏁 All files in the batch have been processed.');
        document.getElementById('currentFileProgressTitle').textContent = `📊 Batch Completed`;
        return;
    }

    updateProgress(0);
    ['totalChunks', 'completedChunks', 'failedChunks'].forEach(id => document.getElementById(id).textContent = '0');
    document.getElementById('elapsedTime').textContent = '0s';
    // Don't clear the log when processing next file
    // document.getElementById('logContainer').innerHTML = '';

    // Reset the translation preview for the new file
    const lastTranslationPreview = document.getElementById('lastTranslationPreview');
    lastTranslationPreview.innerHTML = '<div style="color: #6b7280; font-style: italic; padding: 10px;">No translation yet...</div>';

    if (fileToTranslate.fileType === 'epub') {
        document.getElementById('statsGrid').style.display = 'none';
    } else if (fileToTranslate.fileType === 'srt') {
        document.getElementById('statsGrid').style.display = '';
    } else {
        document.getElementById('statsGrid').style.display = '';
    }

    document.getElementById('currentFileProgressTitle').textContent = `📊 Translating: ${fileToTranslate.name}`;
    document.getElementById('progressSection').classList.remove('hidden');
    addLog(`▶️ Starting translation for: ${fileToTranslate.name} (${fileToTranslate.fileType.toUpperCase()})`);
    updateFileStatusInList(fileToTranslate.name, 'Preparing...');

    let sourceLanguageVal = document.getElementById('sourceLang').value;
    if (sourceLanguageVal === 'Other') sourceLanguageVal = document.getElementById('customSourceLang').value.trim();
    let targetLanguageVal = document.getElementById('targetLang').value;
    if (targetLanguageVal === 'Other') targetLanguageVal = document.getElementById('customTargetLang').value.trim();

    const provider = document.getElementById('llmProvider').value;

    // Validate API keys if using Gemini or OpenAI
    if (provider === 'gemini') {
        const geminiApiKey = document.getElementById('geminiApiKey').value.trim();
        if (!geminiApiKey) {
            addLog('❌ Error: Gemini API key is required when using Gemini provider');
            showMessage('Please enter your Gemini API key', 'error');
            updateFileStatusInList(fileToTranslate.name, 'Error: Missing API key');
            currentProcessingJob = null;
            processNextFileInQueue();
            return;
        }
    }

    if (provider === 'openai') {
        const openaiApiKey = document.getElementById('openaiApiKey').value.trim();
        if (!openaiApiKey) {
            addLog('❌ Error: OpenAI API key is required when using OpenAI provider');
            showMessage('Please enter your OpenAI API key', 'error');
            updateFileStatusInList(fileToTranslate.name, 'Error: Missing API key');
            currentProcessingJob = null;
            processNextFileInQueue();
            return;
        }
    }
    
    const config = {
        source_language: sourceLanguageVal,
        target_language: targetLanguageVal,
        model: document.getElementById('model').value,
        llm_api_endpoint: provider === 'openai' ? document.getElementById('openaiEndpoint').value : document.getElementById('apiEndpoint').value,
        llm_provider: provider,
        gemini_api_key: provider === 'gemini' ? document.getElementById('geminiApiKey').value : '',
        openai_api_key: provider === 'openai' ? document.getElementById('openaiApiKey').value : '',
        chunk_size: parseInt(document.getElementById('chunkSize').value),
        timeout: parseInt(document.getElementById('timeout').value),
        context_window: parseInt(document.getElementById('contextWindow').value),
        max_attempts: parseInt(document.getElementById('maxAttempts').value),
        retry_delay: parseInt(document.getElementById('retryDelay').value),
        output_filename: fileToTranslate.outputFilename,
        file_type: fileToTranslate.fileType,
        simple_mode: document.getElementById('simpleMode').checked
    };

    if (fileToTranslate.fileType === 'epub' || fileToTranslate.fileType === 'srt') {
        if (!fileToTranslate.filePath) {
             addLog(`❌ Critical Error: ${fileToTranslate.fileType.toUpperCase()} file ${fileToTranslate.name} has no server path. Upload might have failed silently or logic error.`);
             showMessage(`Cannot process ${fileToTranslate.fileType.toUpperCase()} ${fileToTranslate.name}: server path missing.`, 'error');
             updateFileStatusInList(fileToTranslate.name, 'Path Error');
             currentProcessingJob = null; 
             processNextFileInQueue(); 
             return;
        }
        config.file_path = fileToTranslate.filePath;
    } else { 
        if (fileToTranslate.content) {
            config.text = fileToTranslate.content; 
        } else {
            if (!fileToTranslate.filePath) {
                 addLog(`❌ Critical Error: TXT file ${fileToTranslate.name} has no server path and no direct content. Upload might have failed or logic error.`);
                 showMessage(`Cannot process TXT file ${fileToTranslate.name}: server path or content missing.`, 'error');
                 updateFileStatusInList(fileToTranslate.name, 'Input Error');
                 currentProcessingJob = null;
                 processNextFileInQueue();
                 return;
            }
            config.file_path = fileToTranslate.filePath;
        }
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/translate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || `Server error ${response.status} for ${fileToTranslate.name}.`);
        }
        const data = await response.json();
        currentProcessingJob = { fileRef: fileToTranslate, translationId: data.translation_id };
        fileToTranslate.translationId = data.translation_id;
        updateFileStatusInList(fileToTranslate.name, 'Submitted', data.translation_id);

        // Update active translations state when a new translation starts
        updateActiveTranslationsState();

    } catch (error) {
        addLog(`❌ Error initiating translation for ${fileToTranslate.name}: ${error.message}`);
        showMessage(`Error starting ${fileToTranslate.name}: ${error.message}`, 'error');
        updateFileStatusInList(fileToTranslate.name, 'Initiation Error');
        currentProcessingJob = null;
        processNextFileInQueue();
    }
}

/**
 * Reset UI state to idle (no active translation)
 * This function should be called when:
 * - An interruption fails (translation already finished)
 * - User manually cancels
 * - Any inconsistent state is detected
 */
function resetUIToIdle() {
    console.log('Resetting UI to idle state...');

    // Reset state variables
    isBatchActive = false;
    currentProcessingJob = null;

    // Reset UI elements
    document.getElementById('interruptBtn').classList.add('hidden');
    document.getElementById('interruptBtn').disabled = false;
    document.getElementById('interruptBtn').innerHTML = '⏹️ Interrupt Current & Stop Batch';

    document.getElementById('translateBtn').disabled = filesToProcess.length === 0;
    document.getElementById('translateBtn').innerHTML = '▶️ Start Translation Batch';

    // Hide progress section if no files to process
    if (filesToProcess.length === 0) {
        document.getElementById('progressSection').classList.add('hidden');
    }

    // Update active translations state
    updateActiveTranslationsState();

    addLog('🔄 UI reset to idle state');
}

async function interruptCurrentTranslation() {
    if (!isBatchActive || !currentProcessingJob) {
        showMessage('No active translation to interrupt.', 'info');
        return;
    }

    const fileToInterrupt = currentProcessingJob.fileRef;
    const tidToInterrupt = currentProcessingJob.translationId;

    document.getElementById('interruptBtn').disabled = true;
    document.getElementById('interruptBtn').innerHTML = '⏳ Interrupting...';

    try {
        const response = await fetch(`${API_BASE_URL}/api/translation/${tidToInterrupt}/interrupt`, { method: 'POST' });

        if (!response.ok) {
            const errData = await response.json();
            const errorMsg = errData.message || `Failed to send interrupt signal for ${fileToInterrupt.name}.`;

            // Check if the error indicates the translation is no longer running
            if (response.status === 400 && errorMsg.includes('not in an interruptible state')) {
                addLog(`ℹ️ Translation for ${fileToInterrupt.name} has already finished or stopped.`);
                showMessage(`Translation already completed or stopped.`, 'info');

                // Reset UI to clean state since there's nothing to interrupt
                resetUIToIdle();
                return;
            }

            throw new Error(errorMsg);
        }

        // Success - log only after confirmation
        addLog(`🛑 User requested interruption for ${fileToInterrupt.name} (ID: ${tidToInterrupt}). This will stop the batch.`);
        showMessage(`ℹ️ Interruption for ${fileToInterrupt.name} requested. Batch will stop after this file.`, 'info');

    } catch (error) {
        // Network error or other unexpected error
        addLog(`❌ Error sending interruption: ${error.message}`);
        showMessage(`❌ Error sending interruption for ${fileToInterrupt.name}: ${error.message}`, 'error');

        // Re-enable interrupt button for retry
        document.getElementById('interruptBtn').disabled = false;
        document.getElementById('interruptBtn').innerHTML = '⏹️ Interrupt Current & Stop Batch';
    }
}

function updateProgress(percent) {
    const progressBar = document.getElementById('progressBar');
    progressBar.style.width = percent + '%';
    progressBar.textContent = Math.round(percent) + '%';
}

function clearActivityLog() {
    document.getElementById('logContainer').innerHTML = '';
    addLog('📝 Activity log cleared by user');
}


// Function to check if model is small (<=12B parameters) and show recommendation
function checkModelSizeAndShowRecommendation() {
    const modelSelect = document.getElementById('model');
    const modelName = modelSelect.value.toLowerCase();
    const recommendationDiv = document.getElementById('smallModelRecommendation');

    // Pattern to detect model size (e.g., "7b", "12b", "3b", etc.)
    const sizeMatch = modelName.match(/(\d+(?:\.\d+)?)b/);

    let isSmallModel = false;

    if (sizeMatch) {
        const sizeInB = parseFloat(sizeMatch[1]);
        isSmallModel = sizeInB <= 12;
    }

    // Show recommendation if small model and not already in simple mode
    if (isSmallModel && !document.getElementById('simpleMode').checked) {
        recommendationDiv.style.display = 'block';
    } else {
        recommendationDiv.style.display = 'none';
    }
}

// Initialize event listeners
window.addEventListener('DOMContentLoaded', function() {
    // Simple mode checkbox handler
    document.getElementById('simpleMode').addEventListener('change', (e) => {
        const simpleModeInfo = document.getElementById('simpleModeInfo');
        if (e.target.checked) {
            simpleModeInfo.style.display = 'block';
        } else {
            simpleModeInfo.style.display = 'none';
        }
        // Re-check model size when simple mode changes
        checkModelSizeAndShowRecommendation();
    });

    // Model selection change handler
    document.getElementById('model').addEventListener('change', checkModelSizeAndShowRecommendation);

    // Load default configuration including languages
    loadDefaultConfig();

    // Load file list on page load
    refreshFileList();
});

async function loadDefaultConfig() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/config`);
        if (response.ok) {
            const config = await response.json();
            
            // Set default languages
            if (config.default_source_language) {
                setDefaultLanguage('sourceLang', 'customSourceLang', config.default_source_language);
            }
            if (config.default_target_language) {
                setDefaultLanguage('targetLang', 'customTargetLang', config.default_target_language);
            }
            
            // Set other configuration values
            if (config.api_endpoint) document.getElementById('apiEndpoint').value = config.api_endpoint;
            if (config.chunk_size) document.getElementById('chunkSize').value = config.chunk_size;
            if (config.timeout) document.getElementById('timeout').value = config.timeout;
            if (config.context_window) document.getElementById('contextWindow').value = config.context_window;
            if (config.max_attempts) document.getElementById('maxAttempts').value = config.max_attempts;
            if (config.retry_delay) document.getElementById('retryDelay').value = config.retry_delay;
            if (config.gemini_api_key) document.getElementById('geminiApiKey').value = config.gemini_api_key;
            
            // Load available models after setting configuration
            loadAvailableModels();
        }
    } catch (error) {
        console.error('Error loading default configuration:', error);
    }
}

function setDefaultLanguage(selectId, customInputId, defaultLanguage) {
    const select = document.getElementById(selectId);
    const customInput = document.getElementById(customInputId);
    
    // Check if the default language is in the dropdown options
    let languageFound = false;
    for (let option of select.options) {
        if (option.value.toLowerCase() === defaultLanguage.toLowerCase()) {
            select.value = option.value;
            languageFound = true;
            customInput.style.display = 'none';
            break;
        }
    }
    
    // If language not found in dropdown, use "Other" and set custom input
    if (!languageFound) {
        select.value = 'Other';
        customInput.value = defaultLanguage;
        customInput.style.display = 'block';
    }
}

// File Management Functions
let selectedFiles = new Set();

async function refreshFileList() {
    const loadingDiv = document.getElementById('fileListLoading');
    const containerDiv = document.getElementById('fileManagementContainer');
    const tableBody = document.getElementById('fileTableBody');
    const emptyDiv = document.getElementById('fileListEmpty');
    
    loadingDiv.style.display = 'block';
    containerDiv.style.display = 'none';
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/files`);
        if (!response.ok) {
            throw new Error('Failed to fetch file list');
        }
        
        const data = await response.json();
        
        loadingDiv.style.display = 'none';
        containerDiv.style.display = 'block';
        
        // Clear existing table rows
        tableBody.innerHTML = '';
        selectedFiles.clear();
        updateFileSelectionButtons();
        
        if (data.files.length === 0) {
            emptyDiv.style.display = 'block';
            containerDiv.querySelector('.file-table').style.display = 'none';
        } else {
            emptyDiv.style.display = 'none';
            containerDiv.querySelector('.file-table').style.display = 'table';
            
            // Populate table with files
            data.files.forEach(file => {
                const row = document.createElement('tr');
                
                // Format date
                const modifiedDate = new Date(file.modified_date);
                const formattedDate = modifiedDate.toLocaleString();
                
                // Determine file icon
                const fileIcon = file.file_type === 'epub' ? '📚' : 
                               file.file_type === 'srt' ? '🎬' : 
                               file.file_type === 'txt' ? '📄' : '📎';
                
                // Check if file is a translated file (for audiobook generation)
                const isTranslatedFile = file.filename.includes('translated_') || file.filename.includes('_to_');
                
                row.innerHTML = `
                    <td>
                        <input type="checkbox" class="file-checkbox" data-filename="${file.filename}" onchange="toggleFileSelection('${file.filename}')">
                    </td>
                    <td>
                        <span class="clickable-filename" onclick="openLocalFile('${file.filename}')" title="Click to open file">
                            ${fileIcon} ${file.filename}
                        </span>
                    </td>
                    <td>${file.file_type.toUpperCase()}</td>
                    <td>${file.size_mb} MB</td>
                    <td>${formattedDate}</td>
                    <td style="text-align: center;">
                        ${isTranslatedFile ? `<button class="file-action-btn audiobook" onclick="createAudiobook('${file.filename}', '${file.file_path}')" title="Create Audiobook">
                            🎧
                        </button>` : ''}
                        <button class="file-action-btn download" onclick="downloadSingleFile('${file.filename}')" title="Download">
                            📥
                        </button>
                        <button class="file-action-btn delete" onclick="deleteSingleFile('${file.filename}')" title="Delete">
                            🗑️
                        </button>
                    </td>
                `;
                
                tableBody.appendChild(row);
            });
        }
        
        // Update totals
        document.getElementById('totalFileCount').textContent = data.total_files;
        document.getElementById('totalFileSize').textContent = `${data.total_size_mb} MB`;
        
    } catch (error) {
        loadingDiv.style.display = 'none';
        showMessage(`Error loading file list: ${error.message}`, 'error');
    }
}

function toggleFileSelection(filename) {
    if (selectedFiles.has(filename)) {
        selectedFiles.delete(filename);
    } else {
        selectedFiles.add(filename);
    }
    updateFileSelectionButtons();
}

function toggleSelectAll() {
    const checkboxes = document.querySelectorAll('.file-checkbox');
    const selectAllFiles = document.getElementById('selectAllFiles');
    
    // Use the Select All checkbox state
    const isChecked = selectAllFiles.checked;
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = isChecked;
        const filename = checkbox.getAttribute('data-filename');
        if (isChecked) {
            selectedFiles.add(filename);
        } else {
            selectedFiles.delete(filename);
        }
    });
    
    updateFileSelectionButtons();
}

function updateFileSelectionButtons() {
    const hasSelection = selectedFiles.size > 0;
    document.getElementById('batchDownloadBtn').disabled = !hasSelection;
    document.getElementById('batchDeleteBtn').disabled = !hasSelection;
    
    // Update button text with count
    if (hasSelection) {
        document.getElementById('batchDownloadBtn').innerHTML = `📥 Download Selected (${selectedFiles.size})`;
        document.getElementById('batchDeleteBtn').innerHTML = `🗑️ Delete Selected (${selectedFiles.size})`;
    } else {
        document.getElementById('batchDownloadBtn').innerHTML = `📥 Download Selected`;
        document.getElementById('batchDeleteBtn').innerHTML = `🗑️ Delete Selected`;
    }
}

async function downloadSingleFile(filename) {
    window.location.href = `${API_BASE_URL}/api/files/${encodeURIComponent(filename)}`;
}

async function deleteSingleFile(filename) {
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/files/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showMessage(data.message, 'success');
            refreshFileList();
        } else {
            showMessage(data.error || 'Failed to delete file', 'error');
        }
    } catch (error) {
        showMessage(`Error deleting file: ${error.message}`, 'error');
    }
}

async function downloadSelectedFiles() {
    if (selectedFiles.size === 0) {
        showMessage('No files selected for download', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/files/batch/download`, {
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
            
            showMessage(`Downloaded ${selectedFiles.size} files as zip`, 'success');
        } else {
            const data = await response.json();
            showMessage(data.error || 'Failed to download files', 'error');
        }
    } catch (error) {
        showMessage(`Error downloading files: ${error.message}`, 'error');
    }
}

async function deleteSelectedFiles() {
    if (selectedFiles.size === 0) {
        showMessage('No files selected for deletion', 'error');
        return;
    }

    if (!confirm(`Are you sure you want to delete ${selectedFiles.size} file(s)?`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/files/batch/delete`, {
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
            showMessage(message, data.failed.length > 0 ? 'info' : 'success');
            refreshFileList();
        } else {
            showMessage(data.error || 'Failed to delete files', 'error');
        }
    } catch (error) {
        showMessage(`Error deleting files: ${error.message}`, 'error');
    }
}

async function openLocalFile(filename) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/files/${encodeURIComponent(filename)}/open`, {
            method: 'POST'
        });

        const data = await response.json();

        if (response.ok) {
            showMessage(`File opened: ${filename}`, 'success');
            addLog(`📂 Opened file: ${filename}`);
        } else {
            showMessage(data.error || 'Failed to open file', 'error');
        }
    } catch (error) {
        showMessage(`Error opening file: ${error.message}`, 'error');
    }
}

// ========================================
// Resumable Jobs Management
// ========================================

/**
 * Load and display resumable jobs
 */
async function loadResumableJobs() {
    const section = document.getElementById('resumableJobsSection');
    const loading = document.getElementById('resumableJobsLoading');
    const listContainer = document.getElementById('resumableJobsList');
    const emptyMessage = document.getElementById('resumableJobsEmpty');

    // Show loading
    loading.style.display = 'block';
    listContainer.style.display = 'none';
    emptyMessage.style.display = 'none';

    try {
        const response = await fetch(`${API_BASE_URL}/api/resumable`);
        const data = await response.json();
        const jobs = data.resumable_jobs || [];

        // Update active translations state first
        await updateActiveTranslationsState();
        const hasActiveTranslation = activeTranslationsState.hasActive;

        loading.style.display = 'none';

        if (jobs.length === 0) {
            // Hide section if no jobs
            section.style.display = 'none';
            emptyMessage.style.display = 'block';
            return;
        }

        // Show section and populate jobs
        section.style.display = 'block';
        listContainer.style.display = 'block';

        // Add warning banner if active translation
        let warningBanner = '';
        if (hasActiveTranslation) {
            const activeNames = activeTranslationsState.activeJobs.map(t => t.output_filename || 'Unknown').join(', ');
            warningBanner = `
                <div class="active-translation-warning" style="background: #fef3c7; border: 1px solid #f59e0b; padding: 12px; margin-bottom: 15px; border-radius: 6px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 20px;">⚠️</span>
                        <div style="flex: 1;">
                            <strong style="color: #92400e;">Traduction active en cours</strong>
                            <p style="margin: 5px 0 0 0; font-size: 13px; color: #78350f;">
                                Les reprises sont désactivées. Traduction(s) active(s): ${escapeHtml(activeNames)}
                            </p>
                        </div>
                    </div>
                </div>
            `;
        }

        // Build jobs HTML
        listContainer.innerHTML = warningBanner + jobs.map(job => {
            const progress = job.progress || {};
            const completedChunks = progress.completed_chunks || 0;
            const totalChunks = progress.total_chunks || 0;
            const progressPercent = job.progress_percentage || 0;
            const fileType = (job.file_type || 'txt').toUpperCase();

            const createdDate = job.created_at ? new Date(job.created_at).toLocaleString('fr-FR') : 'N/A';
            const pausedDate = job.paused_at ? new Date(job.paused_at).toLocaleString('fr-FR') : job.updated_at ? new Date(job.updated_at).toLocaleString('fr-FR') : 'N/A';

            return `
                <div class="resumable-job-card" style="border: 1px solid #e5e7eb; padding: 20px; margin-bottom: 15px; border-radius: 8px; background: #f9fafb;">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 15px;">
                        <div style="flex: 1;">
                            <div style="font-size: 16px; font-weight: 600; color: #1f2937; margin-bottom: 8px;">
                                ${escapeHtml(job.input_filename || 'Unknown')}
                            </div>
                            <div style="font-size: 14px; color: #6b7280; margin-bottom: 5px;">
                                → ${escapeHtml(job.output_filename || 'Unknown')}
                            </div>
                            <div style="display: flex; gap: 15px; font-size: 13px; color: #6b7280; margin-top: 10px;">
                                <span><strong>Type:</strong> ${fileType}</span>
                                <span><strong>ID:</strong> ${job.translation_id}</span>
                            </div>
                        </div>

                        <div style="display: flex; gap: 10px;">
                            <button class="btn btn-primary" onclick="resumeJob('${job.translation_id}')"
                                    title="${hasActiveTranslation ? '⚠️ Impossible: une traduction est déjà en cours' : 'Reprendre cette traduction'}"
                                    ${hasActiveTranslation ? 'disabled style="opacity: 0.5; cursor: not-allowed;"' : ''}>
                                ▶️ Reprendre
                            </button>
                            <button class="btn btn-danger" onclick="deleteCheckpoint('${job.translation_id}')" title="Supprimer ce checkpoint">
                                🗑️ Supprimer
                            </button>
                        </div>
                    </div>

                    <div style="margin-bottom: 10px;">
                        <div style="display: flex; justify-content: space-between; font-size: 13px; color: #6b7280; margin-bottom: 5px;">
                            <span>Progression: ${completedChunks} / ${totalChunks} chunks (${progressPercent}%)</span>
                        </div>
                        <div style="width: 100%; background: #e5e7eb; border-radius: 4px; height: 8px; overflow: hidden;">
                            <div style="width: ${progressPercent}%; background: #3b82f6; height: 100%; transition: width 0.3s;"></div>
                        </div>
                    </div>

                    <div style="display: flex; gap: 20px; font-size: 12px; color: #9ca3af;">
                        <span>Créé: ${createdDate}</span>
                        <span>En pause: ${pausedDate}</span>
                    </div>
                </div>
            `;
        }).join('');

        addLog(`📦 ${jobs.length} traduction(s) en pause trouvée(s)`);

    } catch (error) {
        loading.style.display = 'none';
        emptyMessage.style.display = 'block';
        emptyMessage.innerHTML = `<p style="color: #ef4444;">Erreur lors du chargement: ${escapeHtml(error.message)}</p>`;
        console.error('Error loading resumable jobs:', error);
    }
}

/**
 * Resume a paused translation job
 */
async function resumeJob(translationId) {
    // Check if there's an active translation using our state
    if (activeTranslationsState.hasActive) {
        const activeNames = activeTranslationsState.activeJobs.map(t => t.output_filename || 'Unknown').join(', ');
        showMessage(`⚠️ Impossible de reprendre: une traduction est déjà en cours (${activeNames}). Veuillez attendre la fin ou l'interrompre.`, 'error');
        return;
    }

    if (!confirm('Voulez-vous reprendre cette traduction ?')) {
        return;
    }

    try {
        addLog(`⏯️ Reprise de la traduction ${translationId}...`);
        showMessage('Reprise de la traduction...', 'info');

        const response = await fetch(`${API_BASE_URL}/api/resume/${translationId}`, {
            method: 'POST'
        });

        const data = await response.json();

        if (response.ok) {
            showMessage(`✅ Traduction reprise avec succès ! Reprise au chunk ${data.resume_from_chunk}`, 'success');
            addLog(`✅ Traduction ${translationId} reprise au chunk ${data.resume_from_chunk}`);

            // Fetch job details to get filename and file type
            const jobResponse = await fetch(`${API_BASE_URL}/api/translation/${translationId}`);
            const jobData = await jobResponse.json();

            // Set up currentProcessingJob to track this resumed translation
            currentProcessingJob = {
                translationId: translationId,
                fileRef: {
                    name: jobData.config?.output_filename || 'Resumed Translation',
                    fileType: jobData.config?.file_type || 'txt'
                }
            };

            // Mark as batch active to enable interruption
            isBatchActive = true;

            // Show progress section
            const progressSection = document.getElementById('progressSection');
            if (progressSection) {
                progressSection.classList.remove('hidden');
                progressSection.scrollIntoView({ behavior: 'smooth' });
            }

            // Update title with actual filename
            const fileName = jobData.config?.output_filename || 'traduction reprise';
            document.getElementById('currentFileProgressTitle').textContent = `📊 Reprise: ${fileName}`;

            // Show stats grid
            document.getElementById('statsGrid').style.display = '';

            // Show interrupt button for resumed translation
            document.getElementById('interruptBtn').classList.remove('hidden');
            document.getElementById('interruptBtn').disabled = false;

            // Initialize progress
            updateProgress(jobData.progress || 0);

            // Update active translations state immediately
            updateActiveTranslationsState();

            // Refresh resumable jobs list after a delay
            setTimeout(() => {
                loadResumableJobs();
            }, 1000);
        } else {
            // Enhanced error message for active translation conflicts
            if (response.status === 409 && data.active_translations) {
                const activeList = data.active_translations
                    .map(t => `• ${t.output_filename} (${t.status})`)
                    .join('\n');
                showMessage(`⚠️ Impossible de reprendre: une traduction est déjà en cours\n\n${activeList}\n\nVeuillez attendre la fin ou interrompre la traduction active.`, 'error');
                addLog(`⚠️ ${data.message}`);
            } else {
                showMessage(`❌ Erreur: ${data.error}`, 'error');
                addLog(`❌ Échec de la reprise: ${data.error}`);
            }
        }
    } catch (error) {
        showMessage(`❌ Erreur lors de la reprise: ${error.message}`, 'error');
        addLog(`❌ Erreur réseau: ${error.message}`);
        console.error('Error resuming job:', error);
    }
}

/**
 * Delete a checkpoint
 */
async function deleteCheckpoint(translationId) {
    if (!confirm('Êtes-vous sûr de vouloir supprimer ce checkpoint ?\n\nCette action est irréversible et vous perdrez toute la progression.')) {
        return;
    }

    try {
        addLog(`🗑️ Suppression du checkpoint ${translationId}...`);

        const response = await fetch(`${API_BASE_URL}/api/checkpoint/${translationId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (response.ok) {
            showMessage('✅ Checkpoint supprimé avec succès', 'success');
            addLog(`✅ Checkpoint ${translationId} supprimé`);

            // Refresh resumable jobs list
            loadResumableJobs();
        } else {
            showMessage(`❌ Erreur: ${data.error}`, 'error');
            addLog(`❌ Échec de la suppression: ${data.error}`);
        }
    } catch (error) {
        showMessage(`❌ Erreur lors de la suppression: ${error.message}`, 'error');
        addLog(`❌ Erreur réseau: ${error.message}`);
        console.error('Error deleting checkpoint:', error);
    }
}

/**
 * Helper function to escape HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Load resumable jobs on page load
document.addEventListener('DOMContentLoaded', function() {
    // Initialize active translations state on page load
    updateActiveTranslationsState().then(() => {
        loadResumableJobs();
    });
});
