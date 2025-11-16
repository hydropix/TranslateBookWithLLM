"""
Character-based chunking module for EPUB translation.

Provides consistent chunk sizes (80% within ±20% of target) with semantic boundary preservation.
"""

__version__ = "1.0.0"

# Phase 2: Export all models
from .models import (
    # Enums
    BoundaryType,
    ChunkStatus,
    # Dataclasses
    ChunkingConfiguration,
    TextChunk,
    EPUBChapter,
    ChunkStatistics,
    ChunkBoundary,
    # Exceptions
    ChunkingError,
    ChunkingConfigurationError,
    BoundaryDetectionError,
    EPUBProcessingError,
    StatisticsCalculationError,
)

# Phase 3: Export chunking functions
from .boundary_detector import (
    find_sentence_boundary,
    detect_paragraph_boundaries,
    is_header_line,
    create_chunk_boundary,
)

from .character_chunker import chunk_text_by_characters

from .statistics import calculate_chunk_statistics

__all__ = [
    # Enums
    "BoundaryType",
    "ChunkStatus",
    # Dataclasses
    "ChunkingConfiguration",
    "TextChunk",
    "EPUBChapter",
    "ChunkStatistics",
    "ChunkBoundary",
    # Exceptions
    "ChunkingError",
    "ChunkingConfigurationError",
    "BoundaryDetectionError",
    "EPUBProcessingError",
    "StatisticsCalculationError",
    # Functions
    "find_sentence_boundary",
    "detect_paragraph_boundaries",
    "is_header_line",
    "create_chunk_boundary",
    "chunk_text_by_characters",
    "calculate_chunk_statistics",
]
