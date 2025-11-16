"""
Data models for character-based chunking.

Provides enums, dataclasses, and exceptions for the chunking system.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import statistics as stats_module


# === Enums (T006) ===

class BoundaryType(Enum):
    """Type of chunk boundary."""
    SENTENCE_END = "sentence_end"
    PARAGRAPH_END = "paragraph_end"
    SECTION_END = "section_end"
    FORCED_SIZE = "forced_size"
    CHAPTER_END = "chapter_end"


class ChunkStatus(Enum):
    """Status of a text chunk in the translation pipeline."""
    CREATED = "created"
    VALIDATED = "validated"
    TRANSLATED = "translated"
    ASSEMBLED = "assembled"
    FAILED = "failed"


# === Custom Exceptions (T012) ===

class ChunkingError(Exception):
    """Base exception for chunking operations."""
    pass


class ChunkingConfigurationError(ChunkingError):
    """Invalid chunking configuration."""
    pass


class BoundaryDetectionError(ChunkingError):
    """Failed to find valid boundary."""
    pass


class EPUBProcessingError(ChunkingError):
    """Error processing EPUB structure."""
    pass


class StatisticsCalculationError(ChunkingError):
    """Error computing statistics."""
    pass


# === Configuration (T007) ===

@dataclass
class ChunkingConfiguration:
    """Configuration parameters for the chunking algorithm."""

    target_size: int = 2500
    min_tolerance: float = 0.8
    max_tolerance: float = 1.2
    warning_threshold: float = 1.5
    sentence_terminators: list = field(default_factory=lambda: [
        '.', '!', '?', '."', '?"', '!"', ".'", "?'", "!'", '.)', ':]'
    ])
    preserve_headers: bool = True
    report_statistics: bool = True

    def __post_init__(self):
        """Validate configuration after initialization."""
        self.validate()

    def validate(self) -> None:
        """Validate configuration parameters. Raises ChunkingConfigurationError if invalid."""
        if not (100 < self.target_size < 100000):
            raise ChunkingConfigurationError(
                f"target_size must be between 100 and 100000, got {self.target_size}"
            )

        if not (0 < self.min_tolerance < 1.0):
            raise ChunkingConfigurationError(
                f"min_tolerance must be between 0 and 1.0, got {self.min_tolerance}"
            )

        if not (1.0 < self.max_tolerance < 3.0):
            raise ChunkingConfigurationError(
                f"max_tolerance must be between 1.0 and 3.0, got {self.max_tolerance}"
            )

        if self.warning_threshold < self.max_tolerance:
            raise ChunkingConfigurationError(
                f"warning_threshold ({self.warning_threshold}) must be >= max_tolerance ({self.max_tolerance})"
            )

        if not self.sentence_terminators:
            raise ChunkingConfigurationError("sentence_terminators must contain at least one element")

    @property
    def min_size(self) -> int:
        """Minimum acceptable chunk size in characters."""
        return int(self.target_size * self.min_tolerance)

    @property
    def max_size(self) -> int:
        """Maximum acceptable chunk size in characters."""
        return int(self.target_size * self.max_tolerance)

    @property
    def warning_size(self) -> int:
        """Chunk size that triggers a warning."""
        return int(self.target_size * self.warning_threshold)


# === Text Chunk (T008) ===

@dataclass
class TextChunk:
    """A discrete unit of text prepared for translation."""

    content: str
    character_count: int
    chunk_index: int
    chapter_id: str
    chapter_index: int
    boundary_type: BoundaryType
    has_header: bool = False
    context_before: str = ""
    context_after: str = ""
    status: ChunkStatus = ChunkStatus.CREATED

    def __post_init__(self):
        """Ensure character_count matches actual content length."""
        if self.character_count != len(self.content):
            self.character_count = len(self.content)

    def is_within_tolerance(self, config: ChunkingConfiguration) -> bool:
        """Check if chunk size is within acceptable range."""
        return config.min_size <= self.character_count <= config.max_size

    def is_oversized(self, config: ChunkingConfiguration) -> bool:
        """Check if chunk exceeds max tolerance."""
        return self.character_count > config.max_size

    def is_warning_size(self, config: ChunkingConfiguration) -> bool:
        """Check if chunk should trigger warning."""
        return self.character_count > config.warning_size


# === EPUB Chapter (T009) ===

@dataclass
class EPUBChapter:
    """Represents a single chapter/content file in the EPUB."""

    chapter_id: str
    chapter_index: int
    original_content: str
    title: Optional[str] = None
    translated_content: Optional[str] = None
    chunks: list = field(default_factory=list)
    character_count: int = 0
    chunk_count: int = 0

    def __post_init__(self):
        """Calculate character count from original content."""
        self.character_count = len(self.original_content)
        self.chunk_count = len(self.chunks)

    def update_chunk_count(self) -> None:
        """Update chunk_count to match actual chunks list."""
        self.chunk_count = len(self.chunks)


# === Chunk Statistics (T010) ===

@dataclass
class ChunkStatistics:
    """Aggregated metrics about chunking results."""

    total_chunks: int = 0
    total_characters: int = 0
    min_size: int = 0
    max_size: int = 0
    average_size: float = 0.0
    median_size: float = 0.0
    standard_deviation: float = 0.0
    within_tolerance_count: int = 0
    within_tolerance_percentage: float = 0.0
    undersized_count: int = 0
    oversized_count: int = 0
    warning_count: int = 0
    chunks_per_chapter: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_chunks": self.total_chunks,
            "total_characters": self.total_characters,
            "min_size": self.min_size,
            "max_size": self.max_size,
            "average_size": round(self.average_size, 2),
            "median_size": round(self.median_size, 2),
            "standard_deviation": round(self.standard_deviation, 2),
            "within_tolerance_count": self.within_tolerance_count,
            "within_tolerance_percentage": round(self.within_tolerance_percentage, 2),
            "undersized_count": self.undersized_count,
            "oversized_count": self.oversized_count,
            "warning_count": self.warning_count,
            "chunks_per_chapter": self.chunks_per_chapter
        }

    def summary(self) -> str:
        """Human-readable summary string."""
        return (
            f"Chunks: {self.total_chunks}, "
            f"Avg Size: {self.average_size:.0f} chars, "
            f"Within Tolerance: {self.within_tolerance_percentage:.1f}%, "
            f"Std Dev: {self.standard_deviation:.1f}"
        )


# === Chunk Boundary (T011) ===

@dataclass
class ChunkBoundary:
    """Describes where and why a chunk ends."""

    position: int
    type: BoundaryType
    confidence: float = 1.0
    original_punctuation: Optional[str] = None
    fallback_used: bool = False

    def __post_init__(self):
        """Validate boundary attributes."""
        if self.position < 0:
            raise ValueError(f"position must be >= 0, got {self.position}")

        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {self.confidence}")

        if self.fallback_used and self.confidence >= 1.0:
            # If fallback was used, confidence should be less than 1.0
            self.confidence = min(self.confidence, 0.9)
