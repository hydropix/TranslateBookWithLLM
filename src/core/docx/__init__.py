"""
DOCX translation module.

Provides conversion and translation capabilities for Microsoft Word documents (.docx).
"""

from .converter import DocxHtmlConverter
from .translator import translate_docx_file

__all__ = [
    'DocxHtmlConverter',
    'translate_docx_file'
]
