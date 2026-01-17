"""
Common translation components.

This module contains reusable components for translation:
- GenericTranslationOrchestrator: Unified pipeline for all formats
- TranslationAdapter: Interface for format-specific adapters
- TranslationMetrics: Shared metrics tracking
"""

from .translation_orchestrator import (
    GenericTranslationOrchestrator,
    TranslationAdapter
)

__all__ = [
    'GenericTranslationOrchestrator',
    'TranslationAdapter',
]
