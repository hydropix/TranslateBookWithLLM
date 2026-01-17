# Command Line Interface (CLI)

Complete reference for the `translate.py` command.

---

## Basic Usage

```bash
python translate.py -i input_file -o output_file
```

---

## Options

### Required

| Option | Description |
|--------|-------------|
| `-i, --input` | Input file (.txt, .epub, .srt) |

### Output

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --output` | Output file path | Auto-generated as `{original} ({target_lang}).{ext}` |

### Languages

| Option | Description | Default |
|--------|-------------|---------|
| `-sl, --source_lang` | Source language | English |
| `-tl, --target_lang` | Target language | Chinese |

### Model & Provider

| Option | Description | Default |
|--------|-------------|---------|
| `-m, --model` | Model name | mistral-small:24b |
| `--provider` | ollama / openrouter / openai / gemini | ollama |
| `--api_endpoint` | API URL | http://localhost:11434/api/generate |

### API Keys

| Option | Description |
|--------|-------------|
| `--openrouter_api_key` | OpenRouter API key |
| `--openai_api_key` | OpenAI API key |
| `--gemini_api_key` | Gemini API key |

### Prompt Options

| Option | Description |
|--------|-------------|
| `--text-cleanup` | Enable OCR/typographic cleanup (fix broken lines, spacing, punctuation) |
| `--refine` | Enable refinement pass: runs a second pass to polish translation quality and literary style |

### TTS (Text-to-Speech)

| Option | Description | Default |
|--------|-------------|---------|
| `--tts` | Generate audio from translated text using Edge-TTS | disabled |
| `--tts-voice` | TTS voice name | Auto-selected based on target language |
| `--tts-rate` | Speech rate adjustment (e.g., `+10%`, `-20%`) | +0% |
| `--tts-bitrate` | Audio bitrate (e.g., `64k`, `96k`) | 48k |
| `--tts-format` | Audio output format: `opus` or `mp3` | opus |

### Display

| Option | Description |
|--------|-------------|
| `--no-color` | Disable colored output |

---

## Examples

### Basic Translation

```bash
# Text file (auto-generates "book (French).txt")
python translate.py -i book.txt -sl English -tl French

# Subtitles (auto-generates "movie (French).srt")
python translate.py -i movie.srt -tl French

# EPUB (auto-generates "novel (French).epub")
python translate.py -i novel.epub -tl French

# Custom output filename
python translate.py -i book.txt -o my_custom_name.txt -tl French
```

### With Different Providers

```bash
# Ollama (default)
python translate.py -i book.txt -o book_fr.txt -m qwen3:14b

# OpenRouter
python translate.py -i book.txt -o book_fr.txt \
    --provider openrouter \
    --openrouter_api_key sk-or-v1-xxx \
    -m anthropic/claude-sonnet-4

# OpenAI
python translate.py -i book.txt -o book_fr.txt \
    --provider openai \
    --openai_api_key sk-xxx \
    -m gpt-4o

# Gemini
python translate.py -i book.txt -o book_fr.txt \
    --provider gemini \
    --gemini_api_key xxx \
    -m gemini-2.0-flash

# OpenAI-compatible server (llama.cpp, LM Studio, vLLM, etc.)
python translate.py -i book.txt -o book_fr.txt \
    --provider openai \
    --api_endpoint http://localhost:8080/v1/chat/completions \
    -m your-model
```

### With Prompt Options

```bash
# OCR cleanup (fix broken lines, spacing from scanned documents)
python translate.py -i scanned_book.txt -tl French --text-cleanup

# Refinement pass for higher quality literary translation
python translate.py -i novel.epub -tl French --refine

# Both options combined
python translate.py -i scanned_book.txt -tl French --text-cleanup --refine
```

### With TTS (Text-to-Speech)

```bash
# Generate audio with auto-selected voice
python translate.py -i book.txt -tl French --tts

# Specify voice and format
python translate.py -i book.txt -tl French --tts --tts-voice fr-FR-DeniseNeural --tts-format mp3

# Adjust speech rate and quality
python translate.py -i book.txt -tl French --tts --tts-rate "+10%" --tts-bitrate 96k
```

---

## Environment Variables

Instead of passing options every time, use a `.env` file:

```bash
# Provider
LLM_PROVIDER=ollama
DEFAULT_MODEL=qwen3:14b
API_ENDPOINT=http://localhost:11434/api/generate

# API Keys
OPENROUTER_API_KEY=sk-or-v1-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...

# Performance
REQUEST_TIMEOUT=900
MAX_TOKENS_PER_CHUNK=400  # Token-based chunking (default: 400 tokens)

# Languages
DEFAULT_SOURCE_LANGUAGE=English
DEFAULT_TARGET_LANGUAGE=French

# TTS
TTS_ENABLED=false
TTS_VOICE=               # Auto-selected if empty
TTS_RATE=+0%
TTS_BITRATE=48k
TTS_OUTPUT_FORMAT=opus
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (check console output) |
