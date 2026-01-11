"""Translation metrics and statistics tracking.

This module contains classes for tracking translation statistics and metrics.
Extracted from html_chunker.py as part of Phase 2 refactoring.
"""

import time
import warnings
from dataclasses import dataclass, field
from typing import Dict


class TranslationStats:
    """Track statistics for translation attempts and fallbacks.

    Translation flow:
    1. Phase 1: Normal translation (with retry attempts)
    2. Phase 2: Token alignment fallback (translate without placeholders, reinsert proportionally)
    3. Phase 3: Untranslated fallback (if all retries fail, returns original text)

    .. deprecated::
        This class is maintained for backward compatibility. New code should use
        :class:`TranslationMetrics` which provides more comprehensive tracking.
    """

    def __init__(self):
        # Issue deprecation warning
        warnings.warn(
            "TranslationStats is deprecated and will be removed in a future version. "
            "Please use TranslationMetrics instead for enhanced metrics tracking.",
            DeprecationWarning,
            stacklevel=2
        )

        self.total_chunks = 0
        self.successful_first_try = 0
        self.successful_after_retry = 0  # Success on 2nd+ retry attempt (Phase 1)
        self.retry_attempts = 0  # Total number of retry attempts made
        self.token_alignment_used = 0  # Phase 2: Token alignment fallback used
        self.token_alignment_success = 0  # Phase 2: Token alignment succeeded
        self.fallback_used = 0  # Phase 3: Chunks returned untranslated after all phases failed
        self.placeholder_errors = 0  # Total placeholder validation errors encountered
        self.correction_attempts = 0  # Total LLM correction attempts made
        self.correction_success = 0  # Successful LLM corrections

    def log_summary(self, log_callback=None):
        """Log a summary of translation statistics."""
        summary_lines = [
            "=== Translation Summary ===",
            f"Total chunks: {self.total_chunks}",
            f"Success 1st try: {self.successful_first_try} ({self._pct(self.successful_first_try)}%)",
            f"Success after retry: {self.successful_after_retry} ({self._pct(self.successful_after_retry)}%)",
            f"Total retry attempts: {self.retry_attempts}",
        ]

        # Phase 2 stats (token alignment)
        if self.token_alignment_used > 0:
            summary_lines.extend([
                f"Token alignment fallback used: {self.token_alignment_used} ({self._pct(self.token_alignment_used)}%)",
                f"Token alignment success: {self.token_alignment_success}/{self.token_alignment_used} ({self._pct_of(self.token_alignment_success, self.token_alignment_used)}%)",
            ])

        # Phase 3 stats (untranslated fallback)
        if self.fallback_used > 0:
            summary_lines.append(f"Untranslated chunks (Phase 3 fallback): {self.fallback_used} ({self._pct(self.fallback_used)}%)")

        # Placeholder error tracking
        if self.placeholder_errors > 0:
            summary_lines.extend([
                "",
                "=== Placeholder Issues ===",
                f"Placeholder validation errors: {self.placeholder_errors}",
            ])
            if self.correction_attempts > 0:
                summary_lines.append(f"LLM correction attempts: {self.correction_attempts} (success: {self.correction_success})")

        # Recommendations
        if self.token_alignment_used > 0 or self.fallback_used > 0:
            summary_lines.extend([
                "",
                "=== Recommendations ===",
            ])

            if self.token_alignment_used > 0:
                summary_lines.append(
                    f"⚠️ {self.token_alignment_used} chunks used token alignment fallback (Phase 2)."
                )
                summary_lines.append(
                    "   This can cause minor layout imperfections due to proportional tag repositioning."
                )

            if self.fallback_used > 0:
                summary_lines.append(
                    f"⚠️ {self.fallback_used} chunks could not be translated (Phase 3 fallback)."
                )
                summary_lines.append(
                    "   These chunks remain in the source language."
                )

            summary_lines.extend([
                "",
                "To improve translation quality, consider:",
                "  • Using a more capable LLM model",
                "  • Reducing MAX_TOKENS_PER_CHUNK in .env (e.g., from 400 to 150)",
            ])

        summary = "\n".join(summary_lines)

        if log_callback:
            log_callback("translation_stats", summary)
        return summary

    def _pct(self, value):
        """Calculate percentage of total chunks."""
        if self.total_chunks == 0:
            return 0
        return round(value / self.total_chunks * 100, 1)

    def _pct_of(self, value, total):
        """Calculate percentage of a specific total."""
        if total == 0:
            return 0
        return round(value / total * 100, 1)

    def merge(self, other: 'TranslationStats') -> None:
        """Merge statistics from another TranslationStats instance.

        Args:
            other: Another TranslationStats instance to merge
        """
        self.total_chunks += other.total_chunks
        self.successful_first_try += other.successful_first_try
        self.successful_after_retry += other.successful_after_retry
        self.retry_attempts += other.retry_attempts
        self.token_alignment_used += other.token_alignment_used
        self.token_alignment_success += other.token_alignment_success
        self.fallback_used += other.fallback_used
        self.placeholder_errors += other.placeholder_errors
        self.correction_attempts += other.correction_attempts
        self.correction_success += other.correction_success


