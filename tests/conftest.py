"""
Pytest configuration and fixtures for all tests.

This file is automatically loaded by pytest and provides common fixtures
and configuration for all test modules.
"""

import sys
import os
from pathlib import Path
import importlib.util

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import pytest for fixtures
import pytest


def import_module_from_path(module_name, file_path):
    """
    Import a module directly from file path without triggering package imports.

    This avoids circular import issues when testing isolated modules.
    """
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Pre-load EPUB modules to avoid circular import issues
_epub_exceptions = import_module_from_path(
    'src.core.epub.exceptions',
    project_root / 'src' / 'core' / 'epub' / 'exceptions.py'
)

_placeholder_validator = import_module_from_path(
    'src.core.epub.placeholder_validator',
    project_root / 'src' / 'core' / 'epub' / 'placeholder_validator.py'
)

_tag_preservation = import_module_from_path(
    'src.core.epub.tag_preservation',
    project_root / 'src' / 'core' / 'epub' / 'tag_preservation.py'
)


@pytest.fixture
def sample_html():
    """Sample HTML for testing."""
    return "<p>Hello <b>World</b></p>"


@pytest.fixture
def sample_tag_map():
    """Sample tag map for testing."""
    return {
        "[[0]]": "<p>",
        "[[1]]": "<b>",
        "[[2]]": "</b>",
        "[[3]]": "</p>"
    }


@pytest.fixture
def sample_text_with_placeholders():
    """Sample text with placeholders for testing."""
    return "[[0]]Hello [[1]]World[[2]][[3]]"
