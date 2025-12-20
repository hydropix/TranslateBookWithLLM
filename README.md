<p align="center">
    <img src="https://github.com/hydropix/TranslateBookWithLLM/blob/main/src/web/static/TBL-Logo.png?raw=true" alt="TBL Logo">
</p>

# TranslateBook with LLM (TBL)

Translate books, subtitles, and documents using AI - locally or in the cloud.

**Formats:** EPUB, SRT, TXT | **Providers:** Ollama (local), OpenRouter, OpenAI, Gemini

---

## Quick Start (Windows)

**Prerequisites:** [Python 3.8+](https://www.python.org/downloads/), [Ollama](https://ollama.com/), [Git](https://git-scm.com/)

```bash
git clone https://github.com/hydropix/TranslateBookWithLLM.git
cd TranslateBookWithLLM
ollama pull qwen3:14b    # Download a model
start.bat                # Launch (auto-installs dependencies)
```

The web interface opens at **http://localhost:5000**

---

## Choosing a Model

| VRAM     | Command                    | Parameters |
|----------|----------------------------|------------|
| 6-10 GB  | `ollama pull qwen3:8b`     | 8B         |
| 10-16 GB | `ollama pull qwen3:14b`    | 14B        |
| 16-24 GB | `ollama pull qwen3:30b`    | 30B        |
| 48+ GB   | `ollama pull qwen3:235b`   | 235B       |

---

## LLM Providers

| Provider | Type | Setup |
|----------|------|-------|
| **Ollama** | Local | [ollama.com](https://ollama.com/) |
| **LM Studio** | Local (OpenAI-compatible) | [lmstudio.ai](https://lmstudio.ai/) |
| **OpenRouter** | Cloud (200+ models) | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **OpenAI** | Cloud | [platform.openai.com](https://platform.openai.com/api-keys) |
| **Gemini** | Cloud | [Google AI Studio](https://makersuite.google.com/app/apikey) |

> **LM Studio / Local OpenAI-compatible servers:** Use `--provider openai` with `--api_endpoint http://localhost:1234/v1/chat/completions`

See [docs/PROVIDERS.md](docs/PROVIDERS.md) for detailed setup instructions.

---

## EPUB Translation Modes

| Mode | Use When |
|------|----------|
| **Standard** (default) | Large model (>12B), formatting is important |
| **Fast Mode** (`--fast-mode`) | Small model (≤12B), reader compatibility issues, simpler is better |

Fast Mode strips HTML and outputs EPUB 2.0 for maximum compatibility. See [docs/FAST_MODE.md](docs/FAST_MODE.md) for details.

---

## Command Line

```bash
# Basic
python translate.py -i book.epub -o book_zh.epub -sl English -tl Chinese

# With Fast Mode
python translate.py -i book.epub -o book_zh.epub --fast-mode

# With OpenRouter
python translate.py -i book.txt -o book_fr.txt --provider openrouter \
    --openrouter_api_key YOUR_KEY -m anthropic/claude-sonnet-4

# With OpenAI
python translate.py -i book.txt -o book_fr.txt --provider openai \
    --openai_api_key YOUR_KEY -m gpt-4o

# With Gemini
python translate.py -i book.txt -o book_fr.txt --provider gemini \
    --gemini_api_key YOUR_KEY -m gemini-2.0-flash

# With LM Studio (or any OpenAI-compatible local server)
python translate.py -i book.txt -o book_fr.txt --provider openai \
    --api_endpoint http://localhost:1234/v1/chat/completions -m your-model
```

### Main Options

| Option | Description | Default |
|--------|-------------|---------|
| `-i, --input` | Input file | Required |
| `-o, --output` | Output file | Auto |
| `-sl, --source_lang` | Source language | English |
| `-tl, --target_lang` | Target language | Chinese |
| `-m, --model` | Model name | mistral-small:24b |
| `--provider` | ollama/openrouter/openai/gemini | ollama |
| `--fast-mode` | Fast Mode for EPUB | Off |

See [docs/CLI.md](docs/CLI.md) for all options and examples.

---

## Configuration (.env)

Copy `.env.example` to `.env` and edit:

```bash
# Provider
LLM_PROVIDER=ollama

# Ollama
API_ENDPOINT=http://localhost:11434/api/generate
DEFAULT_MODEL=mistral-small:24b

# API Keys (if using cloud providers)
OPENROUTER_API_KEY=sk-or-v1-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...

# Performance
MAIN_LINES_PER_CHUNK=25
REQUEST_TIMEOUT=900
```

---

## Docker

```bash
docker build -t translatebook .
docker run -p 5000:5000 -v $(pwd)/translated_files:/app/translated_files translatebook
```

See [DOCKER.md](DOCKER.md) for more options.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Ollama won't connect | Check Ollama is running, test `curl http://localhost:11434/api/tags` |
| Model not found | Run `ollama list`, then `ollama pull model-name` |
| Timeouts | Increase `REQUEST_TIMEOUT` or reduce `MAIN_LINES_PER_CHUNK` |
| EPUB won't open | Try `--fast-mode` |
| Placeholders in output (⟦TAG0⟧) | Use `--fast-mode` |

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for more solutions.

---

## Documentation

| Guide | Description |
|-------|-------------|
| [docs/PROVIDERS.md](docs/PROVIDERS.md) | Detailed provider setup (Ollama, LM Studio, OpenRouter, OpenAI, Gemini) |
| [docs/FAST_MODE.md](docs/FAST_MODE.md) | EPUB Fast Mode explained |
| [docs/CLI.md](docs/CLI.md) | Complete CLI reference |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Problem solutions |
| [DOCKER.md](DOCKER.md) | Docker deployment guide |

---

## Links

- [Report Issues](https://github.com/hydropix/TranslateBookWithLLM/issues)
- [OpenRouter Models](https://openrouter.ai/models)

---

**License:** AGPL-3.0 license
