"""
Retry manager with exponential backoff and error recovery strategies.

This module provides sophisticated retry logic with:
- Exponential backoff with jitter
- Different strategies for different error types
- Circuit breaker pattern for repeated failures
- Comprehensive logging
"""

import asyncio
import time
import random
from typing import Optional, Callable, Any, Dict, Type, List
from dataclasses import dataclass
from enum import Enum

from .exceptions import (
    TranslationError,
    LLMError,
    ContextOverflowError,
    RepetitionLoopError,
    LLMConnectionError,
    LLMRateLimitError,
    LLMAuthenticationError,
    RetryExhaustedError,
)


class RetryStrategy(Enum):
    """Retry strategies for different error types."""
    EXPONENTIAL = "exponential"  # Standard exponential backoff
    LINEAR = "linear"  # Linear backoff
    IMMEDIATE = "immediate"  # No delay, retry immediately
    NONE = "none"  # Don't retry


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        backoff_factor: Multiplier for exponential backoff
        jitter: Add random jitter to delays (0.0-1.0)
        strategy: Retry strategy to use
    """
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: float = 0.1
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL


# Default retry configurations for different error types
DEFAULT_RETRY_CONFIGS: Dict[Type[Exception], RetryConfig] = {
    # Context overflow - retry with exponential backoff
    ContextOverflowError: RetryConfig(
        max_attempts=3,
        initial_delay=2.0,
        backoff_factor=2.0,
        strategy=RetryStrategy.EXPONENTIAL
    ),
    # Repetition loop - retry immediately with modified parameters
    RepetitionLoopError: RetryConfig(
        max_attempts=2,
        initial_delay=0.5,
        strategy=RetryStrategy.IMMEDIATE
    ),
    # Connection errors - retry with backoff
    LLMConnectionError: RetryConfig(
        max_attempts=5,
        initial_delay=2.0,
        max_delay=30.0,
        backoff_factor=2.0,
        strategy=RetryStrategy.EXPONENTIAL
    ),
    # Rate limit - wait longer
    LLMRateLimitError: RetryConfig(
        max_attempts=3,
        initial_delay=10.0,
        max_delay=120.0,
        backoff_factor=2.0,
        strategy=RetryStrategy.EXPONENTIAL
    ),
    # Authentication - don't retry
    LLMAuthenticationError: RetryConfig(
        max_attempts=1,
        strategy=RetryStrategy.NONE
    ),
    # Generic LLM errors - standard retry
    LLMError: RetryConfig(
        max_attempts=3,
        initial_delay=1.0,
        strategy=RetryStrategy.EXPONENTIAL
    ),
}


class CircuitBreaker:
    """Circuit breaker pattern to prevent cascading failures.

    After a threshold of failures, the circuit opens and fails fast
    for a timeout period before allowing retries again.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        success_threshold: int = 2
    ):
        """
        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before allowing retries
            success_threshold: Successes needed to close circuit
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold

        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = "closed"  # closed, open, half_open

    def record_success(self):
        """Record a successful operation."""
        if self._state == "half_open":
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._state = "closed"
                self._failure_count = 0
                self._success_count = 0
        elif self._state == "closed":
            self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self):
        """Record a failed operation."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.failure_threshold:
            self._state = "open"
            self._success_count = 0

    def can_attempt(self) -> bool:
        """Check if an attempt is allowed."""
        if self._state == "closed":
            return True

        if self._state == "open":
            # Check if timeout has elapsed
            if self._last_failure_time and (time.time() - self._last_failure_time) >= self.timeout:
                self._state = "half_open"
                self._success_count = 0
                return True
            return False

        # half_open state
        return True

    @property
    def state(self) -> str:
        """Current circuit state."""
        return self._state


