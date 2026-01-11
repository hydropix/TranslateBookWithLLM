"""Unit tests for TranslationContainer and TranslationConfig."""

import pytest
import sys
import os

# Add project root to path to avoid circular imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Import directly to avoid circular dependencies
from src.core.epub.container import TranslationContainer, TranslationConfig
from src.core.epub.tag_preservation import TagPreserver
from src.core.epub.html_chunker import HtmlChunker
from src.core.epub.placeholder_validator import PlaceholderValidator


class TestTranslationConfig:
    """Test TranslationConfig dataclass."""

    def test_default_values(self):
        """TranslationConfig should have sensible defaults."""
        config = TranslationConfig()

        assert config.max_tokens_per_chunk > 0
        assert config.max_retries >= 1
        assert config.enable_debug in [True, False]
        assert config.placeholder_prefix == "[id"
        assert config.placeholder_suffix == "]"

    def test_custom_values(self):
        """TranslationConfig should accept custom values."""
        config = TranslationConfig(
            max_tokens_per_chunk=500,
            max_retries=5,
            enable_debug=True,
            placeholder_prefix="[[",
            placeholder_suffix="]]"
        )

        assert config.max_tokens_per_chunk == 500
        assert config.max_retries == 5
        assert config.enable_debug is True
        assert config.placeholder_prefix == "[["
        assert config.placeholder_suffix == "]]"

    def test_validation_min_tokens(self):
        """TranslationConfig should reject too small max_tokens_per_chunk."""
        with pytest.raises(ValueError, match="max_tokens_per_chunk must be >= 50"):
            TranslationConfig(max_tokens_per_chunk=49)

    def test_validation_min_retries(self):
        """TranslationConfig should reject retries < 1."""
        with pytest.raises(ValueError, match="max_retries must be >= 1"):
            TranslationConfig(max_retries=0)

    def test_boundary_values(self):
        """TranslationConfig should accept boundary values."""
        # Minimum valid values
        config = TranslationConfig(
            max_tokens_per_chunk=50,
            max_retries=1
        )
        assert config.max_tokens_per_chunk == 50
        assert config.max_retries == 1

        # Large values should also work
        config_large = TranslationConfig(
            max_tokens_per_chunk=10000,
            max_retries=100
        )
        assert config_large.max_tokens_per_chunk == 10000
        assert config_large.max_retries == 100


class TestTranslationContainer:
    """Test TranslationContainer dependency injection."""

    def test_initialization_default_config(self):
        """Container should initialize with default config."""
        container = TranslationContainer()

        assert container.config is not None
        assert isinstance(container.config, TranslationConfig)
        assert container.config.max_tokens_per_chunk > 0

    def test_initialization_custom_config(self):
        """Container should accept custom config."""
        custom_config = TranslationConfig(
            max_tokens_per_chunk=600,
            max_retries=4,
            enable_debug=True
        )
        container = TranslationContainer(config=custom_config)

        assert container.config == custom_config
        assert container.config.max_tokens_per_chunk == 600
        assert container.config.max_retries == 4
        assert container.config.enable_debug is True

    def test_lazy_initialization(self):
        """Container should lazily initialize components."""
        container = TranslationContainer()

        # Components should be None before first access
        assert container._tag_preserver is None
        assert container._chunker is None
        assert container._validator is None

    def test_tag_preserver_creation(self):
        """Container should create TagPreserver on first access."""
        container = TranslationContainer()

        preserver = container.tag_preserver

        assert isinstance(preserver, TagPreserver)
        assert container._tag_preserver is not None

    def test_tag_preserver_singleton(self):
        """Container should return same TagPreserver instance."""
        container = TranslationContainer()

        preserver1 = container.tag_preserver
        preserver2 = container.tag_preserver

        assert preserver1 is preserver2

    def test_chunker_creation(self):
        """Container should create HtmlChunker on first access."""
        container = TranslationContainer()

        chunker = container.chunker

        assert isinstance(chunker, HtmlChunker)
        assert container._chunker is not None

    def test_chunker_singleton(self):
        """Container should return same HtmlChunker instance."""
        container = TranslationContainer()

        chunker1 = container.chunker
        chunker2 = container.chunker

        assert chunker1 is chunker2

    def test_chunker_respects_config(self):
        """Chunker should use configuration from container."""
        config = TranslationConfig(max_tokens_per_chunk=700)
        container = TranslationContainer(config=config)

        chunker = container.chunker

        assert chunker.max_tokens == 700

    def test_validator_creation(self):
        """Container should create PlaceholderValidator on first access."""
        container = TranslationContainer()

        validator = container.validator

        assert isinstance(validator, PlaceholderValidator)
        assert container._validator is not None

    def test_validator_singleton(self):
        """Container should return same PlaceholderValidator instance."""
        container = TranslationContainer()

        validator1 = container.validator
        validator2 = container.validator

        assert validator1 is validator2

    def test_multiple_containers_independent(self):
        """Multiple containers should be independent."""
        container1 = TranslationContainer(
            TranslationConfig(max_tokens_per_chunk=400)
        )
        container2 = TranslationContainer(
            TranslationConfig(max_tokens_per_chunk=600)
        )

        chunker1 = container1.chunker
        chunker2 = container2.chunker

        # Different instances
        assert chunker1 is not chunker2
        # Different configurations
        assert chunker1.max_tokens == 400
        assert chunker2.max_tokens == 600

    def test_create_translator_not_implemented(self):
        """create_translator should raise NotImplementedError (Phase 3)."""
        container = TranslationContainer()

        with pytest.raises(NotImplementedError, match="Phase 3"):
            container.create_translator(None, None)


class TestContainerIntegration:
    """Integration tests for container usage."""

    def test_end_to_end_component_access(self):
        """Test accessing all components in sequence."""
        config = TranslationConfig(
            max_tokens_per_chunk=450,
            max_retries=3,
            enable_debug=False
        )
        container = TranslationContainer(config=config)

        # Access all components
        preserver = container.tag_preserver
        chunker = container.chunker
        validator = container.validator

        # All should be initialized
        assert preserver is not None
        assert chunker is not None
        assert validator is not None

        # Components should work together
        # Example: preserve tags, then validate
        html = "<p>Test</p>"
        text_with_placeholders, tag_map = preserver.preserve_tags(html)

        # Validator should validate basic placeholders
        is_valid = validator.validate_basic(text_with_placeholders, tag_map)
        assert is_valid is True

    def test_configuration_propagation(self):
        """Test that configuration properly propagates to components."""
        custom_config = TranslationConfig(
            max_tokens_per_chunk=800,
            max_retries=5
        )
        container = TranslationContainer(config=custom_config)

        # Chunker should respect the config
        chunker = container.chunker
        assert chunker.max_tokens == 800

        # Config should be accessible
        assert container.config.max_retries == 5
