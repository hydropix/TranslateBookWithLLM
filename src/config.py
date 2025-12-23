"""
Centralized configuration class
"""
import os
import sys
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Setup debug logger for configuration
_config_logger = logging.getLogger('config')

# Check for DEBUG_MODE early (before .env is loaded, check environment)
_debug_mode = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
if _debug_mode:
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    _config_logger.setLevel(logging.DEBUG)
    _config_logger.debug("🔍 DEBUG_MODE enabled - verbose logging active")

# Get config directory (current working directory)
_config_dir = Path.cwd()

# Check if .env file exists and provide helpful guidance
_env_file = _config_dir / '.env'
_env_example = _config_dir / '.env.example'
_env_exists = _env_file.exists()
_cwd = Path.cwd()

if _debug_mode:
    _config_logger.debug(f"📁 Current working directory: {_cwd}")
    _config_logger.debug(f"📁 Looking for .env at: {_env_file.absolute()}")
    _config_logger.debug(f"📁 .env exists: {_env_exists}")

if not _env_exists:
    print("\n" + "="*70)
    print("⚠️  WARNING: .env configuration file not found")
    print("="*70)
    print("\nThe application will run with default settings, but you may need to")
    print("configure it for your specific setup.\n")

    if _env_example.exists():
        print("📋 QUICK SETUP:")
        print(f"   1. Copy the template: copy .env.example .env")
        print(f"   2. Edit .env to match your configuration")
        print(f"   3. Restart the application\n")
    else:
        print("📋 MANUAL SETUP:")
        print(f"   1. Create a .env file in: {Path.cwd()}")
        print(f"   2. Add your configuration (see documentation)")
        print(f"   3. Restart the application\n")

    print("🔧 DEFAULT SETTINGS BEING USED:")
    print(f"   • API Endpoint: http://localhost:11434/api/generate")
    print(f"   • LLM Provider: ollama")
    print(f"   • Model: qwen3:14b")
    print(f"   • Port: 5000")
    print(f"\n💡 TIP: If using a remote server or different provider, you MUST")
    print(f"   create a .env file with the correct settings.\n")
    print("="*70)
    print("Press Ctrl+C to stop and configure, or wait 5 seconds to continue...")
    print("="*70 + "\n")

    # Give user time to read and react
    import time
    try:
        time.sleep(5)
    except KeyboardInterrupt:
        print("\n\n⏹️  Startup cancelled by user. Please configure .env and try again.\n")
        sys.exit(0)

# Load .env file if it exists
_dotenv_result = load_dotenv(_env_file)
if _debug_mode:
    _config_logger.debug(f"📁 load_dotenv() returned: {_dotenv_result}")
    _config_logger.debug(f"📁 Loaded .env from: {_env_file.absolute()}")

# Load from environment variables with defaults
API_ENDPOINT = os.getenv('API_ENDPOINT', 'http://localhost:11434/api/generate')
DEFAULT_MODEL = os.getenv('DEFAULT_MODEL', 'qwen3:14b')
PORT = int(os.getenv('PORT', '5000'))
MAIN_LINES_PER_CHUNK = int(os.getenv('MAIN_LINES_PER_CHUNK', '25'))
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '900'))
OLLAMA_NUM_CTX = int(os.getenv('OLLAMA_NUM_CTX', '2048'))
MAX_TRANSLATION_ATTEMPTS = int(os.getenv('MAX_TRANSLATION_ATTEMPTS', '2'))
RETRY_DELAY_SECONDS = int(os.getenv('RETRY_DELAY_SECONDS', '2'))

# Context optimization settings
MIN_RECOMMENDED_NUM_CTX = 4096  # Minimum recommended context for chunk_size=25
SAFETY_MARGIN = 1.1  # 10% safety margin for token estimation
AUTO_ADJUST_CONTEXT = os.getenv("AUTO_ADJUST_CONTEXT", "true").lower() == "true"
MIN_CHUNK_SIZE = int(os.getenv("MIN_CHUNK_SIZE", "5"))
MAX_CHUNK_SIZE = int(os.getenv("MAX_CHUNK_SIZE", "100"))

