"""
Core translation modules
"""
from .text_processor import split_text_into_chunks
from .translator import generate_translation_request, translate_chunks
from .epub import translate_epub_file

__all__ = [
    'split_text_into_chunks',
    'generate_translation_request',
    'translate_chunks',
    'translate_epub_file'
]