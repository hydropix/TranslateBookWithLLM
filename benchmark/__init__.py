"""
Benchmark module for multilingual translation quality testing.

This module provides tools for:
- Running translation benchmarks across multiple languages and models
- Evaluating translation quality via LLM (OpenRouter)
- Generating GitHub wiki pages with results
"""

from benchmark.config import BenchmarkConfig
from benchmark.models import (
    Language,
    LanguageCategory,
    ReferenceText,
    TranslationResult,
    EvaluationScores,
    BenchmarkRun,
)

__version__ = "1.0.0"

__all__ = [
    "BenchmarkConfig",
    "Language",
    "LanguageCategory",
    "ReferenceText",
    "TranslationResult",
    "EvaluationScores",
    "BenchmarkRun",
]
