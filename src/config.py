"""
Centralized configuration class
"""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

# Load from environment variables with defaults
API_ENDPOINT = os.getenv('API_ENDPOINT', 'http://localhost:11434/api/generate')
DEFAULT_MODEL = os.getenv('DEFAULT_MODEL', 'mistral-small:24b')
PORT = int(os.getenv('PORT', '5000'))
MAIN_LINES_PER_CHUNK = int(os.getenv('MAIN_LINES_PER_CHUNK', '25'))
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '900'))
OLLAMA_NUM_CTX = int(os.getenv('OLLAMA_NUM_CTX', '2048'))
MAX_TRANSLATION_ATTEMPTS = int(os.getenv('MAX_TRANSLATION_ATTEMPTS', '2'))
RETRY_DELAY_SECONDS = int(os.getenv('RETRY_DELAY_SECONDS', '2'))

# Context optimization settings
MIN_RECOMMENDED_NUM_CTX = 4096  # Minimum recommended context for chunk_size=25
SAFETY_MARGIN = 1.2  # 20% safety margin for token estimation
AUTO_ADJUST_CONTEXT = os.getenv("AUTO_ADJUST_CONTEXT", "true").lower() == "true"
MIN_CHUNK_SIZE = int(os.getenv("MIN_CHUNK_SIZE", "5"))
MAX_CHUNK_SIZE = int(os.getenv("MAX_CHUNK_SIZE", "100"))

# LLM Provider configuration
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'ollama')  # 'ollama', 'gemini', or 'openai'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

# SRT-specific configuration
SRT_LINES_PER_BLOCK = int(os.getenv('SRT_LINES_PER_BLOCK', '5'))
SRT_MAX_CHARS_PER_BLOCK = int(os.getenv('SRT_MAX_CHARS_PER_BLOCK', '500'))

# Default languages from environment
DEFAULT_SOURCE_LANGUAGE = os.getenv('DEFAULT_SOURCE_LANGUAGE', 'English')
DEFAULT_TARGET_LANGUAGE = os.getenv('DEFAULT_TARGET_LANGUAGE', 'French')

# Server configuration
HOST = os.getenv('HOST', '127.0.0.1')
OUTPUT_DIR = os.getenv('OUTPUT_DIR', 'translated_files')

# Translation tags - Improved for LLM clarity and reliability
TRANSLATE_TAG_IN = "<TRANSLATION>"
TRANSLATE_TAG_OUT = "</TRANSLATION>"
INPUT_TAG_IN = "<SOURCE_TEXT>"
INPUT_TAG_OUT = "</SOURCE_TEXT>"

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
    
    # Translation parameters
    chunk_size: int = MAIN_LINES_PER_CHUNK
    custom_instructions: str = ""
    enable_post_processing: bool = False
    post_processing_instructions: str = ""
    
    # LLM parameters
    timeout: int = REQUEST_TIMEOUT
    max_attempts: int = MAX_TRANSLATION_ATTEMPTS
    retry_delay: int = RETRY_DELAY_SECONDS
    context_window: int = OLLAMA_NUM_CTX

    # Context optimization
    auto_adjust_context: bool = AUTO_ADJUST_CONTEXT
    min_chunk_size: int = MIN_CHUNK_SIZE
    max_chunk_size: int = MAX_CHUNK_SIZE

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
            custom_instructions=args.custom_instructions,
            interface_type="cli",
            enable_colors=not args.no_color,
            llm_provider=getattr(args, 'provider', LLM_PROVIDER),
            gemini_api_key=getattr(args, 'gemini_api_key', GEMINI_API_KEY),
            openai_api_key=getattr(args, 'openai_api_key', OPENAI_API_KEY),
            enable_post_processing=getattr(args, 'post_process', False),
            post_processing_instructions=getattr(args, 'post_process_instructions', '')
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
            custom_instructions=request_data.get('custom_instructions', ''),
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
            enable_post_processing=request_data.get('enable_post_processing', False),
            post_processing_instructions=request_data.get('post_processing_instructions', '')
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'source_language': self.source_language,
            'target_language': self.target_language,
            'model': self.model,
            'api_endpoint': self.api_endpoint,
            'chunk_size': self.chunk_size,
            'custom_instructions': self.custom_instructions,
            'timeout': self.timeout,
            'max_attempts': self.max_attempts,
            'retry_delay': self.retry_delay,
            'context_window': self.context_window,
            'llm_provider': self.llm_provider,
            'gemini_api_key': self.gemini_api_key,
            'openai_api_key': self.openai_api_key,
            'enable_post_processing': self.enable_post_processing,
            'post_processing_instructions': self.post_processing_instructions
        }