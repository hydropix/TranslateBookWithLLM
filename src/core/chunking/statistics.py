"""
Statistics calculation for chunk analysis.

Provides metrics for evaluating chunking quality and consistency.
"""

import statistics as stats_module
from typing import List
from .models import TextChunk, ChunkStatistics, ChunkingConfiguration, StatisticsCalculationError


def calculate_chunk_statistics(
    chunks: List[TextChunk],
    config: ChunkingConfiguration
) -> ChunkStatistics:
    """
    Generate aggregate statistics for chunk size analysis.

    Args:
        chunks: List of all chunks from translation job
        config: Configuration used for chunking (for tolerance calculations)

    Returns:
        ChunkStatistics object with all metrics calculated
    """
    if not chunks:
        return ChunkStatistics()

    try:
        # Extract sizes
        sizes = [chunk.character_count for chunk in chunks]
        total_chunks = len(sizes)
        total_characters = sum(sizes)

        # Basic statistics
        min_size = min(sizes)
        max_size = max(sizes)
        average_size = stats_module.mean(sizes)

        if total_chunks > 1:
            median_size = stats_module.median(sizes)
            standard_deviation = stats_module.stdev(sizes)
        else:
            median_size = sizes[0]
            standard_deviation = 0.0

        # Tolerance analysis
        within_tolerance_count = 0
        undersized_count = 0
        oversized_count = 0
        warning_count = 0

        # Exclude the last chunk from undersized calculation (it's allowed to be smaller)
        for i, chunk in enumerate(chunks):
            if chunk.is_within_tolerance(config):
                within_tolerance_count += 1
            elif chunk.character_count < config.min_size:
                # Only count as undersized if not the last chunk
                if i < total_chunks - 1:
                    undersized_count += 1
            else:  # oversized
                oversized_count += 1

            if chunk.is_warning_size(config):
                warning_count += 1

        # Calculate percentage
        if total_chunks > 0:
            within_tolerance_percentage = (within_tolerance_count / total_chunks) * 100
        else:
            within_tolerance_percentage = 0.0

        # Chunks per chapter breakdown
        chunks_per_chapter = {}
        for chunk in chunks:
            chapter_id = chunk.chapter_id
            if chapter_id not in chunks_per_chapter:
                chunks_per_chapter[chapter_id] = 0
            chunks_per_chapter[chapter_id] += 1

        return ChunkStatistics(
            total_chunks=total_chunks,
            total_characters=total_characters,
            min_size=min_size,
            max_size=max_size,
            average_size=average_size,
            median_size=median_size,
            standard_deviation=standard_deviation,
            within_tolerance_count=within_tolerance_count,
            within_tolerance_percentage=within_tolerance_percentage,
            undersized_count=undersized_count,
            oversized_count=oversized_count,
            warning_count=warning_count,
            chunks_per_chapter=chunks_per_chapter
        )

    except Exception as e:
        raise StatisticsCalculationError(f"Error computing statistics: {str(e)}")
