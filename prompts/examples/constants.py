"""
Shared constants for translation examples.

This module provides dynamic placeholder generation using actual config constants.
"""

from src.config import (
    create_placeholder,
    IMAGE_MARKER_PREFIX,
    IMAGE_MARKER_SUFFIX,
)

# Generate placeholders using the actual config constants
TAG0 = create_placeholder(0)  # e.g., [TAG0]
TAG1 = create_placeholder(1)  # e.g., [TAG1]
TAG2 = create_placeholder(2)  # e.g., [TAG2]

# Image marker examples
IMG_MARKER = f"{IMAGE_MARKER_PREFIX}001{IMAGE_MARKER_SUFFIX}"  # e.g., [IMG001]
IMG_MARKER_2 = f"{IMAGE_MARKER_PREFIX}002{IMAGE_MARKER_SUFFIX}"
