# Troubleshooting Guide

Solutions to common problems with TranslateBookWithLLM.

---

## Table of Contents

- [Connection Issues](#connection-issues)
- [Model Issues](#model-issues)
- [Performance Issues](#performance-issues)
- [Thinking Models](#thinking-models)
- [EPUB Issues](#epub-issues)
- [SRT Issues](#srt-issues)
- [Web Interface Issues](#web-interface-issues)
- [Configuration Issues](#configuration-issues)
- [Language Detection Issues](#language-detection-issues)
- [Checkpoint & Resume Issues](#checkpoint--resume-issues)
- [Quick Reference](#quick-reference)
- [Debugging](#debugging)
- [Getting Help](#getting-help)

---

## Connection Issues

### "Connection refused" / "Cannot connect to Ollama"

**Cause**: Ollama is not running or unreachable.

**Solutions**:
1. Check Ollama icon in system tray
2. Test connection: `curl http://localhost:11434/api/tags`
3. Restart Ollama from Start Menu
4. Check firewall (allow port 11434)
5. Verify endpoint in `.env`: `API_ENDPOINT=http://localhost:11434/api/generate`

### "Invalid API key" (Gemini, OpenAI, OpenRouter)

**Cause**: Wrong, expired, or missing API key.

**Solutions**:
1. Verify key is copied correctly (no extra spaces)
2. Check key is active on provider's website
3. Verify you have credits/quota remaining
4. Check the correct environment variable is set:
   - Gemini: `GEMINI_API_KEY`
   - OpenAI: `OPENAI_API_KEY`
   - OpenRouter: `OPENROUTER_API_KEY`

### "Rate limit exceeded"

**Cause**: Too many requests to the API.

**Solutions**:
1. Wait a few minutes before retrying
2. The system will automatically retry with exponential backoff
3. Consider using a local model (Ollama) for large files
4. Check your API plan limits

---

## Model Issues

### "Model not found"

**Cause**: Model not downloaded or wrong name.

**Solutions**:
1. List installed models: `ollama list`
2. Download missing model: `ollama pull model-name`
3. Check exact model name (case-sensitive)
4. For cloud providers, verify the model ID is correct

### "Context length exceeded"

**Cause**: Chunk is too large for model's context window.

**Solutions**:
1. Reduce chunk size: `MAX_TOKENS_PER_CHUNK=200` (default: 450)
2. Increase context window: `OLLAMA_NUM_CTX=8192`
3. Enable adaptive context: `AUTO_ADJUST_CONTEXT=true` (default)
4. Use a model with larger context window

**Formula**: `required_context = prompt_tokens + (MAX_TOKENS_PER_CHUNK * 2) + 50`

### "Out of memory" / OOM errors

**Cause**: Not enough RAM/VRAM for the model.

**Solutions**:
1. Use a smaller model (8B instead of 14B)
2. Reduce context window: `OLLAMA_NUM_CTX=2048`
3. Close other applications
4. Try a cloud provider (OpenRouter, Gemini, OpenAI)

---

## Performance Issues

### "Request timeout"

**Cause**: Request taking too long.

**Solutions**:
1. Increase timeout: `REQUEST_TIMEOUT=1800` (30 min, default: 900)
2. Reduce chunk size: `MAX_TOKENS_PER_CHUNK=200`
3. Try a smaller/faster model
4. Try a cloud provider

### Model enters repetition loop

**Symptoms**: Model repeats the same phrase endlessly (e.g., "I'm not sure. I'm not sure...")

**Cause**: Context window exceeded, model confusion, or thinking model issues.

**Solutions**:
1. The system automatically detects repetition loops and will retry
2. Increase context window: `OLLAMA_NUM_CTX=8192`
3. Reduce chunk size for simpler content
4. Use a different model
5. For thinking models, see [Thinking Models](#thinking-models) section

**Detection thresholds** (configurable):
- Standard models: 10 repetitions (`REPETITION_MIN_COUNT`)
- Thinking models: 15 repetitions (`REPETITION_MIN_COUNT_THINKING`)

---

## Thinking Models

### What are thinking models?

Some models (DeepSeek R1, Qwen3, QwQ, etc.) produce internal reasoning within `<think>` tags before responding. This is normal behavior.

### Classifications

| Type | Models | Behavior |
|------|--------|----------|
| **Controllable** | qwen3:8b, qwen3:14b, qwen3:4b | Can disable thinking with `think=false` |
| **Uncontrollable** | qwen3:30b, deepseek-r1, qwq, marco-o1, phi4-reasoning | Always thinks, cannot be disabled |
| **Standard** | Most other models | No thinking capability |

### "Thinking model produces very long responses"

**Cause**: Uncontrollable thinking models always include reasoning.

**Solutions**:
1. This is expected behavior - the system filters out `<think>` content
2. Use a controllable thinking model (qwen3:8b, qwen3:14b)
3. Use a standard (non-thinking) model
4. Increase context for thinking models: `ADAPTIVE_CONTEXT_INITIAL_THINKING=6144`

### "Model not detected as thinking model"

**Cause**: Model not in known lists or auto-detection failed.

**Solutions**:
1. Enable debug mode to see detection logs: `DEBUG_MODE=true`
2. The system auto-detects thinking behavior at runtime
3. Check if model name matches known patterns in `src/config.py`

---

## EPUB Issues

### "EPUB won't open" / "Invalid EPUB"

**Cause**: Reader rejects the EPUB format.

**Solutions**:
1. Test with Calibre (most permissive reader)
2. Validate EPUB: [validator.idpf.org](http://validator.idpf.org/)
3. Try a larger model (better at preserving structure)
4. Enable debug mode to see parsing errors

### "Placeholders visible in text" (`[id0]`, `[id1]`)

**Cause**: Model did not preserve placeholders during translation.

**Note**: The placeholder format is now `[id0]`, `[id1]`, etc. (not `⟦TAG0⟧`).

**Solutions**:
1. The system has a 3-phase fallback that handles most cases automatically:
   - **Phase 1**: Normal translation with placeholder preservation
   - **Phase 2**: Token alignment to reinsert missing placeholders
   - **Phase 3**: Proportional fallback based on position
2. If there are many formatting errors in the output file, use a more capable LLM
3. Enable adaptive context: `AUTO_ADJUST_CONTEXT=true`

### "Formatting lost" (bold, italic, styles)

**Cause**: Style tags not properly preserved.

**Solutions**:
1. The 3-phase fallback system handles this automatically
2. Try a larger model for better HTML handling
3. Enable debug mode to see tag preservation details

### "Technical content corrupted" (code, formulas, measurements)

**Cause**: Model translated content that should be preserved.

**Note**: Technical content protection is **always enabled** and automatic.

**Protected content includes**:
- Code blocks (` ```python ``` `)
- Inline code (`` `variable` ``)
- LaTeX formulas (`$E=mc^2$`, `$$\int_0^1 x dx$$`)
- Measurements (`10 Mbps`, `5V`, `100 mA`)
- Technical IDs (`TIA/EIA-485-A`, `DS1487`)

**Solutions**:
1. This should work automatically - check if content matches expected patterns
2. Enable debug mode to see what's being protected
3. Report issue if valid technical content is being translated

---

## SRT Issues

### "Timing desynchronized"

**Cause**: Subtitle timing metadata corrupted.

**Solutions**:
1. SRT uses subtitle-count based grouping (not token-based)
2. Configure grouping: `SRT_LINES_PER_BLOCK=5`, `SRT_MAX_CHARS_PER_BLOCK=500`
3. Try a smaller block size for better timing preservation

### "Subtitle numbers wrong"

**Cause**: Subtitle index corruption during translation.

**Solutions**:
1. The system preserves subtitle structure automatically
2. Try a larger model with better instruction-following
3. Reduce `SRT_LINES_PER_BLOCK` for simpler chunks

---

## Web Interface Issues

### "Port already in use"

**Cause**: Port 5000 is used by another application.

**Solutions**:
1. Find what's using it:
   - Windows: `netstat -an | find "5000"`
   - Mac/Linux: `lsof -i :5000`
2. Change port in `.env`: `PORT=8080`
3. Kill the other process

### "File upload fails"

**Cause**: File too large or wrong format.

**Solutions**:
1. Check file format: `.txt`, `.epub`, `.srt` only (PDF in development)
2. Check file size limits
3. Try a smaller file first
4. Check directory permissions: `data/uploads/` must be writable

### "WebSocket connection fails" / "No real-time updates"

**Cause**: Network issue, CORS, or proxy problem.

**Solutions**:
1. Check browser console for WebSocket errors
2. Verify `HOST=127.0.0.1` or `HOST=0.0.0.0` in `.env`
3. Check firewall allows WebSocket connections
4. Try a different browser
5. Disable proxy/VPN temporarily

---

## Configuration Issues

### ".env file not found" warning

**Cause**: Missing `.env` file on first run.

**Solutions**:
1. Copy template: `cp .env.example .env` (or `copy` on Windows)
2. Edit with your configuration
3. Restart application
4. The system will prompt you with a 5-second grace period on first run

### "DEBUG_MODE not working"

**Cause**: Environment variable not loaded.

**Solutions**:
1. Set in `.env`: `DEBUG_MODE=true`
2. Set before running: `export DEBUG_MODE=true` (Mac/Linux) or `set DEBUG_MODE=true` (Windows)
3. Verify `.env` is in the working directory
4. Restart the application

### "Provider not recognized"

**Cause**: Invalid provider name in configuration.

**Valid providers**: `ollama`, `gemini`, `openai`, `openrouter`

**Solutions**:
1. Check spelling in `.env`: `LLM_PROVIDER=ollama`
2. Provider names are case-insensitive
3. For Gemini models with Ollama, the system auto-switches if model starts with "gemini"

---

## Language Detection Issues

### "Wrong source language detected"

**Cause**: Too short text, mixed languages, or ambiguous content.

**Solutions**:
1. Use file with at least 50+ characters of text
2. Explicitly specify source language:
   - CLI: `-sl English`
   - Web: Select in dropdown
3. Ensure file content is primarily in one language
4. Detection confidence threshold is 70% for auto-fill

### "Language not supported"

**Cause**: Language not in the 40+ supported languages.

**Solutions**:
1. Check supported languages in `src/utils/language_detector.py`
2. Use ISO 639-1 language codes or full language names
3. For rare languages, specify manually instead of auto-detect

---

## Checkpoint & Resume Issues

### "Cannot resume translation"

**Cause**: Checkpoint data corrupted or session mismatch.

**Solutions**:
1. Check database exists: `data/jobs.db`
2. Verify uploaded file exists: `data/uploads/{job_id}/`
3. Start a new translation if checkpoint is corrupted
4. Check logs for specific checkpoint errors

### "Progress lost after restart"

**Cause**: Translation was interrupted before checkpoint was saved.

**Solutions**:
1. Checkpoints are saved periodically during translation
2. Very short translations may not have checkpoints
3. For long translations, progress should be preserved
4. Ensure `data/` directory is writable

---

## Quick Reference

| Problem | Quick Fix |
|---------|-----------|
| Ollama not connecting | Restart Ollama |
| Model not found | `ollama pull model-name` |
| Context exceeded | `MAX_TOKENS_PER_CHUNK=200` |
| Timeouts | `REQUEST_TIMEOUT=1800` |
| Out of memory | Try smaller model |
| Repetition loop | Increase `OLLAMA_NUM_CTX` |
| EPUB broken | Try larger model |
| Placeholders visible | System auto-recovers (3-phase fallback) |
| Thinking model slow | Use controllable model (qwen3:14b) |
| Port in use | Set `PORT=8080` in .env |
| No debug logs | Set `DEBUG_MODE=true` in .env |

---

## Debugging

### Enable Debug Mode

Set in `.env`:
```
DEBUG_MODE=true
```

This enables:
- Verbose configuration logging
- API request/response details
- Model detection logs
- Context window calculations
- Token counting details
- Tag preservation logs

### Log Types

The system uses structured logging with types:
- `TRANSLATION_START` - Translation job started
- `TRANSLATION_PROGRESS` - Progress updates
- `TRANSLATION_COMPLETE` - Job finished
- `ERROR` - Error occurred
- `WARNING` - Non-fatal issues
- `DEBUG` - Detailed debug info

### Key Debug Points

1. **Model Detection**: Look for "Testing thinking behavior"
2. **Context Calculation**: Context size detection logs
3. **Chunking**: Token count per chunk
4. **API Calls**: Request/response logging
5. **Error Recovery**: Retry attempts and strategies

---

## Getting Help

1. **Check this guide** for common solutions
2. **Enable debug mode** (`DEBUG_MODE=true`) for detailed logs
3. **Test with a small file** first to isolate issues
4. **Review console/terminal logs** for error messages
5. **Open an issue**: [GitHub Issues](https://github.com/hydropix/TranslateBookWithLLM/issues)

### When reporting issues, include:

- Operating system
- Python version
- LLM provider and model used
- Error message (full traceback if available)
- File type (EPUB, TXT, SRT)
- Relevant `.env` settings (without API keys)
- Debug logs if available
