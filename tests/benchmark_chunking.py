#!/usr/bin/env python3
"""
Performance Benchmark: Character-Based Chunking vs Line-Based Chunking

Compares the performance overhead of the new character-based chunking algorithm
against the traditional line-based chunking approach.

Usage:
    python benchmark_chunking.py
    python benchmark_chunking.py --iterations 100
"""

import os
import sys
import time
import argparse
import statistics

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.chunking import (
    ChunkingConfiguration,
    chunk_text_by_characters,
    calculate_chunk_statistics,
)
from src.core.text_processor import split_text_into_chunks_with_context


def generate_test_text(size_chars=50000):
    """Generate test text of approximately given size."""
    paragraphs = []
    current_size = 0
    para_num = 0

    while current_size < size_chars:
        para_num += 1
        # Create paragraph with varying sentence lengths
        sentences = [
            f"This is sentence {para_num}.1 in our test text. ",
            f"Here is sentence {para_num}.2 with more content to add variety. ",
            f"Sentence {para_num}.3 continues the paragraph. ",
            f"Dr. Smith and Mr. Jones discussed this in sentence {para_num}.4. ",
            f"Finally, sentence {para_num}.5 concludes this paragraph."
        ]
        paragraph = "".join(sentences)
        paragraphs.append(paragraph)
        current_size += len(paragraph) + 2  # +2 for newlines

    return "\n\n".join(paragraphs)


def benchmark_character_chunking(text, config, iterations=10):
    """Benchmark character-based chunking."""
    times = []

    for _ in range(iterations):
        start = time.perf_counter()
        chunks = chunk_text_by_characters(text, config=config, chapter_id="test", chapter_index=0)
        end = time.perf_counter()
        times.append(end - start)

    return {
        'method': 'Character-Based Chunking',
        'iterations': iterations,
        'total_time': sum(times),
        'avg_time': statistics.mean(times),
        'min_time': min(times),
        'max_time': max(times),
        'std_dev': statistics.stdev(times) if len(times) > 1 else 0,
        'chunk_count': len(chunks),
        'chunks': chunks,
    }


def benchmark_line_chunking(text, chunk_size_lines=25, iterations=10):
    """Benchmark line-based chunking."""
    times = []
    chunk_count = 0
    chunks = []

    for _ in range(iterations):
        start = time.perf_counter()
        # split_text_into_chunks_with_context expects text string
        result_chunks = split_text_into_chunks_with_context(text, chunk_size_lines)
        end = time.perf_counter()
        times.append(end - start)
        chunk_count = len(result_chunks)
        chunks = result_chunks

    return {
        'method': 'Line-Based Chunking',
        'iterations': iterations,
        'total_time': sum(times),
        'avg_time': statistics.mean(times),
        'min_time': min(times),
        'max_time': max(times),
        'std_dev': statistics.stdev(times) if len(times) > 1 else 0,
        'chunk_count': chunk_count,
        'chunks': chunks,
    }


def compare_chunk_quality(char_result, line_result, config):
    """Compare chunk quality metrics."""
    # Character-based statistics
    char_stats = calculate_chunk_statistics(char_result['chunks'], config)

    # Line-based size analysis
    # line_result['chunks'] contains dicts with 'main_content' key (list of strings)
    line_sizes = []
    for chunk in line_result['chunks']:
        if isinstance(chunk, dict) and 'main_content' in chunk:
            # Join lines and count characters
            content = '\n'.join(chunk['main_content'])
            line_sizes.append(len(content))
        else:
            # Fallback if structure is different
            line_sizes.append(len(str(chunk)))

    if line_sizes:
        line_avg = statistics.mean(line_sizes)
        line_min = min(line_sizes)
        line_max = max(line_sizes)
        line_std = statistics.stdev(line_sizes) if len(line_sizes) > 1 else 0

        # Calculate "within target" for line-based (using same target)
        min_target = config.target_size * config.min_tolerance
        max_target = config.target_size * config.max_tolerance
        line_within = sum(1 for s in line_sizes if min_target <= s <= max_target)
        line_within_pct = (line_within / len(line_sizes)) * 100 if line_sizes else 0
    else:
        line_avg = line_min = line_max = line_std = line_within_pct = 0

    return {
        'character_based': {
            'total_chunks': char_stats.total_chunks,
            'avg_size': char_stats.average_size,
            'min_size': char_stats.min_size,
            'max_size': char_stats.max_size,
            'std_dev': char_stats.standard_deviation,
            'within_tolerance_pct': char_stats.within_tolerance_percentage,
            'oversized_count': char_stats.oversized_count,
        },
        'line_based': {
            'total_chunks': len(line_sizes),
            'avg_size': line_avg,
            'min_size': line_min,
            'max_size': line_max,
            'std_dev': line_std,
            'within_tolerance_pct': line_within_pct,
        }
    }


