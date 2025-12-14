<p align="center">
    <img src="https://github.com/hydropix/TranslateBookWithLLM/blob/main/src/web/static/TBL-Logo.png?raw=true" alt="Application Logo">
</p>

# 📚 TranslateBook with LLM (TBL)

**Translate entire books, subtitles, and large texts with AI - simply and efficiently.**

TBL is an application that lets you translate large volumes of text using Language Models (LLMs). Whether you want to translate an ebook, movie subtitles, or long documents, TBL does it automatically while preserving formatting.

## ✨ Why use TBL?

- 🎯 **Easy to use**: Intuitive web interface, no technical skills required
- 🔒 **Private & Local**: Use Ollama to translate without sending your texts to the internet
- 💰 **Cost-effective**: Free with Ollama, controlled costs with cloud APIs
- 📖 **Preserves formatting**: EPUB files keep their structure, subtitles keep their timings
- 🚀 **Batch translation**: Translate multiple files at once
- 🌍 **Multi-language**: Translate between any languages

## 🎯 Use Cases

- Translate ebooks (EPUB)
- Translate movie subtitles (SRT)
- Translate long documents

---

## 🚀 Quick Start

### ⚡ One-Click Installation (Windows) - **RECOMMENDED**

**Prerequisites** (install once):

| Software | Download | Note |
|----------|----------|------|
| **Python 3.8+** | [python.org](https://www.python.org/downloads/) | ⚠️ Check "Add Python to PATH" |
| **Ollama** | [ollama.com](https://ollama.com/) | Runs AI models locally (free) |
| **Git** | [git-scm.com](https://git-scm.com/download/win) | Default settings |

**Installation & Launch:**

```bash
# Download TBL (one time only)
git clone https://github.com/hydropix/TranslateBookWithLLM.git
cd TranslateBookWithLLM

# Download an AI model (choose based on your GPU VRAM)
ollama pull qwen3:30b

# Launch TBL - EVERYTHING ELSE IS AUTOMATIC!
start.bat
```

🎉 **That's it!** The web interface opens automatically at **http://localhost:5000**

### What does `start.bat` do automatically?

✅ Creates Python virtual environment
✅ Installs all dependencies
✅ Checks for updates from Git
✅ Updates dependencies if needed
✅ Creates configuration files
✅ Launches the web interface

**Next time, just double-click `start.bat`!**

---

### 📊 Choosing the Right Model

[Ollama Search](https://ollama.com/search)

**Qwen3 Models by VRAM (GPU Memory):**

```
6-10 GB  → ollama pull qwen3:8b      (5.2 GB, basic translations)
10-16 GB → ollama pull qwen3:14b     (9.3 GB, good translations)
16-24 GB → ollama pull qwen3:30b     (19 GB, very good translations) ⭐ RECOMMENDED
48+ GB   → ollama pull qwen3:235b    (142 GB, professional quality)
```

```bash
# Check your installed models
ollama list
```

---

## 📖 Web Interface Guide

### Basic Configuration

1. **Choose your LLM Provider**:

   - **Ollama** (recommended): Free, private, works offline
   - **OpenRouter** (recommended cloud): Access to 200+ models (Claude, GPT-4, Llama, Mistral...) with unified billing
   - **OpenAI**: Paid, requires API key, high quality (GPT-4, etc.)
   - **Google Gemini**: Paid, requires API key, fast and efficient

2. **Select your Model**:
   
   - The list fills automatically based on your provider
   - Click 🔄 to refresh the list

3. **Languages**:
   
   - **Source Language**: The language of your original text
   - **Target Language**: The language to translate into
   - Use "Other" to specify any language

4. **Add your Files**:
   
   - Drag and drop or click to select
   - Accepted formats: `.txt`, `.epub`, `.srt`
   - You can add multiple files at once

5. **Start Translation**:
   
   - Click "Start Translation"
   - Follow real-time progress
   - Download translated files when complete

### 📚 Translating EPUB Files (Ebooks)

TBL offers **two modes** for translating EPUB files:

#### Standard Mode (Default)

- ✅ Preserves all original formatting (bold, italic, tables, etc.)
- ✅ Keeps images and complex structure
- ⚠️ Requires a capable model (>12 billion parameters)
- ⚠️ May have issues with strict EPUB readers

**When to use**: You have a good model and formatting is important.

#### Fast Mode ⭐ (Recommended for Compatibility)

- ✅ **Maximum compatibility** with all EPUB readers
- ✅ Works with **small models** (7B, 8B parameters)
- ✅ **No issues** with tags or placeholders
- ✅ Creates standard EPUB 2.0 output
- ❌ Complex formatting is simplified (basic text only)

**When to use**:

- You're using a small model (qwen2:7b, llama3:8b, etc.)
- You're having problems with Standard Mode
- Your EPUB reader is strict (Aquile Reader, Adobe Digital Editions)
- Formatting is not critical

💡 **Tip**: TBL automatically detects small models and recommends Fast Mode!

**How to enable Fast Mode**:

- ✅ Check the "Fast Mode (Recommended for small models)" checkbox in the web interface
- Or use `--fast-mode` flag in command line

### 🎬 Translating Subtitles (SRT)

- ✅ **Timings are preserved** exactly
- ✅ Numbering remains intact
- ✅ Only the text is translated
- ✅ SRT format perfectly maintained

Simply drag your `.srt` file and start translation!

### 🎛️ Advanced Settings

Click "▼ Advanced Settings" to access:

**Chunk Size** (5-200 lines)

- Controls how many lines are translated together
- Larger = better context, but slower (make sure you have enough VRAM)
- Recommended: 25 for most cases

**Timeout** (30-600 seconds)

- Maximum wait time per request
- Increase if you're experiencing timeouts
- Recommended: 180s for web, 900s for CLI

**Context Window** (1024-32768 tokens)

- The context adjusts automatically, so this setting is no longer very important.
- Recommended: 2048.

**Max Retries** (1-5)

- Number of retry attempts on failure
- Recommended: 2

**Auto-Adjustment**

- ✅ Enabled by default
- Automatically adapts parameters if needed
- Leave enabled unless you have specific needs

**Output Filename Pattern**

- Customize translated file names
- Example: `{originalName}_FR.{ext}`
- Placeholders: `{originalName}`, `{ext}`

### 📦 Batch Translation

You can translate **multiple files at once**:

1. Add all your files ("Add Files" button)
2. Each file appears in the list with its status
3. Click "Start Batch" to translate all sequentially
4. Follow the progress of each file individually

---

## 💻 Command Line Interface (CLI)

For advanced users or automation:

### Basic Command

```bash
python translate.py -i input_file.txt -o output_file.txt
```

### Available Options

| Option               | Description                        | Default                             |
| -------------------- | ---------------------------------- | ----------------------------------- |
| `-i, --input`        | 📄 Input file (.txt, .epub, .srt)  | **Required**                        |
| `-o, --output`       | 📄 Output file                     | Auto-generated                      |
| `-sl, --source_lang` | 🌍 Source language                 | English                             |
| `-tl, --target_lang` | 🌍 Target language                 | Chinese                             |
| `-m, --model`        | 🤖 LLM model to use                | mistral-small:24b                   |
| `-cs, --chunksize`   | 📏 Lines per chunk                 | 25                                  |
| `--provider`         | 🏢 Provider (ollama/openrouter/gemini/openai) | ollama                              |
| `--api_endpoint`     | 🔗 API URL                         | http://localhost:11434/api/generate |
| `--openrouter_api_key` | 🔑 OpenRouter API key            | -                                   |
| `--gemini_api_key`   | 🔑 Gemini API key                  | -                                   |
| `--openai_api_key`   | 🔑 OpenAI API key                  | -                                   |
| `--fast-mode`        | 📚 Fast Mode for EPUB              | Disabled                            |
| `--no-color`         | 🎨 Disable colors                  | Colors enabled                      |

### Practical Examples

**Translate an EPUB book (Fast Mode)**

```bash
python translate.py -i book.epub -o book_zh.epub -sl English -tl Chinese --fast-mode
```

**Translate with OpenRouter (access to Claude, GPT-4, Llama, etc.)**

```bash
python translate.py -i book.txt -o book_fr.txt \
    --provider openrouter \
    --openrouter_api_key sk-or-v1-your-key \
    -m anthropic/claude-sonnet-4 \
    -sl English -tl French
```

**Translate with OpenAI GPT-4**

```bash
python translate.py -i text.txt -o text_es.txt \
    --provider openai \
    --openai_api_key sk-your-key-here \
    --api_endpoint https://api.openai.com/v1/chat/completions \
    -m gpt-4o \
    -sl English -tl Spanish
```

**Translate with Google Gemini**

```bash
python translate.py -i document.txt -o document_de.txt \
    --provider gemini \
    --gemini_api_key your-gemini-key \
    -m gemini-2.0-flash \
    -sl French -tl German
```

**Translate subtitles**

```bash
python translate.py -i movie.srt -o movie_zh.srt -sl English -tl Chinese
```

**Translation with larger chunks for better context**

```bash
python translate.py -i novel.txt -o novel_zh.txt -cs 50
```

---

## 🔌 LLM Providers (AI Models)

TBL supports four types of providers:

### 1. 🏠 Ollama (Local - Free)

**Advantages**:

- ✅ Totally free
- ✅ Works offline
- ✅ Your texts stay private (nothing sent to the internet)
- ✅ No usage limits

**Disadvantages**:

- ⚠️ Requires a powerful computer (GPU recommended)
- ⚠️ Slower than cloud APIs
- ⚠️ Quality varies by model

### 2. 🌐 OpenRouter (Cloud - Recommended)

**The best of all worlds**: Access 200+ models from multiple providers (Anthropic, OpenAI, Google, Meta, Mistral...) through a single API key and unified billing.

🔗 **Browse all available models**: [openrouter.ai/models](https://openrouter.ai/models)

**Advantages**:

- ✅ **200+ models** in one place (Claude, GPT-4, Llama, Gemini, Mistral...)
- ✅ **Free models available** (Gemini Flash, Llama 70B, etc.)
- ✅ **Precise real-time cost tracking** displayed in TBL interface
- ✅ **Single API key** for all providers
- ✅ **No commitment** - pay only for what you use
- ✅ **Models sorted by price** in TBL (cheapest first)
- ✅ Easy to compare models and find the best value

**Disadvantages**:

- ⚠️ Requires internet connection
- ⚠️ Your texts are sent to model providers

**Popular models** (sorted by cost):

| Model | Quality | Cost (per 1M tokens) |
|-------|---------|---------------------|
| `google/gemini-2.0-flash-exp:free` | Good | **Free** |
| `meta-llama/llama-3.3-70b-instruct` | Very Good | ~$0.10 |
| `google/gemini-2.0-flash-001` | Good | ~$0.10 |
| `openai/gpt-4o-mini` | Very Good | ~$0.60 |
| `anthropic/claude-3-5-haiku-20241022` | Very Good | ~$1.00 |
| `anthropic/claude-sonnet-4` | Excellent | ~$3.00 |
| `openai/gpt-4o` | Excellent | ~$5.00 |

🔗 **Full model list with pricing**: [openrouter.ai/models](https://openrouter.ai/models)

**💰 Real Example - 400-page EPUB book translation**:
- Model: `openai/gpt-4o` (excellent quality)
- Cost: **less than €2** (~$2)
- TBL displays the exact cost in real-time during translation, so you always know precisely what you're spending

**Setup**:

1. Get an API key at [openrouter.ai/keys](https://openrouter.ai/keys)

2. **Web Interface**:

   - Select "OpenRouter (200+ models)"
   - Enter your API key
   - Models load automatically (sorted by price, text-only models filtered)
   - 💰 **Cost is displayed precisely in real-time** during translation

3. **Command Line**:

   ```bash
   python translate.py -i book.txt -o book_zh.txt \
       --provider openrouter \
       --openrouter_api_key sk-or-v1-your-key \
       -m anthropic/claude-sonnet-4 \
       -sl English -tl Chinese
   ```

4. **Environment Variable** (recommended):

   ```bash
   # In .env file
   OPENROUTER_API_KEY=sk-or-v1-your-key
   OPENROUTER_MODEL=anthropic/claude-sonnet-4
   ```

💡 **Tip**: Start with free models like `google/gemini-2.0-flash-exp:free` to test, then upgrade to premium models for better quality!

### 3. ☁️ OpenAI (Cloud - Paid)

**Advantages**:

- ✅ Excellent translation quality
- ✅ Fast
- ✅ No powerful hardware needed
- ✅ Very capable models (GPT-4, etc.)

**Disadvantages**:

- ⚠️ Paid (cost per token)
- ⚠️ Requires internet connection
- ⚠️ Your texts are sent to OpenAI

**Available models**:

- `gpt-4o` - Latest version, very capable
- `gpt-4o-mini` - More economical, still excellent
- `gpt-4-turbo` - Turbo version of GPT-4
- `gpt-3.5-turbo` - Most economical

**Setup**:

1. Get an API key at [platform.openai.com](https://platform.openai.com/api-keys)

2. **Web Interface**:
   
   - Select "OpenAI" in the dropdown
   - Enter your API key
   - Endpoint is automatically configured

3. **Command Line**:
   
   ```bash
   python translate.py -i book.txt -o book_zh.txt \
    --provider openai \
    --openai_api_key sk-your-key \
    --api_endpoint https://api.openai.com/v1/chat/completions \
    -m gpt-4o
   ```

💰 **Estimated cost**: About $0.50 - $2.00 for a 300-page book with GPT-4o-mini.

### 4. 🌐 Google Gemini (Cloud - Paid)

**Advantages**:

- ✅ Very fast
- ✅ Excellent quality/price ratio
- ✅ Generous free quota

**Disadvantages**:

- ⚠️ Requires internet connection
- ⚠️ Quota limits

**Available models**:

- `gemini-2.0-flash` - Fast and efficient (recommended)
- `gemini-1.5-pro` - More capable, slower
- `gemini-1.5-flash` - Balanced

**Setup**:

1. Get an API key at [Google AI Studio](https://makersuite.google.com/app/apikey)

2. **Web Interface**:
   
   - Select "Google Gemini"
   - Enter your API key
   - Choose your model

3. **Command Line**:
   
   ```bash
   python translate.py -i document.txt -o document_zh.txt \
    --provider gemini \
    --gemini_api_key your-key \
    -m gemini-2.0-flash
   ```

💡 **Tip**: Gemini offers a generous monthly free quota, perfect for testing!

---

## 💾 Windows Installer

For the easiest installation experience on Windows, download the pre-built installer:

### Download Options

Go to the [Releases page](https://github.com/hydropix/TranslateBookWithLLM/releases) and download:

| File | Description |
|------|-------------|
| `TranslateBookWithLLM-Setup-x.x.x.exe` | **Installer** - Recommended for most users |
| `TranslateBookWithLLM-Portable-x.x.x.zip` | **Portable** - No installation needed, just unzip and run |

### Installation Steps

1. **Download** the installer (`.exe`) from the Releases page
2. **Run** the installer and follow the wizard
3. **Configure** the `.env` file in the installation folder with your API keys
4. **Launch** TranslateBookWithLLM from the Start Menu or Desktop shortcut
5. **Open** your browser to `http://localhost:5000`

### What's Included

- ✅ Complete application (no Python installation required)
- ✅ Web interface ready to use
- ✅ Configuration file template (`.env.example`)
- ✅ Documentation

### Requirements

- **Windows 10/11** (64-bit)
- **Ollama** (for local translation) - [Download here](https://ollama.com/)
- Or API keys for cloud providers (OpenRouter, OpenAI, Gemini)

---

## 🐳 Docker Installation

For simplified installation with Docker:

### Quick Method

```bash
# Build the image
docker build -t translatebook .

# Run the container
docker run -p 5000:5000 -v $(pwd)/translated_files:/app/translated_files translatebook
```

The web interface will be accessible at **http://localhost:5000**

### With Custom Port

```bash
docker run -p 8080:5000 -e PORT=5000 -v $(pwd)/translated_files:/app/translated_files translatebook
```

Access at **http://localhost:8080**

### With Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3'
services:
  translatebook:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./translated_files:/app/translated_files
    environment:
      - PORT=5000
      - API_ENDPOINT=http://localhost:11434/api/generate
      - DEFAULT_MODEL=mistral-small:24b
```

Then run:

```bash
docker-compose up
```

💡 **Note**: Translated files will be saved in `./translated_files` on your machine.

---

## ⚙️ Advanced Configuration

### Configuration File (.env)

You can create a `.env` file at the project root to set default values:

```bash
# Copy the example file
cp .env.example .env

# Edit with your parameters
```

**Important variables**:

```bash
# Default LLM provider
LLM_PROVIDER=ollama  # or openrouter, gemini, openai

# Ollama configuration
API_ENDPOINT=http://localhost:11434/api/generate
DEFAULT_MODEL=mistral-small:24b
OLLAMA_NUM_CTX=8192  # Context window size

# OpenRouter configuration (recommended for cloud)
OPENROUTER_API_KEY=sk-or-v1-your-key
OPENROUTER_MODEL=anthropic/claude-sonnet-4

# OpenAI configuration
OPENAI_API_KEY=sk-your-key
# Endpoint configured automatically

# Gemini configuration
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-2.0-flash

# Default languages
DEFAULT_SOURCE_LANGUAGE=English
DEFAULT_TARGET_LANGUAGE=Chinese

# Translation parameters
MAIN_LINES_PER_CHUNK=25
REQUEST_TIMEOUT=900
MAX_TRANSLATION_ATTEMPTS=3
RETRY_DELAY_SECONDS=5

# Automatic adjustment (recommended)
AUTO_ADJUST_CONTEXT=true

# Web server
PORT=5000
HOST=127.0.0.1
OUTPUT_DIR=translated_files
```

## 🔧 Troubleshooting

### Common Issues

#### ❌ Web interface won't start

**Symptom**: Error when launching `python translation_api.py`

**Solutions**:

1. Check that the port is free:
   
   ```bash
   netstat -an | find "5000"
   ```
2. Change the port in `.env`:

   ```bash
   PORT=8080
   ```

#### ❌ Ollama won't connect

**Symptom**: "Connection refused" or "Cannot connect to Ollama"

**Solutions**:

1. Check that Ollama is running (icon in system tray)
2. Test the connection:
   
   ```bash
   curl http://localhost:11434/api/tags
   ```
3. Restart Ollama from Start Menu
4. Check your firewall (allow port 11434)

#### ❌ Model not found

**Symptom**: "Model 'xxx' not found"

**Solutions**:

1. List your installed models:
   
   ```bash
   ollama list
   ```
2. Download the missing model:
   
   ```bash
   ollama pull model-name
   ```
3. Use an available model from the list

#### ❌ Frequent timeouts

**Symptom**: Translation stops with "Request timeout"

**Solutions**:

1. Increase timeout in advanced options (web) or `.env`:
   
   ```bash
   REQUEST_TIMEOUT=1800
   ```
2. Reduce chunk size:
   
   ```bash
   MAIN_LINES_PER_CHUNK=15
   ```
3. Use a faster model (qwen2:7b instead of mistral-small:24b)

#### ❌ Poor translation quality

**Symptom**: Translation is incorrect, inconsistent, or weird

**Solutions**:

1. **Use a better model**:
   
   - Ollama: `mistral-small:24b` instead of `qwen2:7b`
   - Switch to OpenAI `gpt-4o` or Gemini `gemini-1.5-pro`
   
   

2. **For EPUB with small models**: Use Fast Mode
   
   ```bash
   --fast-mode
   ```

#### ❌ EPUB issues

**Symptom**: Translated EPUB file won't open or is broken

**Solutions**:

1. **Use Fast Mode** (most reliable solution):
   
   ```bash
   python translate.py -i book.epub -o book_zh.epub --fast-mode
   ```

2. **Check your EPUB reader**: Test with Calibre (more permissive)

3. **If using a small model** (qwen2:7b, llama3:8b): Fast Mode required

4. **If placeholders remain** (⟦TAG0⟧): This is a bug in Standard Mode, switch to Fast Mode

#### ❌ OpenAI/Gemini API errors

**Symptom**: "Invalid API key" or "Quota exceeded"

**Solutions**:

1. **Check your API key**: Copy-paste correctly
2. **Check your quota/credit**:
   - OpenAI: [platform.openai.com/usage](https://platform.openai.com/usage)
   - Gemini: [console.cloud.google.com](https://console.cloud.google.com)
3. **Check endpoint** (OpenAI):
   
   ```
   https://api.openai.com/v1/chat/completions
   ```

#### ❌ Memory errors

**Symptom**: "Out of memory" or crash with large files

**Solutions**:

1. Reduce chunk size:
   
   ```bash
   MAIN_LINES_PER_CHUNK=10
   ```
2. Reduce context window:
   
   ```bash
   OLLAMA_NUM_CTX=4096
   ```
3. Use a smaller model
4. Close other applications

### Common Error Messages

| Message                   | Meaning              | Solution                                     |
| ------------------------- | -------------------- | -------------------------------------------- |
| `Connection refused`      | Ollama not running   | Start Ollama                                 |
| `Model not found`         | Model not downloaded | `ollama pull model-name`                     |
| `Request timeout`         | Request too long     | Increase timeout or reduce chunk size        |
| `Invalid API key`         | Incorrect API key    | Check your key                               |
| `Context length exceeded` | Prompt too large     | Reduce chunk size or increase context window |
| `Quota exceeded`          | API limit reached    | Wait or add credits                          |

---

## ❓ FAQ (Frequently Asked Questions)

### General

**Q: Is it really free?**
A: With Ollama, yes! OpenRouter also offers free models (Gemini Flash, Llama 70B). You only pay for premium models.

**Q: Are my texts sent to the internet?**
A: With Ollama, no. With OpenRouter/OpenAI/Gemini, yes (sent to respective servers).

**Q: How long does it take?**
A: Very variable depending on length, model, and your machine. A 300-page book takes between 30 minutes (cloud) and 3 hours (Ollama with small model).

**Q: What's the translation quality?**
A: Depends on the model. Claude Sonnet 4 and GPT-4o are excellent, mistral-small:24b is very good, small models (7B) are decent for simple text.

### EPUB

**Q: Simple or Standard Mode for my EPUB?**
A:

- **Fast Mode** if: small model (≤12B), strict reader, or you have problems
- **Standard Mode** if: large model (>12B) and complex formatting is important

**Q: Does Fast Mode lose all formatting?**
A: Basic structure is preserved (paragraphs, chapters), but advanced formatting (complex tables, CSS) is simplified.

**Q: Why does TBL recommend Fast Mode with my model?**
A: Your model has ≤12 billion parameters. Small models struggle with the placeholder system in Standard Mode.

### Performance

**Q: How to speed up translation?**
A:

1. Use a cloud model (OpenRouter/OpenAI/Gemini)
2. Reduce chunk size (`-cs 15`)
3. Use a smaller model (qwen2:7b)
4. With Ollama: use a GPU

**Q: How to improve quality?**
A:

1. Use a better model (claude-sonnet-4 via OpenRouter, gpt-4o, mistral-small:24b)
2. Increase chunk size (`-cs 40`)
3. Increase context window (`OLLAMA_NUM_CTX=16384`)

**Q: Is my computer powerful enough?**
A: For Ollama:

- Minimum: 16 GB RAM, recent CPU (7B models)
- Recommended: 32 GB RAM, NVIDIA GPU (24B models)
- Alternative: Use OpenRouter (cloud) - works on any computer!

### Technical

**Q: Can I translate multiple files simultaneously?**
A: In the web interface, yes with batch mode. In CLI, no (launch multiple separate commands).

**Q: Where are translated files stored?**
A: In the `translated_files/` folder by default (configurable with `OUTPUT_DIR`).

**Q: Can I customize translation prompts?**
A: Yes, edit `prompts.py`, but it's technical.

### Security & Privacy

**Q: Are my files stored on your servers?**
A: No, TBL runs on YOUR machine. Nothing is sent elsewhere (except if you use OpenRouter/OpenAI/Gemini).

**Q: What happens to my files during translation?**
A: TBL runs entirely on your local machine. Your files are processed locally by the web server running on your computer:
- **With Ollama**: 100% local - nothing leaves your machine
- **With OpenRouter/OpenAI/Gemini**: Only the text content is sent to their APIs for translation (consult their data policies)
- Source files are deleted after translation. Translated files remain in `translated_files/` until you delete them.

**Q: Are there file size limits?**
A: Yes, configurable. Default limits are set to ensure smooth operation. Modifiable in `.env` or code if needed.

---

## 🤝 Contribution & Support

### Getting Help

1. **Check this FAQ** and the Troubleshooting section
2. **Check logs**: Detailed errors are in the console/terminal
3. **Test with a small file**: Isolate the problem
4. **Check your configuration**: Model downloaded? Valid API key?

### Reporting a Bug

If you find a bug, open an issue on [GitHub](https://github.com/hydropix/TranslateBookWithLLM/issues) with:

- Description of the problem
- Example file (if possible)
- Error logs
- Your configuration (model, OS, etc.)

---

## 📄 License

This project is open-source. See the LICENSE file for details.

---

**Happy translating! 📚✨**
