let filesToProcess = [];
let translationQueue = [];
let currentProcessingJob = null;
let isBatchActive = false;

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
        showMessage('Connection lost. Batch paused. Reconnect to resume or reset.', 'error');
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
    processNextFileInQueue();
}

function handleTranslationUpdate(data) {
    if (!currentProcessingJob || data.translation_id !== currentProcessingJob.translationId) return;

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
    } else if (data.status === 'interrupted') {
        finishCurrentFileTranslationUI(`ℹ️ ${currentFile.name}: Translation interrupted.`, 'info', data);
    } else if (data.status === 'error') {
        finishCurrentFileTranslationUI(`❌ ${currentFile.name}: Error - ${data.error || 'Unknown error.'}`, 'error', data);
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
    translationQueue = [];
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
    translationQueue = [...filesToProcess];

    document.getElementById('translateBtn').disabled = true;
    document.getElementById('translateBtn').innerHTML = '⏳ Batch in Progress...';
    document.getElementById('interruptBtn').classList.remove('hidden');
    document.getElementById('interruptBtn').disabled = false;

    // Don't clear the log when starting a new batch
    // document.getElementById('logContainer').innerHTML = '';

    addLog(`🚀 Batch translation started for ${translationQueue.length} file(s).`);
    showMessage(`Batch of ${translationQueue.length} file(s) initiated.`, 'info');

    processNextFileInQueue();
}

async function processNextFileInQueue() {
    if (currentProcessingJob) return;

    if (translationQueue.length === 0) {
        isBatchActive = false;
        document.getElementById('translateBtn').disabled = filesToProcess.length === 0;
        document.getElementById('translateBtn').innerHTML = '▶️ Start Translation Batch';
        document.getElementById('interruptBtn').classList.add('hidden');
        showMessage('✅ Batch translation completed for all files!', 'success');
        addLog('🏁 All files in the batch have been processed.');
        document.getElementById('currentFileProgressTitle').textContent = `📊 Batch Completed`;
        return;
    }

    const fileToTranslate = translationQueue.shift();

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
        custom_instructions: document.getElementById('customInstructions').value.trim(),
        enable_post_processing: document.getElementById('enablePostProcessing').checked,
        post_processing_instructions: document.getElementById('postProcessingInstructions').value.trim(),
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

    } catch (error) {
        addLog(`❌ Error initiating translation for ${fileToTranslate.name}: ${error.message}`);
        showMessage(`Error starting ${fileToTranslate.name}: ${error.message}`, 'error');
        updateFileStatusInList(fileToTranslate.name, 'Initiation Error');
        currentProcessingJob = null;
        processNextFileInQueue();
    }
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
    addLog(`🛑 User requested interruption for ${fileToInterrupt.name} (ID: ${tidToInterrupt}). This will stop the batch.`);
    translationQueue = [];

    try {
        const response = await fetch(`${API_BASE_URL}/api/translation/${tidToInterrupt}/interrupt`, { method: 'POST' });
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.message || `Failed to send interrupt signal for ${fileToInterrupt.name}.`);
        }
        showMessage(`ℹ️ Interruption for ${fileToInterrupt.name} requested. Batch will stop after this file.`, 'info');
    } catch (error) {
        showMessage(`❌ Error sending interruption for ${fileToInterrupt.name}: ${error.message}`, 'error');
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


// Initialize event listeners
window.addEventListener('DOMContentLoaded', function() {
    // Post-processing checkbox handler
    document.getElementById('enablePostProcessing').addEventListener('change', (e) => {
        const postProcessingOptions = document.getElementById('postProcessingOptions');
        if (e.target.checked) {
            postProcessingOptions.style.display = 'block';
        } else {
            postProcessingOptions.style.display = 'none';
        }
    });

    // Simple mode checkbox handler
    document.getElementById('simpleMode').addEventListener('change', (e) => {
        const simpleModeInfo = document.getElementById('simpleModeInfo');
        if (e.target.checked) {
            simpleModeInfo.style.display = 'block';
        } else {
            simpleModeInfo.style.display = 'none';
        }
    });
    
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
