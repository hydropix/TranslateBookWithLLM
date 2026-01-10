"""
Translation pipeline using composable stages.

Provides a flexible, testable pipeline architecture for EPUB translation.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional
from dataclasses import dataclass

from .events import EventBus, Event, EventType
from .interfaces import ITagPreserver, IChunker, IValidator

# Type variables for pipeline stages
T = TypeVar('T')  # Input type
R = TypeVar('R')  # Output type


class PipelineStage(ABC, Generic[T, R]):
    """Abstract base class for pipeline stages.

    Each stage transforms input of type T to output of type R.
    """

    def __init__(self, event_bus: Optional[EventBus] = None):
        """Initialize stage.

        Args:
            event_bus: Optional event bus for observability
        """
        self.event_bus = event_bus

    @abstractmethod
    async def process(self, input_data: T) -> R:
        """Process input data and return result.

        Args:
            input_data: Input to transform

        Returns:
            Transformed output
        """
        pass

    def emit_event(self, event_type: EventType, data: dict) -> None:
        """Emit an event if event bus is available.

        Args:
            event_type: Type of event
            data: Event data
        """
        if self.event_bus:
            self.event_bus.publish(Event(
                type=event_type,
                data=data,
                source=self.__class__.__name__
            ))


# === Concrete Pipeline Stages ===

@dataclass
class TagPreservationInput:
    """Input for tag preservation stage."""
    html: str


@dataclass
class TagPreservationOutput:
    """Output from tag preservation stage."""
    text_with_placeholders: str
    tag_map: dict


class TagPreservationStage(PipelineStage[TagPreservationInput, TagPreservationOutput]):
    """Stage for preserving HTML tags as placeholders."""

    def __init__(self, tag_preserver: ITagPreserver, event_bus: Optional[EventBus] = None):
        """Initialize stage.

        Args:
            tag_preserver: Tag preservation implementation
            event_bus: Optional event bus
        """
        super().__init__(event_bus)
        self.tag_preserver = tag_preserver

    async def process(self, input_data: TagPreservationInput) -> TagPreservationOutput:
        """Preserve tags in HTML.

        Args:
            input_data: HTML content

        Returns:
            Text with placeholders and tag map
        """
        text, tag_map = self.tag_preserver.preserve_tags(input_data.html)

        self.emit_event(EventType.PERFORMANCE_METRIC, {
            "stage": "tag_preservation",
            "placeholder_count": len(tag_map)
        })

        return TagPreservationOutput(
            text_with_placeholders=text,
            tag_map=tag_map
        )


@dataclass
class ChunkingInput:
    """Input for chunking stage."""
    text: str
    tag_map: dict
    max_tokens: int


@dataclass
class ChunkingOutput:
    """Output from chunking stage."""
    chunks: List[dict]


class ChunkingStage(PipelineStage[ChunkingInput, ChunkingOutput]):
    """Stage for chunking text into translatable segments."""

    def __init__(self, chunker: IChunker, event_bus: Optional[EventBus] = None):
        """Initialize stage.

        Args:
            chunker: Chunking implementation
            event_bus: Optional event bus
        """
        super().__init__(event_bus)
        self.chunker = chunker

    async def process(self, input_data: ChunkingInput) -> ChunkingOutput:
        """Chunk text.

        Args:
            input_data: Text and configuration

        Returns:
            List of chunks
        """
        chunks = self.chunker.chunk_html_with_placeholders(
            input_data.text,
            input_data.tag_map
        )

        self.emit_event(EventType.PERFORMANCE_METRIC, {
            "stage": "chunking",
            "chunk_count": len(chunks)
        })

        return ChunkingOutput(chunks=chunks)


# === Pipeline Orchestrator ===

class TranslationPipeline:
    """Composable translation pipeline."""

    def __init__(self, event_bus: Optional[EventBus] = None):
        """Initialize pipeline.

        Args:
            event_bus: Optional event bus for all stages
        """
        self.event_bus = event_bus
        self.stages: List[PipelineStage] = []

    def add_stage(self, stage: PipelineStage) -> 'TranslationPipeline':
        """Add a stage to the pipeline.

        Args:
            stage: Pipeline stage to add

        Returns:
            Self for fluent chaining
        """
        self.stages.append(stage)
        return self

    async def execute(self, input_data):
        """Execute all pipeline stages sequentially.

        Args:
            input_data: Initial input

        Returns:
            Final output from last stage
        """
        result = input_data

        for i, stage in enumerate(self.stages):
            stage_name = stage.__class__.__name__

            if self.event_bus:
                self.event_bus.publish(Event(
                    type=EventType.PERFORMANCE_METRIC,
                    data={
                        "pipeline_stage": i,
                        "stage_name": stage_name,
                        "status": "starting"
                    }
                ))

            result = await stage.process(result)

            if self.event_bus:
                self.event_bus.publish(Event(
                    type=EventType.PERFORMANCE_METRIC,
                    data={
                        "pipeline_stage": i,
                        "stage_name": stage_name,
                        "status": "completed"
                    }
                ))

        return result
