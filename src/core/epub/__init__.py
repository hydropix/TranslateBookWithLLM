"""
EPUB translation module

This module provides specialized translation functionality for EPUB files,
using the simplified translation approach with smart chunking and tag preservation.

Main entry points:
    translate_epub_file() - Translate an EPUB file using LLM
    translate_xhtml_simplified() - Translate a single XHTML document

Components:
    - translator: Main translation orchestration
    - xhtml_translator: Body-based translation with smart chunking
    - tag_preservation: HTML/XML tag preservation during translation
    - html_chunker: HTML-aware text chunking with placeholder management
    - body_serializer: Body extraction and replacement for XHTML documents
    - xml_helpers: Safe XML manipulation utilities
    - constants: Configuration constants
"""

from .translator import translate_epub_file
from .tag_preservation import TagPreserver
from .xhtml_translator import translate_xhtml_simplified
from .html_chunker import HtmlChunker, TranslationStats
from .body_serializer import extract_body_html, replace_body_content
from .constants import (
    MIN_CONTEXT_LINES,
    MIN_CONTEXT_WORDS,
    MAX_CONTEXT_LINES,
    MAX_CONTEXT_BLOCKS,
    PLACEHOLDER_PATTERN
)

__all__ = [
    # Main translation functions
    'translate_epub_file',
    'translate_xhtml_simplified',

    # Tag preservation
    'TagPreserver',

    # HTML chunking
    'HtmlChunker',
    'TranslationStats',

    # Body serialization
    'extract_body_html',
    'replace_body_content',

    # Constants
    'MIN_CONTEXT_LINES',
    'MIN_CONTEXT_WORDS',
    'MAX_CONTEXT_LINES',
    'MAX_CONTEXT_BLOCKS',
    'PLACEHOLDER_PATTERN',
]
