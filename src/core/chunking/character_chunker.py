"""
Character-based text chunking algorithm.

Splits text into chunks of consistent size while respecting semantic boundaries.
"""

import sys
from pathlib import Path
from typing import List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from .models import (
    TextChunk,
    ChunkingConfiguration,
    BoundaryType,
    ChunkStatus,
)
from .boundary_detector import (
    find_sentence_boundary,
    detect_paragraph_boundaries,
    is_header_line,
)

# Logger configuration - use simple print for now to avoid issues
# The unified logger can be integrated when used in the actual translation pipeline
HAS_LOGGER = False
logger = None


def _log(level: str, message: str) -> None:
    """Log a message (silent for DEBUG to avoid noise)."""
    # Only print warnings and errors to avoid noise during normal operation
    if level in ("WARNING", "ERROR"):
        print(f"[CHUNKING {level}] {message}")


def chunk_text_by_characters(
    text: str,
    config: Optional[ChunkingConfiguration] = None,
    chapter_id: str = "default",
    chapter_index: int = 0
) -> List[TextChunk]:
    """
    Split text into chunks of approximately equal character size while respecting semantic boundaries.

    Args:
        text: Source text to be chunked (extracted from EPUB chapter)
        config: Chunking configuration with target size and tolerances
        chapter_id: Identifier for the source chapter
        chapter_index: Position in reading order

    Returns:
        Ordered list of TextChunk objects

    Behavior:
        1. Parse text into paragraphs (split on double newlines)
        2. Identify headers (lines starting with # or detected as headers)
        3. Accumulate paragraphs until target size range reached
        4. Find nearest sentence boundary for clean break
        5. Create chunk with metadata (size, boundary type, header presence)
        6. Continue until all text processed
        7. Final chunk may be undersized (acceptable)

    Guarantees:
        - No mid-sentence breaks unless forced by extreme size
        - Headers grouped with following content
        - All text accounted for (no loss)
        - Chunk order preserved
    """
    if config is None:
        config = ChunkingConfiguration()

    if not text or not text.strip():
        return []

    # Split text into paragraphs
    paragraphs = _split_into_paragraphs(text)

    if not paragraphs:
        return []

    chunks = []
    current_chunk_text = ""
    current_chunk_size = 0
    chunk_index = 0
    has_header = False
    pending_header = False

    for i, paragraph in enumerate(paragraphs):
        para_text = paragraph.strip()
        if not para_text:
            continue

        # Check if this is a header
        if is_header_line(para_text):
            pending_header = True

        para_size = len(para_text)

        # Check if adding this paragraph would exceed max tolerance
        if current_chunk_size + para_size + 2 > config.max_size and current_chunk_size > 0:
            # Current chunk is full enough, finalize it
            if current_chunk_size >= config.min_size:
                # Create chunk at current size
                chunk = _create_chunk(
                    current_chunk_text.strip(),
                    chunk_index,
                    chapter_id,
                    chapter_index,
                    has_header,
                    config
                )
                chunks.append(chunk)

                _log_chunk_created(chunk, config)

                chunk_index += 1
                current_chunk_text = ""
                current_chunk_size = 0
                has_header = False
            else:
                # Need to split the current chunk to find a better boundary
                # This happens when we have accumulated text but it's still under min_size
                # and adding the next paragraph would exceed max_size
                pass

        # Handle case where single paragraph is very long
        if para_size > config.max_size:
            # First, finalize any existing chunk
            if current_chunk_text.strip():
                chunk = _create_chunk(
                    current_chunk_text.strip(),
                    chunk_index,
                    chapter_id,
                    chapter_index,
                    has_header,
                    config
                )
                chunks.append(chunk)
                _log_chunk_created(chunk, config)
                chunk_index += 1
                current_chunk_text = ""
                current_chunk_size = 0
                has_header = False

            # Split long paragraph by sentences
            para_chunks = _split_long_paragraph(
                para_text, config, chapter_id, chapter_index, chunk_index, pending_header
            )
            chunks.extend(para_chunks)
            chunk_index += len(para_chunks)
            pending_header = False
            continue

        # Add paragraph to current chunk
        if current_chunk_text:
            current_chunk_text += "\n\n" + para_text
            current_chunk_size += 2 + para_size  # +2 for newlines
        else:
            current_chunk_text = para_text
            current_chunk_size = para_size

        if pending_header:
            has_header = True
            pending_header = False

        # Check if we've reached the target range
        if config.min_size <= current_chunk_size <= config.max_size:
            # Good size, but let's see if we should continue accumulating
            # or if the next paragraph would push us over
            if i + 1 < len(paragraphs):
                next_para = paragraphs[i + 1].strip()
                if next_para and current_chunk_size + len(next_para) + 2 > config.max_size:
                    # Next paragraph would exceed max, finalize now
                    chunk = _create_chunk(
                        current_chunk_text.strip(),
                        chunk_index,
                        chapter_id,
                        chapter_index,
                        has_header,
                        config
                    )
                    chunks.append(chunk)
                    _log_chunk_created(chunk, config)
                    chunk_index += 1
                    current_chunk_text = ""
                    current_chunk_size = 0
                    has_header = False

    # Finalize any remaining text
    if current_chunk_text.strip():
        chunk = _create_chunk(
            current_chunk_text.strip(),
            chunk_index,
            chapter_id,
            chapter_index,
            has_header,
            config
        )
        chunks.append(chunk)
        _log_chunk_created(chunk, config)

    # Add context (previous/next chunk content)
    _add_context_to_chunks(chunks)

    return chunks