def print_benchmark_results(char_result, line_result, quality_comparison):
    """Print formatted benchmark results."""
    print("\n" + "=" * 70)
    print("PERFORMANCE BENCHMARK: Character-Based vs Line-Based Chunking")
    print("=" * 70)

    # Performance comparison
    print("\n1. PERFORMANCE METRICS")
    print("-" * 70)
    print(f"{'Metric':<25} {'Character-Based':>20} {'Line-Based':>20}")
    print("-" * 70)

    print(f"{'Iterations':<25} {char_result['iterations']:>20} {line_result['iterations']:>20}")
    print(f"{'Avg Time (ms)':<25} {char_result['avg_time']*1000:>20.4f} {line_result['avg_time']*1000:>20.4f}")
    print(f"{'Min Time (ms)':<25} {char_result['min_time']*1000:>20.4f} {line_result['min_time']*1000:>20.4f}")
    print(f"{'Max Time (ms)':<25} {char_result['max_time']*1000:>20.4f} {line_result['max_time']*1000:>20.4f}")
    print(f"{'Std Dev (ms)':<25} {char_result['std_dev']*1000:>20.4f} {line_result['std_dev']*1000:>20.4f}")
    print(f"{'Total Chunks':<25} {char_result['chunk_count']:>20} {line_result['chunk_count']:>20}")

    # Calculate overhead
    if line_result['avg_time'] > 0:
        overhead_pct = ((char_result['avg_time'] - line_result['avg_time']) / line_result['avg_time']) * 100
        overhead_str = f"{overhead_pct:+.2f}%"
    else:
        overhead_str = "N/A"

    print(f"\nPerformance Overhead: {overhead_str}")

    # Quality comparison
    print("\n2. CHUNK QUALITY METRICS")
    print("-" * 70)
    print(f"{'Metric':<25} {'Character-Based':>20} {'Line-Based':>20}")
    print("-" * 70)

    char_q = quality_comparison['character_based']
    line_q = quality_comparison['line_based']

    print(f"{'Total Chunks':<25} {char_q['total_chunks']:>20} {line_q['total_chunks']:>20}")
    print(f"{'Avg Size (chars)':<25} {char_q['avg_size']:>20.1f} {line_q['avg_size']:>20.1f}")
    print(f"{'Min Size (chars)':<25} {char_q['min_size']:>20} {line_q['min_size']:>20}")
    print(f"{'Max Size (chars)':<25} {char_q['max_size']:>20} {line_q['max_size']:>20}")
    print(f"{'Std Dev (chars)':<25} {char_q['std_dev']:>20.1f} {line_q['std_dev']:>20.1f}")
    print(f"{'Within Tolerance %':<25} {char_q['within_tolerance_pct']:>19.1f}% {line_q['within_tolerance_pct']:>19.1f}%")

    if 'oversized_count' in char_q:
        print(f"{'Oversized Chunks':<25} {char_q['oversized_count']:>20} {'N/A':>20}")

    # Summary
    print("\n3. SUMMARY")
    print("-" * 70)

    # Performance assessment
    if char_result['avg_time'] < line_result['avg_time'] * 2:
        perf_grade = "EXCELLENT"
        perf_note = "Character-based chunking has minimal overhead"
    elif char_result['avg_time'] < line_result['avg_time'] * 5:
        perf_grade = "GOOD"
        perf_note = "Character-based chunking has acceptable overhead"
    else:
        perf_grade = "MODERATE"
        perf_note = "Character-based chunking has noticeable overhead"

    print(f"Performance: {perf_grade} - {perf_note}")

    # Quality assessment
    if char_q['within_tolerance_pct'] >= 80:
        qual_grade = "EXCELLENT"
        qual_note = f"Meets target: {char_q['within_tolerance_pct']:.1f}% within tolerance"
    elif char_q['within_tolerance_pct'] >= 60:
        qual_grade = "GOOD"
        qual_note = f"Near target: {char_q['within_tolerance_pct']:.1f}% within tolerance"
    else:
        qual_grade = "NEEDS IMPROVEMENT"
        qual_note = f"Below target: {char_q['within_tolerance_pct']:.1f}% within tolerance"

    print(f"Quality: {qual_grade} - {qual_note}")

    # Consistency improvement
    if line_q['std_dev'] > 0:
        consistency_improvement = ((line_q['std_dev'] - char_q['std_dev']) / line_q['std_dev']) * 100
        print(f"Consistency Improvement: {consistency_improvement:+.1f}% (lower std dev is better)")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Benchmark chunking performance")
    parser.add_argument("--iterations", type=int, default=50, help="Number of benchmark iterations")
    parser.add_argument("--text-size", type=int, default=50000, help="Test text size in characters")
    parser.add_argument("--target-size", type=int, default=2500, help="Target chunk size in characters")

    args = parser.parse_args()

    print(f"Generating test text ({args.text_size} characters)...")
    test_text = generate_test_text(args.text_size)
    actual_size = len(test_text)
    print(f"Generated {actual_size} characters of test text")

    # Configure character-based chunking
    config = ChunkingConfiguration(
        target_size=args.target_size,
        min_tolerance=0.8,
        max_tolerance=1.2,
        warning_threshold=1.5,
    )

    print(f"\nRunning {args.iterations} iterations for each method...")

    # Benchmark character-based chunking
    print("Benchmarking character-based chunking...")
    char_result = benchmark_character_chunking(test_text, config, args.iterations)

    # Benchmark line-based chunking
    print("Benchmarking line-based chunking...")
    line_result = benchmark_line_chunking(test_text, chunk_size_lines=25, iterations=args.iterations)

    # Compare quality
    quality = compare_chunk_quality(char_result, line_result, config)

    # Print results
    print_benchmark_results(char_result, line_result, quality)


if __name__ == "__main__":
    main()
