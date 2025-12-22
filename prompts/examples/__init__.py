"""
Multilingual examples for translation prompts.

This package provides two types of examples:

1. TECHNICAL EXAMPLES (generated dynamically):
   - Placeholder preservation (HTML/XML tags)
   - Image marker preservation
   - Simple sentences that focus on WHAT to preserve

2. CULTURAL EXAMPLES (hand-curated, high quality):
   - Idiomatic translation (avoid literal translation)
   - Cultural adaptation (metaphors, expressions)
   - Show HOW to translate naturally

All examples use the actual constants from src/config.py to ensure consistency.
"""

# Re-export constants
from .constants import (
    TAG0,
    TAG1,
    TAG2,
    IMG_MARKER,
    IMG_MARKER_2,
)

# Re-export example dictionaries
from .placeholder_examples import PLACEHOLDER_EXAMPLES
from .image_examples import IMAGE_EXAMPLES
from .subtitle_examples import SUBTITLE_EXAMPLES
from .output_examples import OUTPUT_FORMAT_EXAMPLES

# Re-export cultural examples
from .cultural_examples import (
    CULTURAL_EXAMPLES,
    get_cultural_examples,
    has_cultural_examples,
    format_cultural_examples_for_prompt,
)

# Re-export helper functions
from .helpers import (
    get_placeholder_example,
    get_image_example,
    get_subtitle_example,
    get_output_format_example,
    build_placeholder_section,
    build_image_placeholder_section,
    build_cultural_section,
    has_example_for_pair,
    has_image_example_for_pair,
    ensure_example_ready,
    ensure_image_example_ready,
    ensure_all_examples_ready,
)

__all__ = [
    # Constants
    "TAG0",
    "TAG1",
    "TAG2",
    "IMG_MARKER",
    "IMG_MARKER_2",
    # Technical example dictionaries (fallback)
    "PLACEHOLDER_EXAMPLES",
    "IMAGE_EXAMPLES",
    "SUBTITLE_EXAMPLES",
    "OUTPUT_FORMAT_EXAMPLES",
    # Cultural examples
    "CULTURAL_EXAMPLES",
    "get_cultural_examples",
    "has_cultural_examples",
    "format_cultural_examples_for_prompt",
    # Helper functions
    "get_placeholder_example",
    "get_image_example",
    "get_subtitle_example",
    "get_output_format_example",
    "build_placeholder_section",
    "build_image_placeholder_section",
    "build_cultural_section",
    "has_example_for_pair",
    "has_image_example_for_pair",
    "ensure_example_ready",
    "ensure_image_example_ready",
    "ensure_all_examples_ready",
]
