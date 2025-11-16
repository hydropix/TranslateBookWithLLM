"""
Unit tests for chunk statistics calculation.

Tests for User Story 1 (US1) - Consistent Chunk Sizes for Translation.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.chunking.statistics import calculate_chunk_statistics
from core.chunking.models import (
    TextChunk,
    ChunkStatistics,
    ChunkingConfiguration,
    BoundaryType,
    StatisticsCalculationError,
)


class TestCalculateChunkStatistics:
    """Test statistics calculation function."""

    def test_empty_chunks_list(self):
        """Should handle empty chunks list."""
        config = ChunkingConfiguration(target_size=2500)
        stats = calculate_chunk_statistics([], config)

        assert isinstance(stats, ChunkStatistics)
        # Default values for empty list
        assert stats.total_chunks == 0

    def test_single_chunk_statistics(self):
        """Should calculate statistics for single chunk."""
        config = ChunkingConfiguration(target_size=2500)
        chunk = TextChunk(
            content="x" * 2500,
            character_count=2500,
            chunk_index=0,
            chapter_id="ch1",
            chapter_index=0,
            boundary_type=BoundaryType.SENTENCE_END
        )

        stats = calculate_chunk_statistics([chunk], config)

        assert stats.total_chunks == 1
        assert stats.total_characters == 2500
        assert stats.min_size == 2500
        assert stats.max_size == 2500
        assert stats.average_size == 2500.0
        assert stats.median_size == 2500.0
        assert stats.standard_deviation == 0.0

    def test_multiple_chunks_basic_stats(self):
        """Should calculate basic stats for multiple chunks."""
        config = ChunkingConfiguration(target_size=2500)
        chunks = [
            TextChunk("x" * 2000, 2000, 0, "ch1", 0, BoundaryType.SENTENCE_END),
            TextChunk("x" * 2500, 2500, 1, "ch1", 0, BoundaryType.SENTENCE_END),
            TextChunk("x" * 3000, 3000, 2, "ch1", 0, BoundaryType.SENTENCE_END),
        ]

        stats = calculate_chunk_statistics(chunks, config)

        assert stats.total_chunks == 3
        assert stats.total_characters == 7500
        assert stats.min_size == 2000
        assert stats.max_size == 3000
        assert stats.average_size == 2500.0

    def test_within_tolerance_count(self):
        """Should count chunks within tolerance correctly."""
        config = ChunkingConfiguration(target_size=2500)  # min=2000, max=3000
        chunks = [
            TextChunk("x" * 2500, 2500, 0, "ch1", 0, BoundaryType.SENTENCE_END),  # Within
            TextChunk("x" * 2000, 2000, 1, "ch1", 0, BoundaryType.SENTENCE_END),  # At min
            TextChunk("x" * 3000, 3000, 2, "ch1", 0, BoundaryType.SENTENCE_END),  # At max
            TextChunk("x" * 1500, 1500, 3, "ch1", 0, BoundaryType.SENTENCE_END),  # Under (but last)
        ]

        stats = calculate_chunk_statistics(chunks, config)

        # First 3 are within tolerance, last one is undersized but it's the final chunk
        assert stats.within_tolerance_count == 3
        assert stats.undersized_count == 0  # Last chunk excluded from undersized count

    def test_undersized_count_excludes_last_chunk(self):
        """Should not count last chunk as undersized."""
        config = ChunkingConfiguration(target_size=2500)  # min=2000
        chunks = [
            TextChunk("x" * 2500, 2500, 0, "ch1", 0, BoundaryType.SENTENCE_END),
            TextChunk("x" * 1500, 1500, 1, "ch1", 0, BoundaryType.SENTENCE_END),  # Under
            TextChunk("x" * 500, 500, 2, "ch1", 0, BoundaryType.SENTENCE_END),  # Under but last
        ]

        stats = calculate_chunk_statistics(chunks, config)

        # Only middle chunk should be counted as undersized
        assert stats.undersized_count == 1

    def test_oversized_count(self):
        """Should count oversized chunks correctly."""
        config = ChunkingConfiguration(target_size=2500)  # max=3000
        chunks = [
            TextChunk("x" * 2500, 2500, 0, "ch1", 0, BoundaryType.SENTENCE_END),  # OK
            TextChunk("x" * 3500, 3500, 1, "ch1", 0, BoundaryType.SENTENCE_END),  # Oversized
            TextChunk("x" * 4000, 4000, 2, "ch1", 0, BoundaryType.SENTENCE_END),  # Oversized
        ]

        stats = calculate_chunk_statistics(chunks, config)

        assert stats.oversized_count == 2

    def test_warning_count(self):
        """Should count chunks exceeding warning threshold."""
        config = ChunkingConfiguration(target_size=2500, warning_threshold=1.5)  # warning=3750
        chunks = [
            TextChunk("x" * 2500, 2500, 0, "ch1", 0, BoundaryType.SENTENCE_END),  # OK
            TextChunk("x" * 3000, 3000, 1, "ch1", 0, BoundaryType.SENTENCE_END),  # OK
            TextChunk("x" * 4000, 4000, 2, "ch1", 0, BoundaryType.SENTENCE_END),  # Warning
        ]

        stats = calculate_chunk_statistics(chunks, config)

        assert stats.warning_count == 1

    def test_within_tolerance_percentage(self):
        """Should calculate percentage correctly."""
        config = ChunkingConfiguration(target_size=2500)
        chunks = [
            TextChunk("x" * 2500, 2500, 0, "ch1", 0, BoundaryType.SENTENCE_END),  # Within
            TextChunk("x" * 2500, 2500, 1, "ch1", 0, BoundaryType.SENTENCE_END),  # Within
            TextChunk("x" * 3500, 3500, 2, "ch1", 0, BoundaryType.SENTENCE_END),  # Over
            TextChunk("x" * 2500, 2500, 3, "ch1", 0, BoundaryType.SENTENCE_END),  # Within
        ]

        stats = calculate_chunk_statistics(chunks, config)

        # 3 out of 4 = 75%
        assert stats.within_tolerance_percentage == 75.0

    def test_eighty_percent_conformance_target(self):
        """Should identify when 80% conformance is met."""
        config = ChunkingConfiguration(target_size=2500)
        # Create 10 chunks: 8 within tolerance, 2 outside
        chunks = []
        for i in range(8):
            chunks.append(TextChunk("x" * 2500, 2500, i, "ch1", 0, BoundaryType.SENTENCE_END))
        chunks.append(TextChunk("x" * 3500, 3500, 8, "ch1", 0, BoundaryType.SENTENCE_END))
        chunks.append(TextChunk("x" * 1500, 1500, 9, "ch1", 0, BoundaryType.SENTENCE_END))

        stats = calculate_chunk_statistics(chunks, config)

        # 8 out of 10 = 80%
        assert stats.within_tolerance_percentage == 80.0

    def test_standard_deviation_calculation(self):
        """Should calculate standard deviation correctly."""
        config = ChunkingConfiguration(target_size=2500)
        chunks = [
            TextChunk("x" * 2000, 2000, 0, "ch1", 0, BoundaryType.SENTENCE_END),
            TextChunk("x" * 2500, 2500, 1, "ch1", 0, BoundaryType.SENTENCE_END),
            TextChunk("x" * 3000, 3000, 2, "ch1", 0, BoundaryType.SENTENCE_END),
        ]

        stats = calculate_chunk_statistics(chunks, config)

        # Mean = 2500, deviations = [-500, 0, 500]
        # Variance = (250000 + 0 + 250000) / 2 = 250000
        # StdDev = sqrt(250000) = 500
        assert abs(stats.standard_deviation - 500.0) < 1.0

    def test_median_calculation_odd_count(self):
        """Should calculate median for odd number of chunks."""
        config = ChunkingConfiguration(target_size=2500)
        chunks = [
            TextChunk("x" * 1000, 1000, 0, "ch1", 0, BoundaryType.SENTENCE_END),
            TextChunk("x" * 2000, 2000, 1, "ch1", 0, BoundaryType.SENTENCE_END),
            TextChunk("x" * 3000, 3000, 2, "ch1", 0, BoundaryType.SENTENCE_END),
        ]

        stats = calculate_chunk_statistics(chunks, config)

        assert stats.median_size == 2000.0

    def test_median_calculation_even_count(self):
        """Should calculate median for even number of chunks."""
        config = ChunkingConfiguration(target_size=2500)
        chunks = [
            TextChunk("x" * 1000, 1000, 0, "ch1", 0, BoundaryType.SENTENCE_END),
            TextChunk("x" * 2000, 2000, 1, "ch1", 0, BoundaryType.SENTENCE_END),
            TextChunk("x" * 3000, 3000, 2, "ch1", 0, BoundaryType.SENTENCE_END),
            TextChunk("x" * 4000, 4000, 3, "ch1", 0, BoundaryType.SENTENCE_END),
        ]

        stats = calculate_chunk_statistics(chunks, config)

        # Median of [1000, 2000, 3000, 4000] = (2000 + 3000) / 2 = 2500
        assert stats.median_size == 2500.0

    def test_chunks_per_chapter_breakdown(self):
        """Should track chunks per chapter."""
        config = ChunkingConfiguration(target_size=2500)
        chunks = [
            TextChunk("x" * 2500, 2500, 0, "chapter_1", 0, BoundaryType.SENTENCE_END),
            TextChunk("x" * 2500, 2500, 1, "chapter_1", 0, BoundaryType.SENTENCE_END),
            TextChunk("x" * 2500, 2500, 0, "chapter_2", 1, BoundaryType.SENTENCE_END),
            TextChunk("x" * 2500, 2500, 1, "chapter_2", 1, BoundaryType.SENTENCE_END),
            TextChunk("x" * 2500, 2500, 2, "chapter_2", 1, BoundaryType.SENTENCE_END),
        ]

        stats = calculate_chunk_statistics(chunks, config)

        assert stats.chunks_per_chapter["chapter_1"] == 2
        assert stats.chunks_per_chapter["chapter_2"] == 3
        assert sum(stats.chunks_per_chapter.values()) == stats.total_chunks

    def test_to_dict_method(self):
        """Should convert statistics to dictionary."""
        config = ChunkingConfiguration(target_size=2500)
        chunk = TextChunk("x" * 2500, 2500, 0, "ch1", 0, BoundaryType.SENTENCE_END)
        stats = calculate_chunk_statistics([chunk], config)

        stats_dict = stats.to_dict()

        assert isinstance(stats_dict, dict)
        assert "total_chunks" in stats_dict
        assert "average_size" in stats_dict
        assert "within_tolerance_percentage" in stats_dict

    def test_summary_method(self):
        """Should generate human-readable summary."""
        config = ChunkingConfiguration(target_size=2500)
        chunk = TextChunk("x" * 2500, 2500, 0, "ch1", 0, BoundaryType.SENTENCE_END)
        stats = calculate_chunk_statistics([chunk], config)

        summary = stats.summary()

        assert isinstance(summary, str)
        assert "Chunks:" in summary
        assert "Avg Size:" in summary
        assert "Within Tolerance:" in summary

    def test_real_world_scenario(self):
        """Should handle realistic chunking scenario."""
        config = ChunkingConfiguration(target_size=2500, min_tolerance=0.8, max_tolerance=1.2)

        # Simulate typical EPUB chunking: varying sizes around target
        sizes = [2100, 2450, 2700, 2500, 2300, 2900, 2400, 2550, 2200, 1500]  # Last is small
        chunks = []
        for i, size in enumerate(sizes):
            chunks.append(TextChunk("x" * size, size, i, "ch1", 0, BoundaryType.SENTENCE_END))

        stats = calculate_chunk_statistics(chunks, config)

        # Basic sanity checks
        assert stats.total_chunks == 10
        assert stats.total_characters == sum(sizes)
        assert stats.min_size == min(sizes)
        assert stats.max_size == max(sizes)
        assert stats.average_size == sum(sizes) / len(sizes)

        # 9 out of 10 are within tolerance (2000-3000), last one is small but excluded
        # Actually: 2100, 2450, 2700, 2500, 2300, 2900, 2400, 2550, 2200 = 9 within, 1500 = small
        # All except 1500 are in range, 1500 is last so not counted as undersized
        assert stats.within_tolerance_percentage >= 80.0


class TestChunkStatisticsDataClass:
    """Test ChunkStatistics dataclass methods."""

    def test_default_values(self):
        """Should have sensible defaults."""
        stats = ChunkStatistics()

        assert stats.total_chunks == 0
        assert stats.total_characters == 0
        assert stats.min_size == 0
        assert stats.max_size == 0
        assert stats.average_size == 0.0
        assert stats.median_size == 0.0
        assert stats.standard_deviation == 0.0
        assert stats.within_tolerance_count == 0
        assert stats.within_tolerance_percentage == 0.0
        assert stats.undersized_count == 0
        assert stats.oversized_count == 0
        assert stats.warning_count == 0
        assert stats.chunks_per_chapter == {}

    def test_to_dict_completeness(self):
        """Should include all fields in dictionary."""
        stats = ChunkStatistics(
            total_chunks=5,
            total_characters=12500,
            min_size=2000,
            max_size=3000,
            average_size=2500.0,
            median_size=2500.0,
            standard_deviation=350.0,
            within_tolerance_count=4,
            within_tolerance_percentage=80.0,
            undersized_count=0,
            oversized_count=1,
            warning_count=0,
            chunks_per_chapter={"ch1": 3, "ch2": 2}
        )

        d = stats.to_dict()

        assert d["total_chunks"] == 5
        assert d["total_characters"] == 12500
        assert d["min_size"] == 2000
        assert d["max_size"] == 3000
        assert d["average_size"] == 2500.0
        assert d["median_size"] == 2500.0
        assert d["standard_deviation"] == 350.0
        assert d["within_tolerance_count"] == 4
        assert d["within_tolerance_percentage"] == 80.0
        assert d["undersized_count"] == 0
        assert d["oversized_count"] == 1
        assert d["warning_count"] == 0
        assert d["chunks_per_chapter"] == {"ch1": 3, "ch2": 2}

    def test_summary_format(self):
        """Should format summary string correctly."""
        stats = ChunkStatistics(
            total_chunks=10,
            total_characters=25000,
            min_size=2000,
            max_size=3000,
            average_size=2500.0,
            median_size=2450.0,
            standard_deviation=250.5,
            within_tolerance_count=8,
            within_tolerance_percentage=80.0,
            undersized_count=1,
            oversized_count=1,
            warning_count=0,
            chunks_per_chapter={"ch1": 10}
        )

        summary = stats.summary()

        # Check format: "Chunks: 10, Avg Size: 2500 chars, Within Tolerance: 80.0%, Std Dev: 250.5"
        assert "Chunks: 10" in summary
        assert "2500" in summary
        assert "80.0%" in summary
        assert "250.5" in summary
