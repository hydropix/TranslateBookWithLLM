"""Unit tests for TranslationMetrics."""

import pytest
import time
from src.core.epub.html_chunker import TranslationMetrics


class TestTranslationMetrics:
    """Test TranslationMetrics functionality."""

    def test_initialization(self):
        """Metrics should initialize with correct defaults."""
        metrics = TranslationMetrics()

        assert metrics.total_chunks == 0
        assert metrics.successful_first_try == 0
        assert metrics.successful_after_retry == 0
        assert metrics.fallback_used == 0
        assert metrics.failed_chunks == 0
        assert metrics.total_tokens_processed == 0
        assert metrics.total_tokens_generated == 0
        assert metrics.retry_distribution == {}
        assert metrics.start_time > 0

    def test_record_success_first_try(self):
        """Record successful first try."""
        metrics = TranslationMetrics()
        metrics.record_success(attempt=0, chunk_size=100)

        assert metrics.total_chunks == 1
        assert metrics.successful_first_try == 1
        assert metrics.successful_after_retry == 0
        assert metrics.retry_distribution[0] == 1

    def test_record_success_after_retry(self):
        """Record success after retries."""
        metrics = TranslationMetrics()
        metrics.record_success(attempt=2, chunk_size=150)

        assert metrics.total_chunks == 1
        assert metrics.successful_first_try == 0
        assert metrics.successful_after_retry == 1
        assert metrics.retry_distribution[2] == 1

    def test_record_fallback(self):
        """Record fallback usage."""
        metrics = TranslationMetrics()
        metrics.record_fallback(chunk_size=200)

        assert metrics.total_chunks == 1
        assert metrics.fallback_used == 1

    def test_record_failure(self):
        """Record failed translation."""
        metrics = TranslationMetrics()
        metrics.record_failure(chunk_size=100)

        assert metrics.total_chunks == 1
        assert metrics.failed_chunks == 1

    def test_chunk_size_stats(self):
        """Track chunk size statistics."""
        metrics = TranslationMetrics()

        metrics.record_success(attempt=0, chunk_size=100)
        metrics.record_success(attempt=0, chunk_size=200)
        metrics.record_success(attempt=0, chunk_size=150)

        assert metrics.min_chunk_size == 100
        assert metrics.max_chunk_size == 200
        assert metrics.avg_chunk_size == 150.0  # (100 + 200 + 150) / 3

    def test_retry_distribution(self):
        """Track retry distribution."""
        metrics = TranslationMetrics()

        metrics.record_success(attempt=0, chunk_size=100)
        metrics.record_success(attempt=0, chunk_size=100)
        metrics.record_success(attempt=0, chunk_size=100)
        metrics.record_success(attempt=1, chunk_size=100)
        metrics.record_success(attempt=1, chunk_size=100)
        metrics.record_success(attempt=2, chunk_size=100)

        assert metrics.retry_distribution[0] == 3
        assert metrics.retry_distribution[1] == 2
        assert metrics.retry_distribution[2] == 1

    def test_success_rate(self):
        """Calculate success rate."""
        metrics = TranslationMetrics()

        metrics.record_success(attempt=0, chunk_size=100)  # Success
        metrics.record_success(attempt=1, chunk_size=100)  # Success
        metrics.record_fallback(chunk_size=100)  # Not counted as success
        metrics.record_failure(chunk_size=100)  # Failed

        # 2 successful out of 4 total
        assert metrics.success_rate == 0.5

    def test_first_try_rate(self):
        """Calculate first-try success rate."""
        metrics = TranslationMetrics()

        metrics.record_success(attempt=0, chunk_size=100)
        metrics.record_success(attempt=0, chunk_size=100)
        metrics.record_success(attempt=1, chunk_size=100)
        metrics.record_success(attempt=2, chunk_size=100)

        # 2 first-try successes out of 4 total
        assert metrics.first_try_rate == 0.5

    def test_timing_metrics(self):
        """Track timing metrics."""
        metrics = TranslationMetrics()

        start_time = metrics.start_time
        time.sleep(0.01)  # Small delay
        metrics.finalize()

        assert metrics.end_time > start_time
        assert metrics.total_time_seconds > 0

    def test_avg_time_per_chunk(self):
        """Calculate average time per chunk."""
        metrics = TranslationMetrics()

        metrics.record_success(attempt=0, chunk_size=100)
        metrics.record_success(attempt=0, chunk_size=100)

        time.sleep(0.02)
        metrics.finalize()

        assert metrics.avg_time_per_chunk > 0
        assert metrics.avg_time_per_chunk == metrics.total_time_seconds / 2

    def test_to_dict(self):
        """Convert metrics to dictionary."""
        metrics = TranslationMetrics()

        metrics.record_success(attempt=0, chunk_size=100)
        metrics.record_success(attempt=1, chunk_size=150)
        metrics.record_fallback(chunk_size=200)
        metrics.finalize()

        result = metrics.to_dict()

        assert result["total_chunks"] == 3
        assert result["successful_first_try"] == 1
        assert result["successful_after_retry"] == 1
        assert result["fallback_used"] == 1
        assert "avg_chunk_size" in result
        assert "success_rate" in result
        assert "retry_distribution" in result

    def test_log_summary(self, capsys):
        """Log summary to console."""
        metrics = TranslationMetrics()

        metrics.record_success(attempt=0, chunk_size=100)
        metrics.record_success(attempt=1, chunk_size=150)
        metrics.record_fallback(chunk_size=200)
        metrics.finalize()

        metrics.log_summary()

        captured = capsys.readouterr()
        output = captured.out

        assert "Translation Metrics Summary" in output
        assert "Total Chunks: 3" in output
        assert "Success (first try):" in output
        assert "Fallback Used:" in output

    def test_log_summary_with_callback(self):
        """Log summary with callback."""
        metrics = TranslationMetrics()
        logged_messages = []

        def callback(tag, message):
            logged_messages.append((tag, message))

        metrics.record_success(attempt=0, chunk_size=100)
        metrics.finalize()

        metrics.log_summary(log_callback=callback)

        assert len(logged_messages) == 1
        assert logged_messages[0][0] == "translation_metrics"
        assert "Translation Metrics Summary" in logged_messages[0][1]

    def test_empty_metrics(self):
        """Handle empty metrics gracefully."""
        metrics = TranslationMetrics()

        # Should not crash with division by zero
        assert metrics.success_rate == 0.0
        assert metrics.first_try_rate == 0.0
        assert metrics.avg_chunk_size == 0.0
        assert metrics.avg_time_per_chunk == 0.0

    def test_realistic_scenario(self):
        """Test realistic translation scenario."""
        metrics = TranslationMetrics()

        # Simulate 100 chunks
        for i in range(100):
            if i < 80:
                # 80% succeed on first try
                metrics.record_success(attempt=0, chunk_size=100 + i)
            elif i < 95:
                # 15% succeed after retry
                metrics.record_success(attempt=1, chunk_size=100 + i)
            else:
                # 5% use fallback
                metrics.record_fallback(chunk_size=100 + i)

        metrics.finalize()

        assert metrics.total_chunks == 100
        assert metrics.successful_first_try == 80
        assert metrics.successful_after_retry == 15
        assert metrics.fallback_used == 5
        assert metrics.success_rate == 0.95
        assert metrics.first_try_rate == 0.8
        assert metrics.retry_distribution[0] == 80
        assert metrics.retry_distribution[1] == 15