# Token-based chunking configuration
# When enabled, uses tiktoken to count tokens instead of lines for more consistent chunk sizes
USE_TOKEN_CHUNKING = os.getenv('USE_TOKEN_CHUNKING', 'true').lower() == 'true'
MAX_TOKENS_PER_CHUNK = int(os.getenv('MAX_TOKENS_PER_CHUNK', '800'))
SOFT_LIMIT_RATIO = float(os.getenv('SOFT_LIMIT_RATIO', '0.8'))

# LLM Provider configuration
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'ollama')  # 'ollama', 'gemini', 'openai', or 'openrouter'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

# OpenRouter configuration (access to 200+ models)
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'anthropic/claude-sonnet-4')
OPENROUTER_API_ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions'

# SRT-specific configuration
SRT_LINES_PER_BLOCK = int(os.getenv('SRT_LINES_PER_BLOCK', '5'))
SRT_MAX_CHARS_PER_BLOCK = int(os.getenv('SRT_MAX_CHARS_PER_BLOCK', '500'))

# Translation signature configuration
# This adds a discrete attribution to translations to support the project.
# The signature is non-intrusive: EPUB metadata, text file footer, or SRT comment.
# Please consider keeping this enabled to help others discover this free, open-source tool!
# Your support helps maintain and improve the project. Thank you!
SIGNATURE_ENABLED = os.getenv('SIGNATURE_ENABLED', 'true').lower() == 'true'
PROJECT_NAME = "TranslateBook with LLM (TBL)"
PROJECT_GITHUB = "https://github.com/hydropix/TranslateBookWithLLM"
SIGNATURE_VERSION = "1.0"

# Fast Mode Image Preservation
# When enabled, images from the original EPUB are preserved in fast mode output
FAST_MODE_PRESERVE_IMAGES = os.getenv('FAST_MODE_PRESERVE_IMAGES', 'true').lower() == 'true'
# Marker used to track image positions in text (sent to LLM, must be preserved)
# Format: [IMG001] - minimal format for maximum LLM reliability
IMAGE_MARKER_PREFIX = "[IMG"
IMAGE_MARKER_SUFFIX = "]"

# Fast Mode Formatting Preservation
# When enabled, inline formatting (bold, italic) is preserved using markers
FAST_MODE_PRESERVE_FORMATTING = os.getenv('FAST_MODE_PRESERVE_FORMATTING', 'true').lower() == 'true'
# Markers for inline formatting - designed to be simple and LLM-friendly
# These wrap text that should be formatted: [I]italic text[/I], [B]bold text[/B]
FORMAT_ITALIC_START = "[I]"
FORMAT_ITALIC_END = "[/I]"
FORMAT_BOLD_START = "[B]"
FORMAT_BOLD_END = "[/B]"
# Horizontal rule marker (standalone, no content)
FORMAT_HR_MARKER = "[HR]"

# Default languages from environment
DEFAULT_SOURCE_LANGUAGE = os.getenv('DEFAULT_SOURCE_LANGUAGE', 'English')
DEFAULT_TARGET_LANGUAGE = os.getenv('DEFAULT_TARGET_LANGUAGE', 'Chinese')

# ============================================================================
# PROMPT OPTIONS CONFIGURATION
# ============================================================================
# These options control which optional sections are included in the system prompt.
# Each option can be enabled/disabled via the web interface or CLI.

# Technical Content Preservation (for technical documents)
# When enabled, instructs the LLM to NOT translate code, paths, URLs, etc.
PROMPT_PRESERVE_TECHNICAL_CONTENT = os.getenv('PROMPT_PRESERVE_TECHNICAL_CONTENT', 'false').lower() == 'true'

# Server configuration
HOST = os.getenv('HOST', '127.0.0.1')
OUTPUT_DIR = os.getenv('OUTPUT_DIR', 'translated_files')

# Debug mode (reload after .env is loaded)
DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'

