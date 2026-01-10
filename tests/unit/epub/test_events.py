"""Unit tests for Event system."""

import pytest
from src.core.epub.events import (
    EventBus,
    Event,
    EventType,
    create_chunk_translated_event,
    create_fallback_event,
    create_validation_failed_event,
    create_performance_metric_event
)


class TestEventBus:
    """Test EventBus functionality."""

    def test_subscribe_and_publish(self):
        """Subscribe to event and receive it when published."""
        bus = EventBus()
        received_events = []

        def handler(event: Event):
            received_events.append(event)

        bus.subscribe(EventType.CHUNK_TRANSLATED, handler)

        event = Event(type=EventType.CHUNK_TRANSLATED, data={"test": "data"})
        bus.publish(event)

        assert len(received_events) == 1
        assert received_events[0].type == EventType.CHUNK_TRANSLATED
        assert received_events[0].data["test"] == "data"

    def test_subscribe_multiple(self):
        """Subscribe to multiple event types with same handler."""
        bus = EventBus()
        received_events = []

        def handler(event: Event):
            received_events.append(event)

        bus.subscribe_multiple([
            EventType.CHUNK_STARTED,
            EventType.CHUNK_TRANSLATED,
            EventType.CHUNK_FAILED
        ], handler)

        bus.publish(Event(type=EventType.CHUNK_STARTED))
        bus.publish(Event(type=EventType.CHUNK_TRANSLATED))
        bus.publish(Event(type=EventType.CHUNK_FAILED))
        bus.publish(Event(type=EventType.FILE_STARTED))  # Not subscribed

        assert len(received_events) == 3

    def test_unsubscribe(self):
        """Unsubscribe from event type."""
        bus = EventBus()
        received_count = [0]

        def handler(event: Event):
            received_count[0] += 1

        bus.subscribe(EventType.CHUNK_TRANSLATED, handler)
        bus.publish(Event(type=EventType.CHUNK_TRANSLATED))
        assert received_count[0] == 1

        bus.unsubscribe(EventType.CHUNK_TRANSLATED, handler)
        bus.publish(Event(type=EventType.CHUNK_TRANSLATED))
        assert received_count[0] == 1  # Still 1, not incremented

    def test_event_history(self):
        """Test event history recording."""
        bus = EventBus()

        # History disabled by default
        bus.publish(Event(type=EventType.CHUNK_STARTED))
        assert len(bus.get_history()) == 0

        # Enable history
        bus.enable_history()
        bus.publish(Event(type=EventType.CHUNK_STARTED, data={"chunk": 1}))
        bus.publish(Event(type=EventType.CHUNK_TRANSLATED, data={"chunk": 1}))

        history = bus.get_history()
        assert len(history) == 2
        assert history[0].type == EventType.CHUNK_STARTED
        assert history[1].type == EventType.CHUNK_TRANSLATED

    def test_get_events_by_type(self):
        """Filter events by type from history."""
        bus = EventBus()
        bus.enable_history()

        bus.publish(Event(type=EventType.CHUNK_STARTED))
        bus.publish(Event(type=EventType.CHUNK_TRANSLATED))
        bus.publish(Event(type=EventType.CHUNK_STARTED))
        bus.publish(Event(type=EventType.CHUNK_FAILED))

        started_events = bus.get_events_by_type(EventType.CHUNK_STARTED)
        assert len(started_events) == 2

        failed_events = bus.get_events_by_type(EventType.CHUNK_FAILED)
        assert len(failed_events) == 1

    def test_clear_history(self):
        """Clear event history."""
        bus = EventBus()
        bus.enable_history()

        bus.publish(Event(type=EventType.CHUNK_STARTED))
        bus.publish(Event(type=EventType.CHUNK_TRANSLATED))
        assert len(bus.get_history()) == 2

        bus.clear_history()
        assert len(bus.get_history()) == 0

    def test_listener_exception_handling(self):
        """Listener exceptions should not crash the bus."""
        bus = EventBus()
        received = []

        def failing_handler(event: Event):
            raise ValueError("Handler error")

        def working_handler(event: Event):
            received.append(event)

        bus.subscribe(EventType.CHUNK_TRANSLATED, failing_handler)
        bus.subscribe(EventType.CHUNK_TRANSLATED, working_handler)

        # Should not raise, working_handler should still receive
        bus.publish(Event(type=EventType.CHUNK_TRANSLATED))

        assert len(received) == 1


class TestEventBuilders:
    """Test convenience event builder functions."""

    def test_create_chunk_translated_event(self):
        """Create chunk translated event."""
        event = create_chunk_translated_event(
            chunk_index=5,
            total_chunks=10,
            success=True,
            retry_count=2
        )

        assert event.type == EventType.CHUNK_TRANSLATED
        assert event.data["chunk_index"] == 5
        assert event.data["total_chunks"] == 10
        assert event.data["success"] is True
        assert event.data["retry_count"] == 2
        assert event.data["progress"] == 0.6  # (5+1)/10
        assert event.source == "chunk_translator"

    def test_create_fallback_event(self):
        """Create fallback event."""
        event = create_fallback_event(
            chunk_index=3,
            reason="validation_failed"
        )

        assert event.type == EventType.FALLBACK_USED
        assert event.data["chunk_index"] == 3
        assert event.data["reason"] == "validation_failed"
        assert event.source == "chunk_translator"

    def test_create_validation_failed_event(self):
        """Create validation failed event."""
        event = create_validation_failed_event(
            chunk_index=2,
            expected_count=5,
            actual_count=3,
            error_message="Missing placeholders"
        )

        assert event.type == EventType.PLACEHOLDER_VALIDATION_FAILED
        assert event.data["chunk_index"] == 2
        assert event.data["expected_count"] == 5
        assert event.data["actual_count"] == 3
        assert event.data["error_message"] == "Missing placeholders"
        assert event.source == "placeholder_validator"

    def test_create_performance_metric_event(self):
        """Create performance metric event."""
        event = create_performance_metric_event(
            stage="chunking",
            metric_name="chunk_count",
            value=15
        )

        assert event.type == EventType.PERFORMANCE_METRIC
        assert event.data["stage"] == "chunking"
        assert event.data["metric_name"] == "chunk_count"
        assert event.data["value"] == 15
        assert event.source == "chunking"


class TestEvent:
    """Test Event dataclass."""

    def test_event_creation(self):
        """Create event with all fields."""
        event = Event(
            type=EventType.CHUNK_STARTED,
            data={"chunk_index": 1},
            source="test"
        )

        assert event.type == EventType.CHUNK_STARTED
        assert event.data["chunk_index"] == 1
        assert event.source == "test"
        assert isinstance(event.timestamp, float)

    def test_event_default_values(self):
        """Event should have default values."""
        event = Event(type=EventType.CHUNK_STARTED)

        assert event.data == {}
        assert event.source == "unknown"
        assert event.timestamp > 0
