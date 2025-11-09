"""
EPUB translation module

This module provides specialized translation functionality for EPUB files,
including structure preservation, tag handling, and metadata management.

Main entry point:
    translate_epub_file() - Translate an EPUB file using LLM

Components:
    - translator: Main translation orchestration
    - job_collector: Translation job collection from EPUB structure
    - tag_preservation: HTML/XML tag preservation during translation
    - xml_helpers: Safe XML manipulation utilities
    - constants: Configuration constants
"""

from .translator import translate_epub_file
from .tag_preservation import TagPreserver
from .job_collector import collect_translation_jobs
from .constants import (
    MIN_CONTEXT_LINES,
    MIN_CONTEXT_WORDS,
    MAX_CONTEXT_LINES,
    MAX_CONTEXT_BLOCKS,
    PLACEHOLDER_PATTERN
)

__all__ = [
    # Main translation function
    'translate_epub_file',

    # Tag preservation
    'TagPreserver',

    # Job collection
    'collect_translation_jobs',

    # Constants
    'MIN_CONTEXT_LINES',
    'MIN_CONTEXT_WORDS',
    'MAX_CONTEXT_LINES',
    'MAX_CONTEXT_BLOCKS',
    'PLACEHOLDER_PATTERN',
]