@dataclass
class TranslationMetrics:
    """Comprehensive translation metrics.

    Tracks counts, timing, token usage, and retry distribution.
    This is an enhanced version of TranslationStats for Phase 3 refactoring.
    """
    # === Counts ===
    total_chunks: int = 0
    successful_first_try: int = 0
    successful_after_retry: int = 0
    fallback_used: int = 0  # Chunks returned untranslated after all retries failed
    failed_chunks: int = 0

    # === Timing ===
    total_time_seconds: float = 0.0
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0

    # === Token Usage ===
    total_tokens_processed: int = 0
    total_tokens_generated: int = 0

    # === Retry Distribution ===
    retry_distribution: Dict[int, int] = field(default_factory=dict)
    """Map of retry_count -> number_of_chunks. Example: {0: 85, 1: 10, 2: 5}"""

    # === Chunk Size Stats ===
    min_chunk_size: int = field(default_factory=lambda: float('inf'))
    max_chunk_size: int = 0
    total_chunk_size: int = 0

    def record_success(self, attempt: int, chunk_size: int) -> None:
        """Record successful translation.

        Args:
            attempt: Attempt number (0 = first try)
            chunk_size: Size of chunk in tokens
        """
        self.total_chunks += 1

        if attempt == 0:
            self.successful_first_try += 1
        else:
            self.successful_after_retry += 1

        # Update retry distribution
        self.retry_distribution[attempt] = self.retry_distribution.get(attempt, 0) + 1

        # Update chunk size stats
        self._update_chunk_stats(chunk_size)

    def record_fallback(self, chunk_size: int) -> None:
        """Record fallback usage (untranslated chunk returned).

        Args:
            chunk_size: Size of chunk in tokens
        """
        self.total_chunks += 1
        self.fallback_used += 1
        self._update_chunk_stats(chunk_size)

    def record_failure(self, chunk_size: int) -> None:
        """Record failed translation.

        Args:
            chunk_size: Size of chunk in tokens
        """
        self.total_chunks += 1
        self.failed_chunks += 1
        self._update_chunk_stats(chunk_size)

    def _update_chunk_stats(self, chunk_size: int) -> None:
        """Update chunk size statistics."""
        self.min_chunk_size = min(self.min_chunk_size, chunk_size)
        self.max_chunk_size = max(self.max_chunk_size, chunk_size)
        self.total_chunk_size += chunk_size

    def finalize(self) -> None:
        """Finalize metrics (call when translation completes)."""
        self.end_time = time.time()
        self.total_time_seconds = self.end_time - self.start_time

    @property
    def avg_time_per_chunk(self) -> float:
        """Average time per chunk in seconds."""
        if self.total_chunks == 0:
            return 0.0
        return self.total_time_seconds / self.total_chunks

    @property
    def avg_chunk_size(self) -> float:
        """Average chunk size in tokens."""
        if self.total_chunks == 0:
            return 0.0
        return self.total_chunk_size / self.total_chunks

    @property
    def success_rate(self) -> float:
        """Success rate (excludes fallbacks)."""
        if self.total_chunks == 0:
            return 0.0
        successful = self.successful_first_try + self.successful_after_retry
        return successful / self.total_chunks

    @property
    def first_try_rate(self) -> float:
        """First-try success rate."""
        if self.total_chunks == 0:
            return 0.0
        return self.successful_first_try / self.total_chunks

    def to_dict(self) -> Dict:
        """Convert metrics to dictionary for serialization."""
        return {
            "total_chunks": self.total_chunks,
            "successful_first_try": self.successful_first_try,
            "successful_after_retry": self.successful_after_retry,
            "fallback_used": self.fallback_used,
            "failed_chunks": self.failed_chunks,
            "total_time_seconds": self.total_time_seconds,
            "avg_time_per_chunk": self.avg_time_per_chunk,
            "total_tokens_processed": self.total_tokens_processed,
            "total_tokens_generated": self.total_tokens_generated,
            "avg_chunk_size": self.avg_chunk_size,
            "min_chunk_size": self.min_chunk_size if self.min_chunk_size != float('inf') else 0,
            "max_chunk_size": self.max_chunk_size,
            "success_rate": self.success_rate,
            "first_try_rate": self.first_try_rate,
            "retry_distribution": self.retry_distribution
        }

    def log_summary(self, log_callback=None) -> None:
        """Log comprehensive summary.

        Args:
            log_callback: Optional callback for logging
        """
        summary = f"""
=== Translation Metrics Summary ===
Total Chunks: {self.total_chunks}
Success (first try): {self.successful_first_try} ({self.first_try_rate:.1%})
Success (after retry): {self.successful_after_retry}
Untranslated (fallback): {self.fallback_used}
Failed: {self.failed_chunks}

Overall Success Rate: {self.success_rate:.1%}

Timing:
  Total Time: {self.total_time_seconds:.2f}s
  Avg per Chunk: {self.avg_time_per_chunk:.2f}s

Tokens:
  Processed: {self.total_tokens_processed:,}
  Generated: {self.total_tokens_generated:,}

Chunk Sizes:
  Min: {self.min_chunk_size if self.min_chunk_size != float('inf') else 0} tokens
  Max: {self.max_chunk_size} tokens
  Avg: {self.avg_chunk_size:.1f} tokens

Retry Distribution:
"""
        for attempt, count in sorted(self.retry_distribution.items()):
            percentage = (count / self.total_chunks * 100) if self.total_chunks > 0 else 0
            summary += f"  {attempt} retries: {count} chunks ({percentage:.1f}%)\n"

        if log_callback:
            log_callback("translation_metrics", summary)
        else:
            print(summary)
