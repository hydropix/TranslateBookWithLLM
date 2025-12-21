"""
Constants for EPUB translation processing

This module defines all magic numbers and configuration values used throughout
the EPUB translation pipeline.
"""

# Context window constants
MIN_CONTEXT_LINES = 3
"""Minimum number of lines to include in translation context"""

MIN_CONTEXT_WORDS = 25
"""Minimum number of words to include in translation context"""

MAX_CONTEXT_LINES = 5
"""Maximum number of lines to include in translation context"""

MAX_CONTEXT_BLOCKS = 10
"""Maximum number of translation blocks to keep in context accumulator"""

# Placeholder configuration - re-exported from src.config for backward compatibility
# The canonical definitions are in src/config.py to avoid circular imports
from src.config import (
    PLACEHOLDER_TAG_KEYWORD,
    PLACEHOLDER_PREFIX,
    PLACEHOLDER_SUFFIX,
    PLACEHOLDER_PATTERN,
    PLACEHOLDER_DOUBLE_BRACKET_PATTERN,
    PLACEHOLDER_SINGLE_BRACKET_PATTERN,
    PLACEHOLDER_CURLY_BRACE_PATTERN,
    PLACEHOLDER_ANGLE_BRACKET_PATTERN,
    PLACEHOLDER_BARE_PATTERN,
    ORPHANED_DOUBLE_BRACKETS_PATTERN,
    ORPHANED_UNICODE_BRACKETS_PATTERN,
    create_placeholder,
    create_example_placeholder,
    get_mutation_variants,
)
