"""
Custom exceptions for EPUB translation pipeline.

This module defines specific exception types for different failure scenarios,
enabling better error handling and debugging.
"""


class EpubTranslationError(Exception):
    """Base exception for all EPUB translation errors."""
    pass


class PlaceholderValidationError(EpubTranslationError):
    """Raised when placeholder validation fails.

    Attributes:
        message: Error description
        expected_count: Expected number of placeholders
        actual_count: Actual number found
        missing_placeholders: List of missing placeholder IDs
    """
    def __init__(
        self,
        message: str,
        expected_count: int = None,
        actual_count: int = None,
        missing_placeholders: list = None
    ):
        super().__init__(message)
        self.expected_count = expected_count
        self.actual_count = actual_count
        self.missing_placeholders = missing_placeholders or []


class ChunkSizeExceededError(EpubTranslationError):
    """Raised when a chunk exceeds maximum allowed size.

    Attributes:
        chunk_size: Actual size in tokens
        max_size: Maximum allowed size
    """
    def __init__(self, message: str, chunk_size: int = None, max_size: int = None):
        super().__init__(message)
        self.chunk_size = chunk_size
        self.max_size = max_size


class TagRestorationError(EpubTranslationError):
    """Raised when tag restoration from placeholders fails."""
    pass


class XmlParsingError(EpubTranslationError):
    """Raised when XML/HTML parsing fails after all fallback attempts.

    Attributes:
        original_error: The underlying parsing error
        content_preview: First 200 chars of problematic content
    """
    def __init__(self, message: str, original_error: Exception = None, content_preview: str = None):
        super().__init__(message)
        self.original_error = original_error
        self.content_preview = content_preview


class BodyExtractionError(EpubTranslationError):
    """Raised when body extraction from XHTML fails."""
    pass


class TranslationTimeoutError(EpubTranslationError):
    """Raised when translation exceeds timeout threshold."""
    pass
