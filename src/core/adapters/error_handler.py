"""
Unified error handling system that integrates exceptions, retry, recovery, and logging.

This module provides a high-level error handling interface that combines:
- Custom exceptions with context
- Retry logic with exponential backoff
- Error recovery strategies
- Comprehensive logging

Example usage:
    handler = ErrorHandler()

    async def risky_translation():
        # This will automatically retry, attempt recovery, and log everything
        return await handler.handle_operation(
            translate_func,
            content,
            operation_id="translate_chapter_5"
        )
"""

import asyncio
from typing import Optional, Callable, Any, Dict, List
from pathlib import Path

from .exceptions import (
    TranslationError,
    ContextOverflowError,
    RepetitionLoopError,
    PlaceholderValidationError,
    RetryExhaustedError,
    UnitTranslationError,
)
from .retry_manager import RetryManager, RetryConfig, RetryStrategy
from .error_recovery import ErrorRecoveryManager, RecoveryResult, GracefulDegradation
from .error_logger import ErrorLogger, ErrorLoggerContext


class ErrorHandler:
    """Unified error handling system."""

    def __init__(
        self,
        log_file: Optional[Path] = None,
        log_callback: Optional[Callable[[str, str], None]] = None,
        enable_retry: bool = True,
        enable_recovery: bool = True,
        enable_logging: bool = True,
        capture_stack_traces: bool = True
    ):
        """
        Args:
            log_file: Path to error log file
            log_callback: Callback for console logging (severity, message)
            enable_retry: Enable retry logic
            enable_recovery: Enable error recovery
            enable_logging: Enable error logging
            capture_stack_traces: Capture full stack traces in logs
        """
        self.enable_retry = enable_retry
        self.enable_recovery = enable_recovery
        self.enable_logging = enable_logging

        # Initialize components
        self.logger = ErrorLogger(
            log_file=log_file,
            console_callback=log_callback,
            capture_stack_traces=capture_stack_traces
        ) if enable_logging else None

        self.retry_manager = RetryManager(
            log_callback=log_callback
        ) if enable_retry else None

        self.recovery_manager = ErrorRecoveryManager(
            log_callback=log_callback
        ) if enable_recovery else None

    async def handle_operation(
        self,
        func: Callable[..., Any],
        *args,
        operation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        allow_partial_failure: bool = False,
        **kwargs
    ) -> Any:
        """Execute an operation with full error handling.

        This method automatically:
        1. Retries on recoverable errors
        2. Attempts recovery strategies
        3. Logs all errors
        4. Falls back gracefully

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            operation_id: Unique identifier for this operation
            context: Additional context for error logging
            allow_partial_failure: If True, return partial results instead of failing
            **kwargs: Keyword arguments for func

        Returns:
            Result of func

        Raises:
            TranslationError: If operation fails and cannot be recovered
        """
        op_id = operation_id or f"op_{id(func)}"

        # Logging context
        log_context = context or {}

        try:
            if self.enable_retry and self.retry_manager:
                # Execute with retry
                return await self.retry_manager.execute_with_retry(
                    func,
                    *args,
                    operation_id=op_id,
                    on_retry=lambda err, attempt: self._on_retry(err, attempt, op_id),
                    **kwargs
                )
            else:
                # Execute without retry
                return await func(*args, **kwargs)

        except ContextOverflowError as e:
            # Attempt recovery from context overflow
            if self.enable_recovery and self.recovery_manager:
                recovery = await self._handle_context_overflow(
                    e, func, args, kwargs, op_id, log_context
                )
                if recovery.success:
                    return recovery.data
            raise

        except RepetitionLoopError as e:
            # Attempt recovery from repetition loop
            if self.enable_recovery and self.recovery_manager:
                recovery = await self._handle_repetition_loop(
                    e, func, args, kwargs, op_id, log_context
                )
                if recovery.success:
                    return recovery.data
            raise

        except PlaceholderValidationError as e:
            # Attempt recovery from placeholder validation
            if self.enable_recovery and self.recovery_manager:
                recovery = await self._handle_placeholder_validation(
                    e, func, args, kwargs, op_id, log_context
                )
                if recovery.success:
                    return recovery.data
            raise

        except RetryExhaustedError as e:
            # All retries exhausted
            if self.enable_logging and self.logger:
                self.logger.log_recovery_failure(
                    e.original_error,
                    recovery_attempts=e.attempts,
                    context=log_context,
                    operation_id=op_id
                )

            if allow_partial_failure:
                # Return a graceful fallback
                return None
            raise

        except Exception as e:
            # Unexpected error
            if self.enable_logging and self.logger:
                self.logger.log_error(
                    e,
                    context=log_context,
                    operation_id=op_id
                )
            raise

    async def _handle_context_overflow(
        self,
        error: ContextOverflowError,
        func: Callable,
        args: tuple,
        kwargs: dict,
        operation_id: str,
        context: Dict[str, Any]
    ) -> RecoveryResult:
        """Handle context overflow with content splitting."""
        # Extract content from args (assume first arg is content)
        content = args[0] if args else kwargs.get('content', '')

        if not content or not isinstance(content, str):
            return RecoveryResult(
                success=False,
                message="Cannot split non-string content"
            )

        # Attempt recovery
        recovery = await self.recovery_manager.recover_from_context_overflow(
            content,
            lambda c: func(c, *args[1:], **kwargs),
            max_splits=3
        )

        # Log result
        if self.enable_logging and self.logger:
            if recovery.success:
                self.logger.log_recovery_success(
                    error,
                    recovery_method="content_splitting",
                    context={**context, "splits": recovery.message},
                    operation_id=operation_id
                )
            else:
                self.logger.log_error(
                    error,
                    context=context,
                    operation_id=operation_id,
                    recovered=False
                )

        return recovery

    async def _handle_repetition_loop(
        self,
        error: RepetitionLoopError,
        func: Callable,
        args: tuple,
        kwargs: dict,
        operation_id: str,
        context: Dict[str, Any]
    ) -> RecoveryResult:
        """Handle repetition loop with parameter adjustment."""
        content = args[0] if args else kwargs.get('content', '')
        params = kwargs.copy()

        recovery = await self.recovery_manager.recover_from_repetition_loop(
            content,
            lambda c, p: func(c, *args[1:], **{**kwargs, **p}),
            params
        )

        if self.enable_logging and self.logger:
            if recovery.success:
                self.logger.log_recovery_success(
                    error,
                    recovery_method="parameter_adjustment",
                    context={**context, "adjustments": recovery.message},
                    operation_id=operation_id
                )
            else:
                self.logger.log_error(
                    error,
                    context=context,
                    operation_id=operation_id,
                    recovered=False
                )

        return recovery

    async def _handle_placeholder_validation(
        self,
        error: PlaceholderValidationError,
        func: Callable,
        args: tuple,
        kwargs: dict,
        operation_id: str,
        context: Dict[str, Any]
    ) -> RecoveryResult:
        """Handle placeholder validation failure."""
        # This requires more context about placeholders
        # For now, just log and fail
        if self.enable_logging and self.logger:
            self.logger.log_error(
                error,
                context=context,
                operation_id=operation_id,
                recovered=False
            )

        return RecoveryResult(
            success=False,
            message="Placeholder validation recovery not implemented"
        )

    def _on_retry(self, error: Exception, attempt: int, operation_id: str):
        """Called before each retry attempt."""
        if self.enable_logging and self.logger:
            self.logger.log_error(
                error,
                context={"retry_attempt": attempt},
                operation_id=operation_id,
                recovered=False
            )

    async def handle_batch_operations(
        self,
        func: Callable,
        items: List[Any],
        operation_id: Optional[str] = None,
        max_concurrent: int = 5,
        allow_partial_failure: bool = True
    ) -> Dict[str, Any]:
        """Handle batch operations with individual error handling.

        Args:
            func: Async function to apply to each item
            items: List of items to process
            operation_id: Base operation ID
            max_concurrent: Maximum concurrent operations
            allow_partial_failure: Continue on individual failures

        Returns:
            Dict with 'successful', 'failed', and 'results' keys
        """
        successful = []
        failed = []
        results = []

        # Process in batches
        for i in range(0, len(items), max_concurrent):
            batch = items[i:i + max_concurrent]
            batch_op_id = f"{operation_id or 'batch'}_batch_{i // max_concurrent}"

            tasks = []
            for j, item in enumerate(batch):
                item_op_id = f"{batch_op_id}_item_{j}"
                task = self.handle_operation(
                    func,
                    item,
                    operation_id=item_op_id,
                    allow_partial_failure=allow_partial_failure
                )
                tasks.append(task)

            # Execute batch
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Categorize results
            for item, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    failed.append({
                        "item": item,
                        "error": result
                    })
                else:
                    successful.append(item)
                    results.append(result)

        # Attempt recovery for failed items
        if failed and self.enable_recovery and self.recovery_manager:
            recovery = await self.recovery_manager.recover_partial_results(
                failed,
                lambda item: self.handle_operation(
                    func,
                    item["item"],
                    operation_id=f"{operation_id}_recovery"
                )
            )

            if recovery.success:
                recovered_items = recovery.data.get("recovered", [])
                still_failed = recovery.data.get("still_failed", [])

                # Update results
                for recovered in recovered_items:
                    successful.append(recovered["unit"])
                    results.append(recovered["translation"])
                failed = still_failed

        return {
            "successful": successful,
            "failed": failed,
            "results": results,
            "success_rate": len(successful) / len(items) if items else 1.0
        }

    def get_error_summary(self) -> Optional[Dict[str, Any]]:
        """Get error summary from logger.

        Returns:
            Error summary dict or None if logging disabled
        """
        if self.enable_logging and self.logger:
            return self.logger.get_error_summary()
        return None

    def export_error_report(self, output_path: Path, format: str = "json"):
        """Export comprehensive error report.

        Args:
            output_path: Path to output file
            format: Report format ("json" or "text")
        """
        if self.enable_logging and self.logger:
            self.logger.export_report(output_path, format)

    def reset_stats(self):
        """Reset all statistics and state."""
        if self.logger:
            self.logger.clear()

        if self.retry_manager:
            self.retry_manager.reset()

        if self.recovery_manager:
            self.recovery_manager.reset_stats()


# Convenience function for quick error handling
async def with_error_handling(
    func: Callable[..., Any],
    *args,
    log_callback: Optional[Callable[[str, str], None]] = None,
    **kwargs
) -> Any:
    """Convenience function for quick error handling.

    Example:
        result = await with_error_handling(
            translate_text,
            "Hello world",
            log_callback=print
        )
    """
    handler = ErrorHandler(log_callback=log_callback)
    return await handler.handle_operation(func, *args, **kwargs)