def _split_into_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs."""
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Split on double newlines (paragraph separator)
    paragraphs = text.split('\n\n')

    # Filter empty paragraphs but preserve structure
    return [p for p in paragraphs if p.strip()]


def _split_long_paragraph(
    text: str,
    config: ChunkingConfiguration,
    chapter_id: str,
    chapter_index: int,
    start_chunk_index: int,
    has_header: bool
) -> List[TextChunk]:
    """
    Split a very long paragraph into multiple chunks at sentence boundaries.

    Args:
        text: Long paragraph text
        config: Chunking configuration
        chapter_id: Chapter identifier
        chapter_index: Chapter position
        start_chunk_index: Starting index for chunks
        has_header: Whether this paragraph started with a header

    Returns:
        List of TextChunk objects
    """
    chunks = []
    chunk_index = start_chunk_index
    remaining_text = text
    first_chunk = True

    while remaining_text:
        if len(remaining_text) <= config.max_size:
            # Remaining text fits in one chunk
            chunk = _create_chunk(
                remaining_text,
                chunk_index,
                chapter_id,
                chapter_index,
                has_header and first_chunk,
                config
            )
            chunks.append(chunk)
            _log_chunk_created(chunk, config)
            break

        # Find sentence boundary near target size
        target_pos = config.target_size
        pos, term, confidence = find_sentence_boundary(
            remaining_text,
            target_pos,
            "backward",
            int(config.target_size * 0.3),  # Search within 30% of target
            config.sentence_terminators
        )

        if pos == target_pos and confidence < 1.0:
            # No good boundary found, search forward instead
            pos, term, confidence = find_sentence_boundary(
                remaining_text,
                target_pos,
                "forward",
                int(config.target_size * 0.3),
                config.sentence_terminators
            )

        if pos <= 0 or pos >= len(remaining_text):
            # Still no boundary, force split at target size (worst case)
            pos = min(config.target_size, len(remaining_text))
            _log("WARNING", f"Forced split at position {pos} - no sentence boundary found")

        chunk_text = remaining_text[:pos].strip()
        if chunk_text:
            chunk = TextChunk(
                content=chunk_text,
                character_count=len(chunk_text),
                chunk_index=chunk_index,
                chapter_id=chapter_id,
                chapter_index=chapter_index,
                boundary_type=BoundaryType.SENTENCE_END if term else BoundaryType.FORCED_SIZE,
                has_header=has_header and first_chunk,
                status=ChunkStatus.CREATED
            )
            chunks.append(chunk)
            _log_chunk_created(chunk, config)
            chunk_index += 1

        remaining_text = remaining_text[pos:].strip()
        first_chunk = False

    return chunks


def _create_chunk(
    text: str,
    chunk_index: int,
    chapter_id: str,
    chapter_index: int,
    has_header: bool,
    config: ChunkingConfiguration
) -> TextChunk:
    """Create a TextChunk with appropriate boundary type."""
    # Determine boundary type
    text_stripped = text.rstrip()
    if text_stripped.endswith('\n\n'):
        boundary_type = BoundaryType.PARAGRAPH_END
    elif text_stripped and text_stripped[-1] in '.!?':
        boundary_type = BoundaryType.SENTENCE_END
    elif '"' in text_stripped[-3:] or "'" in text_stripped[-3:]:
        boundary_type = BoundaryType.SENTENCE_END
    else:
        boundary_type = BoundaryType.PARAGRAPH_END

    return TextChunk(
        content=text,
        character_count=len(text),
        chunk_index=chunk_index,
        chapter_id=chapter_id,
        chapter_index=chapter_index,
        boundary_type=boundary_type,
        has_header=has_header,
        status=ChunkStatus.CREATED
    )


def _add_context_to_chunks(chunks: List[TextChunk]) -> None:
    """Add previous/next chunk content as context for translation."""
    for i, chunk in enumerate(chunks):
        if i > 0:
            # Add last 200 characters of previous chunk as context
            prev_content = chunks[i - 1].content
            chunk.context_before = prev_content[-200:] if len(prev_content) > 200 else prev_content

        if i < len(chunks) - 1:
            # Add first 200 characters of next chunk as context
            next_content = chunks[i + 1].content
            chunk.context_after = next_content[:200] if len(next_content) > 200 else next_content


def _log_chunk_created(chunk: TextChunk, config: ChunkingConfiguration) -> None:
    """Log chunk creation with size information."""
    size = chunk.character_count
    status_msg = "OK"

    if chunk.is_warning_size(config):
        _log("WARNING", f"Chunk {chunk.chunk_index} size {size} exceeds warning threshold {config.warning_size}")
        status_msg = "WARNING"
    elif chunk.is_oversized(config):
        _log("WARNING", f"Chunk {chunk.chunk_index} size {size} exceeds max tolerance {config.max_size}")
        status_msg = "OVERSIZED"
    elif size < config.min_size:
        status_msg = "SMALL"

    _log(
        "DEBUG",
        f"Created chunk {chunk.chunk_index} ({chunk.chapter_id}): {size} chars, "
        f"boundary={chunk.boundary_type.value}, header={chunk.has_header}, status={status_msg}"
    )