class RetryManager:
    """Manages retry logic with exponential backoff and circuit breaking."""

    def __init__(
        self,
        default_config: Optional[RetryConfig] = None,
        custom_configs: Optional[Dict[Type[Exception], RetryConfig]] = None,
        enable_circuit_breaker: bool = True,
        log_callback: Optional[Callable[[str, str], None]] = None
    ):
        """
        Args:
            default_config: Default retry configuration
            custom_configs: Custom configs for specific error types
            enable_circuit_breaker: Enable circuit breaker pattern
            log_callback: Callback for logging (log_type, message)
        """
        self.default_config = default_config or RetryConfig()
        self.custom_configs = {**DEFAULT_RETRY_CONFIGS, **(custom_configs or {})}
        self.enable_circuit_breaker = enable_circuit_breaker
        self.log_callback = log_callback

        self._circuit_breaker = CircuitBreaker() if enable_circuit_breaker else None
        self._attempt_counts: Dict[str, int] = {}

    def _get_config(self, error: Exception) -> RetryConfig:
        """Get retry configuration for an error type."""
        error_type = type(error)

        # Check for exact match
        if error_type in self.custom_configs:
            return self.custom_configs[error_type]

        # Check for parent classes
        for exc_type, config in self.custom_configs.items():
            if isinstance(error, exc_type):
                return config

        return self.default_config

    def _calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """Calculate delay for the given attempt."""
        if config.strategy == RetryStrategy.IMMEDIATE:
            return 0.0

        if config.strategy == RetryStrategy.NONE:
            return 0.0

        if config.strategy == RetryStrategy.LINEAR:
            delay = config.initial_delay * attempt
        else:  # EXPONENTIAL
            delay = config.initial_delay * (config.backoff_factor ** (attempt - 1))

        # Apply max delay cap
        delay = min(delay, config.max_delay)

        # Add jitter
        if config.jitter > 0:
            jitter_amount = delay * config.jitter * random.random()
            delay += jitter_amount

        return delay

    def _log(self, log_type: str, message: str):
        """Internal logging helper."""
        if self.log_callback:
            self.log_callback(log_type, message)

    async def execute_with_retry(
        self,
        func: Callable[..., Any],
        *args,
        operation_id: Optional[str] = None,
        on_retry: Optional[Callable[[Exception, int], None]] = None,
        **kwargs
    ) -> Any:
        """Execute a function with retry logic.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            operation_id: Unique identifier for this operation
            on_retry: Callback called before each retry (error, attempt_number)
            **kwargs: Keyword arguments for func

        Returns:
            Result of func

        Raises:
            RetryExhaustedError: If all retries are exhausted
            Exception: If error is not recoverable
        """
        last_error: Optional[Exception] = None
        attempt = 0
        op_id = operation_id or f"op_{id(func)}"

        while True:
            attempt += 1

            # Check circuit breaker
            if self._circuit_breaker and not self._circuit_breaker.can_attempt():
                self._log(
                    "error",
                    f"Circuit breaker open for {op_id}, failing fast"
                )
                raise RetryExhaustedError(
                    "Circuit breaker is open, operation blocked",
                    original_error=last_error,
                    attempts=attempt - 1
                )

            try:
                # Execute the function
                result = await func(*args, **kwargs)

                # Success - record and return
                if self._circuit_breaker:
                    self._circuit_breaker.record_success()

                if attempt > 1:
                    self._log(
                        "info",
                        f"Operation {op_id} succeeded after {attempt} attempts"
                    )

                return result

            except Exception as error:
                last_error = error

                # Get retry config for this error type
                config = self._get_config(error)

                # Check if error is recoverable
                if isinstance(error, TranslationError) and not error.recoverable:
                    self._log(
                        "error",
                        f"Non-recoverable error in {op_id}: {error}"
                    )
                    raise

                # Check if we should retry
                if config.strategy == RetryStrategy.NONE or attempt >= config.max_attempts:
                    if self._circuit_breaker:
                        self._circuit_breaker.record_failure()

                    self._log(
                        "error",
                        f"Retry exhausted for {op_id} after {attempt} attempts: {error}"
                    )
                    raise RetryExhaustedError(
                        f"Maximum retry attempts ({config.max_attempts}) exceeded",
                        original_error=error,
                        attempts=attempt
                    )

                # Calculate delay
                delay = self._calculate_delay(attempt, config)

                # Log retry
                self._log(
                    "warning",
                    f"Attempt {attempt}/{config.max_attempts} failed for {op_id}: "
                    f"{type(error).__name__}: {error}. "
                    f"Retrying in {delay:.2f}s..."
                )

                # Call on_retry callback
                if on_retry:
                    try:
                        on_retry(error, attempt)
                    except Exception as callback_error:
                        self._log(
                            "warning",
                            f"Error in on_retry callback: {callback_error}"
                        )

                # Wait before retry
                if delay > 0:
                    await asyncio.sleep(delay)

    def reset(self, operation_id: Optional[str] = None):
        """Reset retry state for an operation or all operations.

        Args:
            operation_id: If provided, reset only this operation, otherwise reset all
        """
        if operation_id:
            self._attempt_counts.pop(operation_id, None)
        else:
            self._attempt_counts.clear()

        if self._circuit_breaker:
            self._circuit_breaker._failure_count = 0
            self._circuit_breaker._success_count = 0
            self._circuit_breaker._state = "closed"

    def get_circuit_state(self) -> Optional[str]:
        """Get current circuit breaker state."""
        return self._circuit_breaker.state if self._circuit_breaker else None


# Convenience decorator for retry
def with_retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
):
    """Decorator to add retry logic to async functions.

    Example:
        @with_retry(max_attempts=5, initial_delay=2.0)
        async def translate_chunk(text: str) -> str:
            # Translation logic that might fail
            pass
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                initial_delay=initial_delay,
                backoff_factor=backoff_factor,
                strategy=strategy
            )
            manager = RetryManager(default_config=config)
            return await manager.execute_with_retry(func, *args, **kwargs)
        return wrapper
    return decorator
