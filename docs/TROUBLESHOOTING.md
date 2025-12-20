# Troubleshooting Guide

Solutions to common problems with TBL.

---

## Connection Issues

### "Connection refused" / "Cannot connect to Ollama"

**Cause**: Ollama is not running.

**Solutions**:
1. Check Ollama icon in system tray
2. Test connection: `curl http://localhost:11434/api/tags`
3. Restart Ollama from Start Menu
4. Check firewall (allow port 11434)

### "Invalid API key"

**Cause**: Wrong or expired API key.

**Solutions**:
1. Verify key is copied correctly (no extra spaces)
2. Check key is active on provider's website
3. Verify you have credits/quota remaining

---

## Model Issues

### "Model not found"

**Cause**: Model not downloaded or wrong name.

**Solutions**:
1. List installed models: `ollama list`
2. Download missing model: `ollama pull model-name`
3. Check exact model name (case-sensitive)

### "Context length exceeded"

**Cause**: Chunk is too large for model's context window.

**Solutions**:
1. Reduce chunk size: `-cs 15` or `MAIN_LINES_PER_CHUNK=15`
2. Increase context window: `OLLAMA_NUM_CTX=8192`

---

## Performance Issues

### "Request timeout"

**Cause**: Request taking too long.

**Solutions**:
1. Increase timeout: `REQUEST_TIMEOUT=1800` (30 min)
2. Reduce chunk size: `MAIN_LINES_PER_CHUNK=15`
3. Try a smaller model
4. Try a cloud provider

### "Out of memory"

**Cause**: Not enough RAM/VRAM for the model.

**Solutions**:
1. Use a smaller model (8B instead of 14B)
2. Reduce context window: `OLLAMA_NUM_CTX=2048`
3. Close other applications
4. Try a cloud provider

---

## EPUB Issues

### "EPUB won't open" / "Invalid EPUB"

**Cause**: Reader rejects the EPUB format.

**Solutions**:
1. Try `--fast-mode`
2. Test with Calibre
3. Validate EPUB: [validator.idpf.org](http://validator.idpf.org/)

### "Placeholders in text" (⟦TAG0⟧)

**Cause**: Model did not preserve HTML tag placeholders.

**Solution**: Use `--fast-mode`

### "Lost formatting"

**Cause**: Fast Mode simplifies formatting by design.

**Solution**: Use Standard Mode (remove `--fast-mode`)

---

## Web Interface Issues

### "Port already in use"

**Cause**: Port 5000 is used by another application.

**Solutions**:
1. Find what's using it: `netstat -an | find "5000"`
2. Change port in `.env`: `PORT=8080`
3. Kill the other process

### "File upload fails"

**Cause**: File too large or wrong format.

**Solutions**:
1. Check file format (.txt, .epub, .srt only)
2. Check file size limits
3. Try a smaller file first

---

## Quick Reference

| Problem | Quick Fix |
|---------|-----------|
| Ollama not connecting | Restart Ollama |
| Model not found | `ollama pull model-name` |
| Timeouts | `REQUEST_TIMEOUT=1800` |
| Out of memory | Try smaller model |
| EPUB broken | Try `--fast-mode` |
| Placeholders visible | Use `--fast-mode` |
| Port in use | Set `PORT=8080` in .env |

---

## Getting Help

1. Check this guide
2. Review console/terminal logs
3. Test with a small file first
4. Open an issue: [GitHub Issues](https://github.com/hydropix/TranslateBookWithLLM/issues)

When reporting issues, include:
- Operating system
- Model used
- Error message
- File type (EPUB, TXT, SRT)
