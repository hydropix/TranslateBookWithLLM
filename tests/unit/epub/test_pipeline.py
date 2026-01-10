"""Unit tests for Pipeline pattern."""

import pytest
from src.core.epub.pipeline import (
    PipelineStage,
    TranslationPipeline,
    TagPreservationStage,
    TagPreservationInput,
    TagPreservationOutput,
    ChunkingStage,
    ChunkingInput,
    ChunkingOutput
)
from src.core.epub.events import EventBus, EventType


class MockTagPreserver:
    """Mock tag preserver for testing."""

    def preserve_tags(self, text: str):
        """Mock preserve_tags."""
        # Simple mock: replace < with [[, > with ]]
        tag_map = {
            "[[0]]": "<p>",
            "[[1]]": "</p>"
        }
        return "[[0]]Hello World[[1]]", tag_map

    def restore_tags(self, text: str, tag_map: dict):
        """Mock restore_tags."""
        result = text
        for placeholder, tag in tag_map.items():
            result = result.replace(placeholder, tag)
        return result


class MockChunker:
    """Mock chunker for testing."""

    def chunk_html_with_placeholders(self, text: str, tag_map: dict):
        """Mock chunking - returns single chunk."""
        return [{
            'text': text,
            'local_tag_map': tag_map,
            'global_offset': 0,
            'global_indices': [0, 1]
        }]


class TestPipelineStage:
    """Test PipelineStage base class."""

    @pytest.mark.asyncio
    async def test_stage_emit_event(self):
        """Stage should emit events when event bus provided."""
        event_bus = EventBus()
        event_bus.enable_history()

        # Create a simple test stage
        class TestStage(PipelineStage):
            async def process(self, input_data):
                self.emit_event(EventType.PERFORMANCE_METRIC, {"test": "data"})
                return input_data + "_processed"

        stage = TestStage(event_bus=event_bus)
        result = await stage.process("input")

        assert result == "input_processed"

        events = event_bus.get_events_by_type(EventType.PERFORMANCE_METRIC)
        assert len(events) == 1
        assert events[0].data["test"] == "data"

    @pytest.mark.asyncio
    async def test_stage_without_event_bus(self):
        """Stage should work without event bus."""
        class TestStage(PipelineStage):
            async def process(self, input_data):
                self.emit_event(EventType.PERFORMANCE_METRIC, {"test": "data"})
                return input_data + "_processed"

        stage = TestStage(event_bus=None)
        result = await stage.process("input")

        assert result == "input_processed"  # Should not crash


class TestTagPreservationStage:
    """Test TagPreservationStage."""

    @pytest.mark.asyncio
    async def test_tag_preservation_stage(self):
        """Process HTML and preserve tags."""
        tag_preserver = MockTagPreserver()
        stage = TagPreservationStage(tag_preserver)

        input_data = TagPreservationInput(html="<p>Hello World</p>")
        output = await stage.process(input_data)

        assert isinstance(output, TagPreservationOutput)
        assert "[[0]]" in output.text_with_placeholders
        assert "[[1]]" in output.text_with_placeholders
        assert len(output.tag_map) == 2

    @pytest.mark.asyncio
    async def test_tag_preservation_emits_event(self):
        """Stage should emit performance metrics."""
        event_bus = EventBus()
        event_bus.enable_history()

        tag_preserver = MockTagPreserver()
        stage = TagPreservationStage(tag_preserver, event_bus=event_bus)

        input_data = TagPreservationInput(html="<p>Hello World</p>")
        await stage.process(input_data)

        events = event_bus.get_events_by_type(EventType.PERFORMANCE_METRIC)
        assert len(events) == 1
        assert events[0].data["stage"] == "tag_preservation"
        assert "placeholder_count" in events[0].data


class TestChunkingStage:
    """Test ChunkingStage."""

    @pytest.mark.asyncio
    async def test_chunking_stage(self):
        """Process text and create chunks."""
        chunker = MockChunker()
        stage = ChunkingStage(chunker)

        input_data = ChunkingInput(
            text="[[0]]Hello World[[1]]",
            tag_map={"[[0]]": "<p>", "[[1]]": "</p>"},
            max_tokens=400
        )
        output = await stage.process(input_data)

        assert isinstance(output, ChunkingOutput)
        assert len(output.chunks) == 1
        assert output.chunks[0]['text'] == "[[0]]Hello World[[1]]"

    @pytest.mark.asyncio
    async def test_chunking_emits_event(self):
        """Stage should emit performance metrics."""
        event_bus = EventBus()
        event_bus.enable_history()

        chunker = MockChunker()
        stage = ChunkingStage(chunker, event_bus=event_bus)

        input_data = ChunkingInput(
            text="[[0]]Hello World[[1]]",
            tag_map={"[[0]]": "<p>", "[[1]]": "</p>"},
            max_tokens=400
        )
        await stage.process(input_data)

        events = event_bus.get_events_by_type(EventType.PERFORMANCE_METRIC)
        assert len(events) == 1
        assert events[0].data["stage"] == "chunking"
        assert events[0].data["chunk_count"] == 1


