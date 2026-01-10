"""Unit tests for custom exceptions."""

import pytest
from src.core.epub.exceptions import (
    EpubTranslationError,
    PlaceholderValidationError,
    ChunkSizeExceededError,
    XmlParsingError,
    TagRestorationError,
    BodyExtractionError,
    TranslationTimeoutError
)


class TestEpubTranslationError:
    """Test base exception class."""

    def test_base_exception_message(self):
        """Base exception should store message."""
        error = EpubTranslationError("Test error")
        assert str(error) == "Test error"

    def test_base_exception_inheritance(self):
        """Base exception should inherit from Exception."""
        error = EpubTranslationError("Test")
        assert isinstance(error, Exception)


class TestPlaceholderValidationError:
    """Test placeholder validation error."""

    def test_placeholder_validation_error_attributes(self):
        """PlaceholderValidationError should store attributes."""
        error = PlaceholderValidationError(
            "Test error",
            expected_count=5,
            actual_count=3,
            missing_placeholders=["[[3]]", "[[4]]"]
        )

        assert str(error) == "Test error"
        assert error.expected_count == 5
        assert error.actual_count == 3
        assert "[[3]]" in error.missing_placeholders
        assert "[[4]]" in error.missing_placeholders
        assert len(error.missing_placeholders) == 2

    def test_placeholder_validation_error_defaults(self):
        """PlaceholderValidationError should have default values."""
        error = PlaceholderValidationError("Test error")

        assert str(error) == "Test error"
        assert error.expected_count is None
        assert error.actual_count is None
        assert error.missing_placeholders == []

    def test_placeholder_validation_error_inheritance(self):
        """PlaceholderValidationError should inherit from EpubTranslationError."""
        error = PlaceholderValidationError("Test")
        assert isinstance(error, EpubTranslationError)
        assert isinstance(error, Exception)


class TestChunkSizeExceededError:
    """Test chunk size exceeded error."""

    def test_chunk_size_exceeded_error(self):
        """ChunkSizeExceededError should store size info."""
        error = ChunkSizeExceededError(
            "Chunk too large",
            chunk_size=600,
            max_size=400
        )

        assert str(error) == "Chunk too large"
        assert error.chunk_size == 600
        assert error.max_size == 400

    def test_chunk_size_exceeded_error_defaults(self):
        """ChunkSizeExceededError should have default values."""
        error = ChunkSizeExceededError("Chunk too large")

        assert str(error) == "Chunk too large"
        assert error.chunk_size is None
        assert error.max_size is None

    def test_chunk_size_exceeded_error_inheritance(self):
        """ChunkSizeExceededError should inherit from EpubTranslationError."""
        error = ChunkSizeExceededError("Test")
        assert isinstance(error, EpubTranslationError)


class TestXmlParsingError:
    """Test XML parsing error."""

    def test_xml_parsing_error_with_preview(self):
        """XmlParsingError should store content preview."""
        original_error = ValueError("Invalid XML")
        error = XmlParsingError(
            "Parse failed",
            original_error=original_error,
            content_preview="<p>Invalid HTML..."
        )

        assert str(error) == "Parse failed"
        assert error.original_error == original_error
        assert "<p>" in error.content_preview
        assert "Invalid HTML" in error.content_preview

    def test_xml_parsing_error_defaults(self):
        """XmlParsingError should have default values."""
        error = XmlParsingError("Parse failed")

        assert str(error) == "Parse failed"
        assert error.original_error is None
        assert error.content_preview is None

    def test_xml_parsing_error_inheritance(self):
        """XmlParsingError should inherit from EpubTranslationError."""
        error = XmlParsingError("Test")
        assert isinstance(error, EpubTranslationError)


class TestTagRestorationError:
    """Test tag restoration error."""

    def test_tag_restoration_error(self):
        """TagRestorationError should work as basic exception."""
        error = TagRestorationError("Failed to restore tags")
        assert str(error) == "Failed to restore tags"

    def test_tag_restoration_error_inheritance(self):
        """TagRestorationError should inherit from EpubTranslationError."""
        error = TagRestorationError("Test")
        assert isinstance(error, EpubTranslationError)


class TestBodyExtractionError:
    """Test body extraction error."""

    def test_body_extraction_error(self):
        """BodyExtractionError should work as basic exception."""
        error = BodyExtractionError("Failed to extract body")
        assert str(error) == "Failed to extract body"

    def test_body_extraction_error_inheritance(self):
        """BodyExtractionError should inherit from EpubTranslationError."""
        error = BodyExtractionError("Test")
        assert isinstance(error, EpubTranslationError)


class TestTranslationTimeoutError:
    """Test translation timeout error."""

    def test_translation_timeout_error(self):
        """TranslationTimeoutError should work as basic exception."""
        error = TranslationTimeoutError("Translation timed out")
        assert str(error) == "Translation timed out"

    def test_translation_timeout_error_inheritance(self):
        """TranslationTimeoutError should inherit from EpubTranslationError."""
        error = TranslationTimeoutError("Test")
        assert isinstance(error, EpubTranslationError)


class TestExceptionRaising:
    """Test that exceptions can be raised and caught correctly."""

    def test_raise_placeholder_validation_error(self):
        """PlaceholderValidationError should be raisable and catchable."""
        with pytest.raises(PlaceholderValidationError) as exc_info:
            raise PlaceholderValidationError(
                "Validation failed",
                expected_count=5,
                actual_count=3
            )

        assert "Validation failed" in str(exc_info.value)
        assert exc_info.value.expected_count == 5

    def test_raise_chunk_size_exceeded_error(self):
        """ChunkSizeExceededError should be raisable and catchable."""
        with pytest.raises(ChunkSizeExceededError) as exc_info:
            raise ChunkSizeExceededError("Too large", chunk_size=600, max_size=400)

        assert exc_info.value.chunk_size == 600

    def test_catch_base_exception(self):
        """Specific exceptions should be catchable as base EpubTranslationError."""
        with pytest.raises(EpubTranslationError):
            raise PlaceholderValidationError("Test")

        with pytest.raises(EpubTranslationError):
            raise XmlParsingError("Test")

    def test_catch_specific_exception(self):
        """Should be able to catch specific exception types."""
        try:
            raise PlaceholderValidationError("Test", expected_count=5, actual_count=3)
        except PlaceholderValidationError as e:
            assert e.expected_count == 5
            assert e.actual_count == 3
        except EpubTranslationError:
            pytest.fail("Should have caught PlaceholderValidationError specifically")
