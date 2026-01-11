"""
Event system for translation pipeline observability.

Provides decoupled event publishing and subscription for monitoring
translation progress and debugging.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List
import time


class EventType(Enum):
    """Translation pipeline event types."""

    # High-level events
    TRANSLATION_STARTED = "translation_started"
    TRANSLATION_COMPLETED = "translation_completed"
    TRANSLATION_FAILED = "translation_failed"

    # File-level events
    FILE_STARTED = "file_started"
    FILE_COMPLETED = "file_completed"
    FILE_FAILED = "file_failed"

    # Chunk-level events
    CHUNK_STARTED = "chunk_started"
    CHUNK_TRANSLATED = "chunk_translated"
    CHUNK_RETRY = "chunk_retry"
    CHUNK_FAILED = "chunk_failed"

    # Validation events
    PLACEHOLDER_VALIDATION_PASSED = "placeholder_validation_passed"
    PLACEHOLDER_VALIDATION_FAILED = "placeholder_validation_failed"
    PLACEHOLDER_CORRECTION_ATTEMPTED = "placeholder_correction_attempted"

    # Fallback events
    FALLBACK_USED = "fallback_used"

    # Performance events
    PERFORMANCE_METRIC = "performance_metric"


@dataclass
class Event:
    """Translation pipeline event.

    Attributes:
        type: Event type
        data: Event-specific data dictionary
        timestamp: Unix timestamp when event occurred
        source: Optional source identifier (e.g., "chunk_translator")
    """
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str = "unknown"


class EventBus:
    """Central event bus for translation pipeline."""

    def __init__(self):
        """Initialize event bus."""
        self._listeners: Dict[EventType, List[Callable]] = {}
        self._history: List[Event] = []
        self._record_history = False

    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """Subscribe to an event type.

        Args:
            event_type: Type of event to listen for
            callback: Function to call when event occurs (receives Event object)
        """
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def subscribe_multiple(
        self,
        event_types: List[EventType],
        callback: Callable[[Event], None]
    ) -> None:
        """Subscribe to multiple event types with same callback.

        Args:
            event_types: List of event types
            callback: Callback function
        """
        for event_type in event_types:
            self.subscribe(event_type, callback)

    def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        """Unsubscribe from an event type.

        Args:
            event_type: Event type
            callback: Previously registered callback
        """
        if event_type in self._listeners:
            try:
                self._listeners[event_type].remove(callback)
            except ValueError:
                pass  # Callback not found

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers.

        Args:
            event: Event to publish
        """
        # Record in history if enabled
        if self._record_history:
            self._history.append(event)

        # Call all subscribers
        listeners = self._listeners.get(event.type, [])
        for listener in listeners:
            try:
                listener(event)
            except Exception as e:
                # Don't let listener errors crash the pipeline
                import traceback
                from src.utils.unified_logger import log, LogType
                log(LogType.GENERAL, "event_listener_error", f"Event listener failed: {e}")
                traceback.print_exc()

    def enable_history(self) -> None:
        """Enable event history recording."""
        self._record_history = True

    def disable_history(self) -> None:
        """Disable event history recording."""
        self._record_history = False

    def get_history(self) -> List[Event]:
        """Get recorded event history.

        Returns:
            List of events in chronological order
        """
        return self._history.copy()

    def clear_history(self) -> None:
        """Clear event history."""
        self._history.clear()

    def get_events_by_type(self, event_type: EventType) -> List[Event]:
        """Get all events of a specific type from history.

        Args:
            event_type: Event type to filter

        Returns:
            List of matching events
        """
        return [e for e in self._history if e.type == event_type]


# === Convenience Event Builders ===

def create_chunk_translated_event(
    chunk_index: int,
    total_chunks: int,
    success: bool,
    retry_count: int = 0
) -> Event:
    """Create chunk translation event.

    Args:
        chunk_index: Index of translated chunk
        total_chunks: Total number of chunks
        success: Whether translation succeeded
        retry_count: Number of retries attempted

    Returns:
        Event object
    """
    return Event(
        type=EventType.CHUNK_TRANSLATED,
        data={
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "success": success,
            "retry_count": retry_count,
            "progress": (chunk_index + 1) / total_chunks if total_chunks > 0 else 0
        },
        source="chunk_translator"
    )


def create_fallback_event(chunk_index: int, reason: str) -> Event:
    """Create fallback usage event.

    Args:
        chunk_index: Chunk that used fallback
        reason: Reason for fallback

    Returns:
        Event object
    """
    return Event(
        type=EventType.FALLBACK_USED,
        data={
            "chunk_index": chunk_index,
            "reason": reason
        },
        source="chunk_translator"
    )


def create_validation_failed_event(
    chunk_index: int,
    expected_count: int,
    actual_count: int,
    error_message: str
) -> Event:
    """Create placeholder validation failed event.

    Args:
        chunk_index: Chunk that failed validation
        expected_count: Expected placeholder count
        actual_count: Actual placeholder count
        error_message: Validation error message

    Returns:
        Event object
    """
    return Event(
        type=EventType.PLACEHOLDER_VALIDATION_FAILED,
        data={
            "chunk_index": chunk_index,
            "expected_count": expected_count,
            "actual_count": actual_count,
            "error_message": error_message
        },
        source="placeholder_validator"
    )


def create_performance_metric_event(
    stage: str,
    metric_name: str,
    value: Any
) -> Event:
    """Create performance metric event.

    Args:
        stage: Pipeline stage name
        metric_name: Name of the metric
        value: Metric value

    Returns:
        Event object
    """
    return Event(
        type=EventType.PERFORMANCE_METRIC,
        data={
            "stage": stage,
            "metric_name": metric_name,
            "value": value
        },
        source=stage
    )