class TestTranslationPipeline:
    """Test TranslationPipeline orchestrator."""

    @pytest.mark.asyncio
    async def test_pipeline_single_stage(self):
        """Pipeline with single stage."""
        class UppercaseStage(PipelineStage):
            async def process(self, input_data):
                return input_data.upper()

        pipeline = TranslationPipeline()
        pipeline.add_stage(UppercaseStage())

        result = await pipeline.execute("hello")
        assert result == "HELLO"

    @pytest.mark.asyncio
    async def test_pipeline_multiple_stages(self):
        """Pipeline with multiple stages."""
        class UppercaseStage(PipelineStage):
            async def process(self, input_data):
                return input_data.upper()

        class ReverseStage(PipelineStage):
            async def process(self, input_data):
                return input_data[::-1]

        class PrefixStage(PipelineStage):
            async def process(self, input_data):
                return f"PREFIX_{input_data}"

        pipeline = (TranslationPipeline()
                    .add_stage(UppercaseStage())
                    .add_stage(ReverseStage())
                    .add_stage(PrefixStage()))

        result = await pipeline.execute("hello")
        # hello -> HELLO -> OLLEH -> PREFIX_OLLEH
        assert result == "PREFIX_OLLEH"

    @pytest.mark.asyncio
    async def test_pipeline_with_event_bus(self):
        """Pipeline should emit events for stage execution."""
        event_bus = EventBus()
        event_bus.enable_history()

        class TestStage(PipelineStage):
            async def process(self, input_data):
                return input_data

        pipeline = TranslationPipeline(event_bus=event_bus)
        pipeline.add_stage(TestStage())
        pipeline.add_stage(TestStage())

        await pipeline.execute("test")

        events = event_bus.get_events_by_type(EventType.PERFORMANCE_METRIC)
        # Should have starting and completed events for each stage
        assert len(events) >= 4  # 2 stages × 2 events (start + complete)

        # Check for stage lifecycle events
        starting_events = [e for e in events if e.data.get("status") == "starting"]
        completed_events = [e for e in events if e.data.get("status") == "completed"]

        assert len(starting_events) == 2
        assert len(completed_events) == 2

    @pytest.mark.asyncio
    async def test_pipeline_fluent_interface(self):
        """Pipeline should support fluent chaining."""
        class DoubleStage(PipelineStage):
            async def process(self, input_data):
                return input_data * 2

        pipeline = TranslationPipeline()

        # add_stage should return self
        returned = pipeline.add_stage(DoubleStage())
        assert returned is pipeline

        # Should support chaining
        result = await (pipeline
                        .add_stage(DoubleStage())
                        .add_stage(DoubleStage())
                        .execute(2))

        # 2 -> 4 -> 8 -> 16
        assert result == 16

    @pytest.mark.asyncio
    async def test_full_pipeline_integration(self):
        """Test full pipeline with tag preservation and chunking."""
        event_bus = EventBus()
        event_bus.enable_history()

        tag_preserver = MockTagPreserver()
        chunker = MockChunker()

        pipeline = (TranslationPipeline(event_bus=event_bus)
                    .add_stage(TagPreservationStage(tag_preserver, event_bus))
                    .add_stage(ChunkingStage(chunker, event_bus)))

        initial_input = TagPreservationInput(html="<p>Hello World</p>")

        # Execute pipeline
        result = await pipeline.execute(initial_input)

        # Result should be ChunkingOutput
        assert isinstance(result, ChunkingOutput)
        assert len(result.chunks) == 1

        # Check events were emitted
        perf_events = event_bus.get_events_by_type(EventType.PERFORMANCE_METRIC)
        assert len(perf_events) > 0

        # Should have events from both stages
        stage_names = {e.data.get("stage") for e in perf_events}
        assert "tag_preservation" in stage_names
        assert "chunking" in stage_names