# Log loaded configuration in debug mode
if DEBUG_MODE or _debug_mode:
    _config_logger.setLevel(logging.DEBUG)
    _config_logger.debug("="*60)
    _config_logger.debug("📋 LOADED CONFIGURATION VALUES:")
    _config_logger.debug("="*60)
    _config_logger.debug(f"   API_ENDPOINT: {API_ENDPOINT}")
    _config_logger.debug(f"   DEFAULT_MODEL: {DEFAULT_MODEL}")
    _config_logger.debug(f"   LLM_PROVIDER: {LLM_PROVIDER}")
    _config_logger.debug(f"   PORT: {PORT}")
    _config_logger.debug(f"   HOST: {HOST}")
    _config_logger.debug(f"   DEFAULT_SOURCE_LANGUAGE: {DEFAULT_SOURCE_LANGUAGE}")
    _config_logger.debug(f"   DEFAULT_TARGET_LANGUAGE: {DEFAULT_TARGET_LANGUAGE}")
    _config_logger.debug(f"   OLLAMA_NUM_CTX: {OLLAMA_NUM_CTX}")
    _config_logger.debug(f"   REQUEST_TIMEOUT: {REQUEST_TIMEOUT}")
    _config_logger.debug(f"   GEMINI_API_KEY: {'***' + GEMINI_API_KEY[-4:] if GEMINI_API_KEY else '(not set)'}")
    _config_logger.debug(f"   OPENAI_API_KEY: {'***' + OPENAI_API_KEY[-4:] if OPENAI_API_KEY else '(not set)'}")
    _config_logger.debug(f"   OPENROUTER_API_KEY: {'***' + OPENROUTER_API_KEY[-4:] if OPENROUTER_API_KEY else '(not set)'}")
    _config_logger.debug(f"   OPENROUTER_MODEL: {OPENROUTER_MODEL}")
    _config_logger.debug("="*60)

# Translation tags - Improved for LLM clarity and reliability
TRANSLATE_TAG_IN = "<TRANSLATION>"
TRANSLATE_TAG_OUT = "</TRANSLATION>"
INPUT_TAG_IN = "<SOURCE_TEXT>"
INPUT_TAG_OUT = "</SOURCE_TEXT>"

# ============================================================================
# TAG PLACEHOLDER CONFIGURATION
# ============================================================================
# These placeholders are used to temporarily replace HTML/XML tags during
# translation. The LLM must preserve them exactly in its output.

PLACEHOLDER_TAG_KEYWORD = "TAG"
"""The keyword used in placeholders (e.g., TAG in [TAG0])"""

PLACEHOLDER_PREFIX = f"[{PLACEHOLDER_TAG_KEYWORD}"
"""Prefix for tag placeholders (e.g., [TAG in [TAG0])"""

PLACEHOLDER_SUFFIX = "]"
"""Suffix for tag placeholders (e.g., ] in [TAG0])"""

PLACEHOLDER_PATTERN = rf'\[{PLACEHOLDER_TAG_KEYWORD}\d+\]'
"""Regex pattern for detecting tag placeholders in translated text (e.g., [TAG0])"""

# Mutation patterns - alternative formats LLMs might produce
PLACEHOLDER_DOUBLE_BRACKET_PATTERN = rf'\[\[{PLACEHOLDER_TAG_KEYWORD}\d+\]\]'
"""Pattern for double bracket mutation (e.g., [[TAG0]])"""

PLACEHOLDER_SINGLE_BRACKET_PATTERN = rf'\[{PLACEHOLDER_TAG_KEYWORD}\d+\]'
"""Pattern for single bracket mutation (e.g., [TAG0])"""

PLACEHOLDER_CURLY_BRACE_PATTERN = rf'\{{{PLACEHOLDER_TAG_KEYWORD}\d+\}}'
"""Pattern for curly brace mutation (e.g., {TAG0})"""

PLACEHOLDER_ANGLE_BRACKET_PATTERN = rf'<{PLACEHOLDER_TAG_KEYWORD}\d+>'
"""Pattern for angle bracket mutation (e.g., <TAG0>)"""

PLACEHOLDER_BARE_PATTERN = rf'{PLACEHOLDER_TAG_KEYWORD}\d+'
"""Pattern for bare TAG without brackets (e.g., TAG0)"""

# Orphaned bracket patterns for cleanup
ORPHANED_DOUBLE_BRACKETS_PATTERN = r'\[\[|\]\]'
"""Pattern for orphaned double brackets"""

ORPHANED_UNICODE_BRACKETS_PATTERN = r'⟦|⟧'
"""Pattern for orphaned Unicode brackets (legacy format)"""

ORPHANED_SINGLE_BRACKETS_PATTERN = r'(?<!\[)\[(?!\[)|(?<!\])\](?!\])'
"""Pattern for orphaned single brackets (current format)"""


def create_placeholder(tag_num: int) -> str:
    """Create a placeholder string for a given tag number."""
    return f"{PLACEHOLDER_PREFIX}{tag_num}{PLACEHOLDER_SUFFIX}"


