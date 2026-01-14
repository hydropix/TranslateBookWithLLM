"""
Exception hierarchy for the translation adapter system.

This module provides a comprehensive exception system for error handling
across all translation adapters and operations.
"""

from typing import Optional, Dict, Any


class TranslationError(Exception):
    """Base exception for all translation-related errors.

    Attributes:
        message: Human-readable error message
        context: Additional context about the error
        recoverable: Whether the error can potentially be recovered from
    """

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        recoverable: bool = False
    ):
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.recoverable = recoverable

    def __str__(self) -> str:
        base = f"{self.__class__.__name__}: {self.message}"
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            base += f" (context: {context_str})"
        return base


# ============================================================================
# Adapter-level errors
# ============================================================================

class AdapterError(TranslationError):
    """Base exception for adapter-specific errors."""
    pass


class AdapterInitializationError(AdapterError):
    """Raised when adapter initialization fails."""
    pass


class AdapterPreparationError(AdapterError):
    """Raised when prepare_for_translation() fails."""
    pass


class AdapterReconstructionError(AdapterError):
    """Raised when reconstruct_output() fails."""
    pass


class AdapterCleanupError(AdapterError):
    """Raised when cleanup() fails (non-critical)."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        # Cleanup errors are always non-critical
        super().__init__(message, context, recoverable=True)


# ============================================================================
# Translation unit errors
# ============================================================================

class TranslationUnitError(TranslationError):
    """Base exception for translation unit processing errors."""
    pass


class UnitExtractionError(TranslationUnitError):
    """Raised when extracting translation units fails."""
    pass


class UnitTranslationError(TranslationUnitError):
    """Raised when translating a specific unit fails.

    Attributes:
        unit_id: Identifier of the failed unit
        unit_index: Index of the failed unit
    """

    def __init__(
        self,
        message: str,
        unit_id: Optional[str] = None,
        unit_index: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
        recoverable: bool = True
    ):
        super().__init__(message, context, recoverable)
        self.unit_id = unit_id
        self.unit_index = unit_index


class UnitSaveError(TranslationUnitError):
    """Raised when saving a translated unit fails."""
    pass


# ============================================================================
# LLM-related errors
# ============================================================================

class LLMError(TranslationError):
    """Base exception for LLM provider errors."""
    pass


class ContextOverflowError(LLMError):
    """Raised when input exceeds model's context window.

    This is recoverable by splitting the content into smaller chunks.
    """

    def __init__(
        self,
        message: str,
        token_count: Optional[int] = None,
        max_tokens: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if token_count is not None:
            ctx['token_count'] = token_count
        if max_tokens is not None:
            ctx['max_tokens'] = max_tokens
        super().__init__(message, ctx, recoverable=True)


class RepetitionLoopError(LLMError):
    """Raised when model enters a repetition loop.

    This is recoverable by retrying with different parameters.
    """

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, context, recoverable=True)


class LLMConnectionError(LLMError):
    """Raised when connection to LLM provider fails.

    This is recoverable by retrying the request.
    """

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, context, recoverable=True)


class LLMRateLimitError(LLMError):
    """Raised when rate limit is exceeded.

    This is recoverable by waiting and retrying.
    """

    def __init__(
        self,
        message: str,
        retry_after: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if retry_after is not None:
            ctx['retry_after'] = retry_after
        super().__init__(message, ctx, recoverable=True)


class LLMAuthenticationError(LLMError):
    """Raised when authentication fails (missing/invalid API key).

    This is NOT recoverable without user intervention.
    """

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, context, recoverable=False)


class LLMResponseError(LLMError):
    """Raised when LLM response is invalid or unparseable.

    This is recoverable by retrying the request.
    """

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, context, recoverable=True)


# ============================================================================
# Checkpoint/Resume errors
# ============================================================================

class CheckpointError(TranslationError):
    """Base exception for checkpoint system errors."""
    pass


class CheckpointLoadError(CheckpointError):
    """Raised when loading checkpoint data fails."""
    pass


class CheckpointSaveError(CheckpointError):
    """Raised when saving checkpoint data fails."""
    pass


class CheckpointCorruptionError(CheckpointError):
    """Raised when checkpoint data is corrupted or invalid."""
    pass


class ResumeError(CheckpointError):
    """Raised when resuming from checkpoint fails.

    Attributes:
        checkpoint_id: ID of the checkpoint that failed to resume
    """

    def __init__(
        self,
        message: str,
        checkpoint_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, context, recoverable=False)
        self.checkpoint_id = checkpoint_id


# ============================================================================
# File/Format-specific errors
# ============================================================================

class FileFormatError(TranslationError):
    """Base exception for file format errors."""
    pass


class FileReadError(FileFormatError):
    """Raised when reading input file fails."""
    pass


class FileWriteError(FileFormatError):
    """Raised when writing output file fails."""
    pass


class FileValidationError(FileFormatError):
    """Raised when file validation fails."""
    pass


class UnsupportedFormatError(FileFormatError):
    """Raised when file format is not supported."""

    def __init__(
        self,
        message: str,
        file_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if file_type is not None:
            ctx['file_type'] = file_type
        super().__init__(message, ctx, recoverable=False)


# EPUB-specific errors (re-exported from epub module for consistency)
class EpubError(FileFormatError):
    """Base exception for EPUB-specific errors."""
    pass


class PlaceholderValidationError(EpubError):
    """Raised when placeholder validation fails."""

    def __init__(
        self,
        message: str,
        expected_count: Optional[int] = None,
        actual_count: Optional[int] = None,
        missing_placeholders: Optional[list] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if expected_count is not None:
            ctx['expected_count'] = expected_count
        if actual_count is not None:
            ctx['actual_count'] = actual_count
        if missing_placeholders:
            ctx['missing_placeholders'] = missing_placeholders
        super().__init__(message, ctx, recoverable=True)


class ChunkSizeExceededError(EpubError):
    """Raised when chunk exceeds maximum size."""

    def __init__(
        self,
        message: str,
        chunk_size: Optional[int] = None,
        max_size: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if chunk_size is not None:
            ctx['chunk_size'] = chunk_size
        if max_size is not None:
            ctx['max_size'] = max_size
        super().__init__(message, ctx, recoverable=True)


class TagRestorationError(EpubError):
    """Raised when tag restoration fails."""
    pass


class XmlParsingError(EpubError):
    """Raised when XML/HTML parsing fails."""

    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
        content_preview: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if original_error:
            ctx['original_error'] = str(original_error)
        if content_preview:
            ctx['content_preview'] = content_preview[:200]
        super().__init__(message, ctx, recoverable=False)


class BodyExtractionError(EpubError):
    """Raised when body extraction fails."""
    pass


# ============================================================================
# Configuration errors
# ============================================================================

class ConfigurationError(TranslationError):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, context, recoverable=False)


# ============================================================================
# Retry exhaustion
# ============================================================================

class RetryExhaustedError(TranslationError):
    """Raised when all retry attempts have been exhausted.

    Attributes:
        original_error: The original error that triggered retries
        attempts: Number of retry attempts made
    """

    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
        attempts: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if original_error:
            ctx['original_error'] = str(original_error)
            ctx['original_error_type'] = type(original_error).__name__
        if attempts is not None:
            ctx['attempts'] = attempts
        super().__init__(message, ctx, recoverable=False)
        self.original_error = original_error
        self.attempts = attempts


# ============================================================================
# Validation errors
# ============================================================================

class ValidationError(TranslationError):
    """Raised when validation fails."""
    pass


class ContentValidationError(ValidationError):
    """Raised when content validation fails."""
    pass


class StructureValidationError(ValidationError):
    """Raised when structure validation fails."""
    pass
