"""
Wiki generation module for benchmark results.

Generates GitHub wiki pages from benchmark data:
- Home.md: Overview with rankings and summaries
- languages/[Language].md: Per-language results
- models/[Model].md: Per-model results
"""

from .generator import WikiGenerator

__all__ = ["WikiGenerator"]