def create_example_placeholder() -> str:
    """Create an example placeholder for documentation/prompts."""
    return create_placeholder(0)


def get_mutation_variants(tag_num) -> list:
    """
    Get all possible mutation variants for a given tag number.

    These are alternative formats that LLMs might produce instead of
    the correct placeholder format.

    Args:
        tag_num: The tag number (e.g., 0 for TAG0) - can be int or str

    Returns:
        List of possible mutation strings
    """
    return [
        f"[[{PLACEHOLDER_TAG_KEYWORD}{tag_num}]]",   # Double brackets
        f"{{{PLACEHOLDER_TAG_KEYWORD}{tag_num}}}",   # Curly braces
        f"<{PLACEHOLDER_TAG_KEYWORD}{tag_num}>",     # Angle brackets
        f"⟦{PLACEHOLDER_TAG_KEYWORD}{tag_num}⟧",     # Unicode brackets (legacy)
        f"{PLACEHOLDER_TAG_KEYWORD}{tag_num}",       # No brackets (check last)
    ]


# Sentence terminators
SENTENCE_TERMINATORS = tuple(list(".!?") + ['."', '?"', '!"', '."', ".'", "?'", "!'", ":", ".)"])

# EPUB-specific configuration
NAMESPACES = {
    'opf': 'http://www.idpf.org/2007/opf',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'xhtml': 'http://www.w3.org/1999/xhtml',
    'epub': 'http://www.idpf.org/2007/ops'
}

IGNORED_TAGS_EPUB = [
    '{http://www.w3.org/1999/xhtml}script',
    '{http://www.w3.org/1999/xhtml}style',
    '{http://www.w3.org/1999/xhtml}meta',
    '{http://www.w3.org/1999/xhtml}link'
]

CONTENT_BLOCK_TAGS_EPUB = [
    '{http://www.w3.org/1999/xhtml}p', '{http://www.w3.org/1999/xhtml}div',
    '{http://www.w3.org/1999/xhtml}li', '{http://www.w3.org/1999/xhtml}h1',
    '{http://www.w3.org/1999/xhtml}h2', '{http://www.w3.org/1999/xhtml}h3',
    '{http://www.w3.org/1999/xhtml}h4', '{http://www.w3.org/1999/xhtml}h5',
    '{http://www.w3.org/1999/xhtml}h6', '{http://www.w3.org/1999/xhtml}blockquote',
    '{http://www.w3.org/1999/xhtml}td', '{http://www.w3.org/1999/xhtml}th',
    '{http://www.w3.org/1999/xhtml}caption',
    '{http://www.w3.org/1999/xhtml}dt', '{http://www.w3.org/1999/xhtml}dd'
]

# Model family context size defaults (shared across providers)
# Used as fallback when context size cannot be detected from the server
# NOTE: Order matters! More specific patterns (gpt-4) must come before generic ones (gpt)
MODEL_FAMILY_CONTEXT_DEFAULTS = {
    "gpt-4": 128000,  # Must come before "gpt"
    "gpt": 8192,
    "claude": 100000,
    "deepseek": 16384,
    "mistral": 8192,
    "gemma": 8192,
    "qwen": 8192,
    "llama": 4096,
    "phi": 2048,
}
DEFAULT_CONTEXT_FALLBACK = 2048


