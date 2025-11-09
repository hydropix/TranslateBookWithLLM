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

# Placeholder pattern
PLACEHOLDER_PATTERN = r'⟦TAG\d+⟧'
"""Regex pattern for detecting tag placeholders in translated text"""
