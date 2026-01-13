<p align="center">
    <img src="https://github.com/hydropix/TranslateBookWithLLM/blob/main/src/web/static/TBL-Logo.png?raw=true" alt="TBL Logo">
</p>

# TranslateBook with LLM (TBL)

Translate books, subtitles, and documents using AI - locally or in the cloud.

**Formats:** EPUB, SRT, TXT | **Providers:** Ollama (local), OpenRouter, OpenAI, Gemini

> 📊 **[Translation Quality Benchmarks](https://github.com/hydropix/TranslateBookWithLLM/wiki)** — Find the best model for your target language.

---

## Quick Start

**Prerequisites:** [Python 3.8+](https://www.python.org/downloads/), [Ollama](https://ollama.com/), [Git](https://git-scm.com/)

```bash
git clone https://github.com/hydropix/TranslateBookWithLLM.git
cd TranslateBookWithLLM
ollama pull qwen3:14b    # Download a model

# Windows
start.bat

# Mac/Linux
chmod +x start.sh && ./start.sh
```

The web interface opens at **http://localhost:5000**

---

## Choosing a Model

| VRAM | Model | Best For |
|------|-------|----------|
| 8 GB | `gemma3:12b` | Spanish, Portuguese, European |
| 24 GB | `mistral-small:24b` | French |
| 24 GB | `gemma3:27b` | Japanese, Korean, Arabic, most languages |
| 24 GB | `qwen3:30b-instruct` | Chinese (Simplified/Traditional) |

> 📊 **[Full benchmarks](https://github.com/hydropix/TranslateBookWithLLM/wiki)** — 11 models × 19 languages with accuracy, fluency & style scores.

---

## LLM Providers

| Provider | Type | Setup |
|----------|------|-------|
| **Ollama** | Local | [ollama.com](https://ollama.com/) |
| **OpenAI-Compatible** | Local | llama.cpp, LM Studio, vLLM, LocalAI... |
| **OpenRouter** | Cloud (200+ models) | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **OpenAI** | Cloud | [platform.openai.com](https://platform.openai.com/api-keys) |
| **Gemini** | Cloud | [Google AI Studio](https://makersuite.google.com/app/apikey) |

> **OpenAI-Compatible servers:** Use `--provider openai` with your server's endpoint (e.g., llama.cpp: `http://localhost:8080/v1/chat/completions`, LM Studio: `http://localhost:1234/v1/chat/completions`)

See [docs/PROVIDERS.md](docs/PROVIDERS.md) for detailed setup instructions.

---

## Command Line

```bash
# Basic (auto-generates "book (Chinese).epub")
python translate.py -i book.epub -sl English -tl Chinese

# With OpenRouter
python translate.py -i book.txt --provider openrouter \
    --openrouter_api_key YOUR_KEY -m anthropic/claude-sonnet-4 -tl French

# With OpenAI
python translate.py -i book.txt --provider openai \
    --openai_api_key YOUR_KEY -m gpt-4o -tl French

# With Gemini
python translate.py -i book.txt --provider gemini \
    --gemini_api_key YOUR_KEY -m gemini-2.0-flash -tl French

# With local OpenAI-compatible server (llama.cpp, LM Studio, vLLM, etc.)
python translate.py -i book.txt --provider openai \
    --api_endpoint http://localhost:8080/v1/chat/completions -m your-model -tl French
```

### Main Options

| Option | Description | Default |
|--------|-------------|---------|
| `-i, --input` | Input file | Required |
| `-o, --output` | Output file | Auto: `{name} ({lang}).{ext}` |
| `-sl, --source_lang` | Source language | English |
| `-tl, --target_lang` | Target language | Chinese |
| `-m, --model` | Model name | mistral-small:24b |
| `--provider` | ollama/openrouter/openai/gemini | ollama |

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
REQUEST_TIMEOUT=900
MAX_TOKENS_PER_CHUNK=400  # Token-based chunking (default: 400 tokens)
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

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for more solutions.

---

## Documentation

| Guide | Description |
|-------|-------------|
| [docs/PROVIDERS.md](docs/PROVIDERS.md) | Detailed provider setup (Ollama, LM Studio, OpenRouter, OpenAI, Gemini) |
| [docs/CLI.md](docs/CLI.md) | Complete CLI reference |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Problem solutions |
| [DOCKER.md](DOCKER.md) | Docker deployment guide |

---

## Links

- [Report Issues](https://github.com/hydropix/TranslateBookWithLLM/issues)
- [OpenRouter Models](https://openrouter.ai/models)

---

**License:** AGPL-3.0
