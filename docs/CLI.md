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
| `-o, --output` | Output file path | Auto-generated |

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

### EPUB Options

| Option | Description | Default |
|--------|-------------|---------|
| `--fast-mode` | Use Fast Mode (strips formatting) | Off |
| `--no-images` | Don't preserve images in Fast Mode | Off |

### Performance

| Option | Description | Default |
|--------|-------------|---------|
| `-cs, --chunksize` | Lines per chunk | 25 |
| `--timeout` | Request timeout (seconds) | 900 |
| `--context-window` | Context window size | 2048 |

### Display

| Option | Description |
|--------|-------------|
| `--no-color` | Disable colored output |

---

## Examples

### Basic Translation

```bash
# Text file
python translate.py -i book.txt -o book_fr.txt -sl English -tl French

# Subtitles
python translate.py -i movie.srt -o movie_fr.srt -tl French

# EPUB
python translate.py -i novel.epub -o novel_fr.epub -tl French
```

### EPUB with Fast Mode

```bash
python translate.py -i book.epub -o book_fr.epub --fast-mode
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

### Performance Tuning

```bash
# Larger chunks for better context (needs more VRAM)
python translate.py -i book.txt -o book_fr.txt -cs 50

# Smaller chunks for limited hardware
python translate.py -i book.txt -o book_fr.txt -cs 15

# Longer timeout for slow models
python translate.py -i book.txt -o book_fr.txt --timeout 1800
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
MAIN_LINES_PER_CHUNK=25
REQUEST_TIMEOUT=900

# Languages
DEFAULT_SOURCE_LANGUAGE=English
DEFAULT_TARGET_LANGUAGE=French
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (check console output) |

---

## Output Location

By default, translated files are saved in `translated_files/` directory.

Configure with `OUTPUT_DIR` environment variable.
