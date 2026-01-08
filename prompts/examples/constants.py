"""
Shared constants for translation examples.

This module provides dynamic placeholder generation using actual config constants.
"""

from src.config import create_placeholder

# Generate placeholders using the actual config constants
TAG0 = create_placeholder(0)  # e.g., [[0]]
TAG1 = create_placeholder(1)  # e.g., [[1]]
TAG2 = create_placeholder(2)  # e.g., [[2]]
