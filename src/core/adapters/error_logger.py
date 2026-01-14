"""
Comprehensive error logging system for translation operations.

This module provides structured logging with:
- Error context preservation
- Stack trace capture
- Error categorization
- Performance metrics
- Exportable error reports
"""

import json
import traceback
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, asdict
from enum import Enum

from .exceptions import TranslationError


class ErrorSeverity(Enum):
    """Error severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ErrorRecord:
    """Record of an error occurrence.

    Attributes:
        timestamp: When the error occurred
        error_type: Type of exception
        message: Error message
        severity: Error severity level
        context: Additional context data
        stack_trace: Stack trace if available
        recoverable: Whether error was recoverable
        recovered: Whether error was successfully recovered
        recovery_method: Method used for recovery
        operation_id: ID of the operation that failed
        unit_id: ID of translation unit (if applicable)
    """
    timestamp: str
    error_type: str
    message: str
    severity: str
    context: Dict[str, Any]
    stack_trace: Optional[str] = None
    recoverable: bool = False
    recovered: bool = False
    recovery_method: Optional[str] = None
    operation_id: Optional[str] = None
    unit_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class ErrorLogger:
    """Comprehensive error logging system."""

    def __init__(
        self,
        log_file: Optional[Path] = None,
        console_callback: Optional[Callable[[str, str], None]] = None,
        capture_stack_traces: bool = True,
        max_context_size: int = 1000
    ):
        """
        Args:
            log_file: Path to log file (if None, only in-memory)
            console_callback: Callback for console logging (severity, message)
            capture_stack_traces: Whether to capture full stack traces
            max_context_size: Maximum size for context values (chars)
        """
        self.log_file = log_file
        self.console_callback = console_callback
        self.capture_stack_traces = capture_stack_traces
        self.max_context_size = max_context_size

        self._error_records: List[ErrorRecord] = []
        self._error_counts: Dict[str, int] = {}
        self._session_start = time.time()

        # Initialize log file
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def _truncate_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Truncate large context values."""
        truncated = {}
        for key, value in context.items():
            if isinstance(value, str) and len(value) > self.max_context_size:
                truncated[key] = value[:self.max_context_size] + "... (truncated)"
            else:
                truncated[key] = value
        return truncated

    def _get_severity(self, error: Exception) -> ErrorSeverity:
        """Determine severity level for an error."""
        if isinstance(error, TranslationError):
            if not error.recoverable:
                return ErrorSeverity.CRITICAL
            return ErrorSeverity.ERROR

        # Default severities for common error types
        error_type_name = type(error).__name__
        if "Warning" in error_type_name:
            return ErrorSeverity.WARNING
        if "Critical" in error_type_name or "Fatal" in error_type_name:
            return ErrorSeverity.CRITICAL

        return ErrorSeverity.ERROR

    def log_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        operation_id: Optional[str] = None,
        unit_id: Optional[str] = None,
        recovered: bool = False,
        recovery_method: Optional[str] = None
    ) -> ErrorRecord:
        """Log an error with full context.

        Args:
            error: The exception that occurred
            context: Additional context information
            operation_id: ID of the operation
            unit_id: ID of translation unit
            recovered: Whether error was recovered
            recovery_method: Method used for recovery

        Returns:
            ErrorRecord for the logged error
        """
        # Prepare context
        error_context = context or {}
        if isinstance(error, TranslationError) and error.context:
            error_context = {**error.context, **error_context}

        # Truncate large values
        error_context = self._truncate_context(error_context)

        # Capture stack trace
        stack_trace = None
        if self.capture_stack_traces:
            stack_trace = "".join(traceback.format_exception(
                type(error), error, error.__traceback__
            ))

        # Determine severity
        severity = self._get_severity(error)

        # Create record
        record = ErrorRecord(
            timestamp=datetime.now().isoformat(),
            error_type=type(error).__name__,
            message=str(error),
            severity=severity.value,
            context=error_context,
            stack_trace=stack_trace,
            recoverable=isinstance(error, TranslationError) and error.recoverable,
            recovered=recovered,
            recovery_method=recovery_method,
            operation_id=operation_id,
            unit_id=unit_id
        )

        # Store record
        self._error_records.append(record)
        self._error_counts[record.error_type] = self._error_counts.get(record.error_type, 0) + 1

        # Write to file
        if self.log_file:
            self._write_to_file(record)

        # Console callback
        if self.console_callback:
            self._log_to_console(record)

        return record

    def _write_to_file(self, record: ErrorRecord):
        """Write error record to log file."""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(record.to_json() + "\n")
        except Exception as e:
            print(f"Failed to write to log file: {e}")

    def _log_to_console(self, record: ErrorRecord):
        """Log to console via callback."""
        severity = record.severity
        message = f"[{record.error_type}] {record.message}"

        if record.operation_id:
            message = f"[{record.operation_id}] {message}"

        if record.recovered:
            message += f" (recovered via {record.recovery_method})"

        self.console_callback(severity, message)

    def log_recovery_success(
        self,
        original_error: Exception,
        recovery_method: str,
        context: Optional[Dict[str, Any]] = None,
        operation_id: Optional[str] = None
    ):
        """Log successful error recovery.

        Args:
            original_error: The error that was recovered from
            recovery_method: Method used for recovery
            context: Additional context
            operation_id: ID of the operation
        """
        self.log_error(
            original_error,
            context=context,
            operation_id=operation_id,
            recovered=True,
            recovery_method=recovery_method
        )

    def log_recovery_failure(
        self,
        original_error: Exception,
        recovery_attempts: int,
        context: Optional[Dict[str, Any]] = None,
        operation_id: Optional[str] = None
    ):
        """Log failed error recovery.

        Args:
            original_error: The error that could not be recovered
            recovery_attempts: Number of recovery attempts made
            context: Additional context
            operation_id: ID of the operation
        """
        ctx = context or {}
        ctx['recovery_attempts'] = recovery_attempts
        ctx['recovery_failed'] = True

        self.log_error(
            original_error,
            context=ctx,
            operation_id=operation_id,
            recovered=False
        )

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of all logged errors.

        Returns:
            Dict with error statistics
        """
        total_errors = len(self._error_records)
        recovered = sum(1 for r in self._error_records if r.recovered)
        critical = sum(1 for r in self._error_records if r.severity == ErrorSeverity.CRITICAL.value)

        severity_counts = {}
        for record in self._error_records:
            severity_counts[record.severity] = severity_counts.get(record.severity, 0) + 1

        return {
            "total_errors": total_errors,
            "recovered": recovered,
            "unrecovered": total_errors - recovered,
            "critical": critical,
            "error_types": self._error_counts.copy(),
            "severity_counts": severity_counts,
            "session_duration": time.time() - self._session_start,
            "recovery_rate": recovered / total_errors if total_errors > 0 else 0.0
        }

    def get_errors_by_type(self, error_type: str) -> List[ErrorRecord]:
        """Get all errors of a specific type.

        Args:
            error_type: Name of error type

        Returns:
            List of matching error records
        """
        return [r for r in self._error_records if r.error_type == error_type]

    def get_errors_by_operation(self, operation_id: str) -> List[ErrorRecord]:
        """Get all errors for a specific operation.

        Args:
            operation_id: Operation identifier

        Returns:
            List of matching error records
        """
        return [r for r in self._error_records if r.operation_id == operation_id]

    def get_unrecovered_errors(self) -> List[ErrorRecord]:
        """Get all errors that were not recovered.

        Returns:
            List of unrecovered error records
        """
        return [r for r in self._error_records if not r.recovered]

    def get_critical_errors(self) -> List[ErrorRecord]:
        """Get all critical errors.

        Returns:
            List of critical error records
        """
        return [r for r in self._error_records if r.severity == ErrorSeverity.CRITICAL.value]

    def export_report(self, output_path: Path, format: str = "json"):
        """Export comprehensive error report.

        Args:
            output_path: Path to output file
            format: Report format ("json" or "text")
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            self._export_json_report(output_path)
        else:
            self._export_text_report(output_path)

    def _export_json_report(self, output_path: Path):
        """Export JSON format report."""
        report = {
            "summary": self.get_error_summary(),
            "errors": [r.to_dict() for r in self._error_records]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)

    def _export_text_report(self, output_path: Path):
        """Export text format report."""
        with open(output_path, 'w', encoding='utf-8') as f:
            # Header
            f.write("=" * 80 + "\n")
            f.write("ERROR REPORT\n")
            f.write("=" * 80 + "\n\n")

            # Summary
            summary = self.get_error_summary()
            f.write("SUMMARY\n")
            f.write("-" * 80 + "\n")
            for key, value in summary.items():
                if key == "error_types":
                    f.write(f"{key}:\n")
                    for error_type, count in value.items():
                        f.write(f"  {error_type}: {count}\n")
                elif key == "severity_counts":
                    f.write(f"{key}:\n")
                    for severity, count in value.items():
                        f.write(f"  {severity}: {count}\n")
                else:
                    f.write(f"{key}: {value}\n")
            f.write("\n")

            # Detailed errors
            f.write("DETAILED ERRORS\n")
            f.write("-" * 80 + "\n\n")

            for i, record in enumerate(self._error_records, 1):
                f.write(f"Error #{i}\n")
                f.write(f"  Timestamp: {record.timestamp}\n")
                f.write(f"  Type: {record.error_type}\n")
                f.write(f"  Severity: {record.severity}\n")
                f.write(f"  Message: {record.message}\n")
                if record.operation_id:
                    f.write(f"  Operation: {record.operation_id}\n")
                if record.unit_id:
                    f.write(f"  Unit: {record.unit_id}\n")
                f.write(f"  Recoverable: {record.recoverable}\n")
                f.write(f"  Recovered: {record.recovered}\n")
                if record.recovery_method:
                    f.write(f"  Recovery Method: {record.recovery_method}\n")
                if record.context:
                    f.write(f"  Context: {json.dumps(record.context, indent=4)}\n")
                if record.stack_trace:
                    f.write(f"  Stack Trace:\n")
                    for line in record.stack_trace.split('\n'):
                        f.write(f"    {line}\n")
                f.write("\n")

    def clear(self):
        """Clear all error records and reset statistics."""
        self._error_records.clear()
        self._error_counts.clear()
        self._session_start = time.time()


class ErrorLoggerContext:
    """Context manager for error logging.

    Example:
        with ErrorLoggerContext(logger, operation_id="translate_unit_5") as ctx:
            # Operations that might fail
            result = translate(content)

        # Errors are automatically logged with operation_id
    """

    def __init__(
        self,
        logger: ErrorLogger,
        operation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        self.logger = logger
        self.operation_id = operation_id
        self.context = context or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            self.logger.log_error(
                exc_val,
                context=self.context,
                operation_id=self.operation_id
            )
        return False  # Don't suppress exceptions