@dataclass
class TranslationConfig:
    """Unified configuration for both CLI and web interfaces"""
    
    # Core settings
    source_language: str = DEFAULT_SOURCE_LANGUAGE
    target_language: str = DEFAULT_TARGET_LANGUAGE
    model: str = DEFAULT_MODEL
    api_endpoint: str = API_ENDPOINT
    
    # LLM Provider settings
    llm_provider: str = LLM_PROVIDER
    gemini_api_key: str = GEMINI_API_KEY
    openai_api_key: str = OPENAI_API_KEY
    openrouter_api_key: str = OPENROUTER_API_KEY
    
    # Translation parameters
    chunk_size: int = MAIN_LINES_PER_CHUNK
    
    # LLM parameters
    timeout: int = REQUEST_TIMEOUT
    max_attempts: int = MAX_TRANSLATION_ATTEMPTS
    retry_delay: int = RETRY_DELAY_SECONDS
    context_window: int = OLLAMA_NUM_CTX

    # Context optimization
    auto_adjust_context: bool = AUTO_ADJUST_CONTEXT
    min_chunk_size: int = MIN_CHUNK_SIZE
    max_chunk_size: int = MAX_CHUNK_SIZE

    # Token-based chunking
    use_token_chunking: bool = USE_TOKEN_CHUNKING
    max_tokens_per_chunk: int = MAX_TOKENS_PER_CHUNK
    soft_limit_ratio: float = SOFT_LIMIT_RATIO

    # Interface-specific
    interface_type: str = "cli"  # or "web"
    enable_colors: bool = True
    enable_interruption: bool = False

    @classmethod
    def from_cli_args(cls, args) -> 'TranslationConfig':
        """Create config from CLI arguments"""
        return cls(
            source_language=args.source_lang,
            target_language=args.target_lang,
            model=args.model,
            api_endpoint=args.api_endpoint,
            chunk_size=args.chunksize,
            interface_type="cli",
            enable_colors=not args.no_color,
            llm_provider=getattr(args, 'provider', LLM_PROVIDER),
            gemini_api_key=getattr(args, 'gemini_api_key', GEMINI_API_KEY),
            openai_api_key=getattr(args, 'openai_api_key', OPENAI_API_KEY),
            openrouter_api_key=getattr(args, 'openrouter_api_key', OPENROUTER_API_KEY),
            use_token_chunking=getattr(args, 'use_token_chunking', USE_TOKEN_CHUNKING),
            max_tokens_per_chunk=getattr(args, 'max_tokens_per_chunk', MAX_TOKENS_PER_CHUNK),
            soft_limit_ratio=getattr(args, 'soft_limit_ratio', SOFT_LIMIT_RATIO)
        )

    @classmethod
    def from_web_request(cls, request_data: dict) -> 'TranslationConfig':
        """Create config from web request data"""
        return cls(
            source_language=request_data.get('source_language', DEFAULT_SOURCE_LANGUAGE),
            target_language=request_data.get('target_language', DEFAULT_TARGET_LANGUAGE),
            model=request_data.get('model', DEFAULT_MODEL),
            api_endpoint=request_data.get('llm_api_endpoint', API_ENDPOINT),
            chunk_size=request_data.get('chunk_size', MAIN_LINES_PER_CHUNK),
            timeout=request_data.get('timeout', REQUEST_TIMEOUT),
            max_attempts=request_data.get('max_attempts', MAX_TRANSLATION_ATTEMPTS),
            retry_delay=request_data.get('retry_delay', RETRY_DELAY_SECONDS),
            context_window=request_data.get('context_window', OLLAMA_NUM_CTX),
            auto_adjust_context=request_data.get('auto_adjust_context', AUTO_ADJUST_CONTEXT),
            min_chunk_size=request_data.get('min_chunk_size', MIN_CHUNK_SIZE),
            max_chunk_size=request_data.get('max_chunk_size', MAX_CHUNK_SIZE),
            interface_type="web",
            enable_interruption=True,
            llm_provider=request_data.get('llm_provider', LLM_PROVIDER),
            gemini_api_key=request_data.get('gemini_api_key', GEMINI_API_KEY),
            openai_api_key=request_data.get('openai_api_key', OPENAI_API_KEY),
            openrouter_api_key=request_data.get('openrouter_api_key', OPENROUTER_API_KEY),
            use_token_chunking=request_data.get('use_token_chunking', USE_TOKEN_CHUNKING),
            max_tokens_per_chunk=request_data.get('max_tokens_per_chunk', MAX_TOKENS_PER_CHUNK),
            soft_limit_ratio=request_data.get('soft_limit_ratio', SOFT_LIMIT_RATIO)
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'source_language': self.source_language,
            'target_language': self.target_language,
            'model': self.model,
            'api_endpoint': self.api_endpoint,
            'chunk_size': self.chunk_size,
            'timeout': self.timeout,
            'max_attempts': self.max_attempts,
            'retry_delay': self.retry_delay,
            'context_window': self.context_window,
            'llm_provider': self.llm_provider,
            'gemini_api_key': self.gemini_api_key,
            'openai_api_key': self.openai_api_key,
            'openrouter_api_key': self.openrouter_api_key,
            'use_token_chunking': self.use_token_chunking,
            'max_tokens_per_chunk': self.max_tokens_per_chunk,
            'soft_limit_ratio': self.soft_limit_ratio
        }