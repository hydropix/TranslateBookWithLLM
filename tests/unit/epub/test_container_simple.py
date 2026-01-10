"""Simple unit tests for TranslationConfig only (avoiding circular imports)."""

import pytest


def test_import_config():
    """Test that TranslationConfig can be imported."""
    from src.config import MAX_TOKENS_PER_CHUNK
    from src.core.epub.container import TranslationConfig

    config = TranslationConfig()
    assert config.max_tokens_per_chunk ==  MAX_TOKENS_PER_CHUNK
    assert config.max_retries >= 1


def test_custom_config():
    """TranslationConfig should accept custom values."""
    from src.core.epub.container import TranslationConfig

    config = TranslationConfig(
        max_tokens_per_chunk=500,
        max_retries=5,
        enable_debug=True
    )

    assert config.max_tokens_per_chunk == 500
    assert config.max_retries == 5
    assert config.enable_debug is True


def test_validation_min_tokens():
    """TranslationConfig should reject too small max_tokens_per_chunk."""
    from src.core.epub.container import TranslationConfig

    with pytest.raises(ValueError, match="max_tokens_per_chunk must be >= 50"):
        TranslationConfig(max_tokens_per_chunk=49)


def test_validation_min_retries():
    """TranslationConfig should reject retries < 1."""
    from src.core.epub.container import TranslationConfig

    with pytest.raises(ValueError, match="max_retries must be >= 1"):
        TranslationConfig(max_retries=0)
