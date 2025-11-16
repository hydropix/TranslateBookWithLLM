"""
Unit tests for character-based text chunking.

Tests for User Story 1 (US1) - Consistent Chunk Sizes for Translation.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.chunking.character_chunker import (
    chunk_text_by_characters,
    _split_into_paragraphs,
    _split_long_paragraph,
)
from core.chunking.models import (
    ChunkingConfiguration,
    TextChunk,
    BoundaryType,
    ChunkStatus,
)


class TestChunkTextByCharacters:
    """Test main chunking function."""

    def test_empty_text_returns_empty_list(self):
        """Should return empty list for empty text."""
        config = ChunkingConfiguration(target_size=2500)
        chunks = chunk_text_by_characters("", config)
        assert chunks == []

    def test_whitespace_only_returns_empty_list(self):
        """Should return empty list for whitespace-only text."""
        config = ChunkingConfiguration(target_size=2500)
        chunks = chunk_text_by_characters("   \n\n   ", config)
        assert chunks == []

    def test_single_short_paragraph(self):
        """Should create single chunk for short text."""
        text = "This is a short paragraph."
        config = ChunkingConfiguration(target_size=2500)
        chunks = chunk_text_by_characters(text, config)
        assert len(chunks) == 1
        assert chunks[0].content == text
        assert chunks[0].chunk_index == 0

    def test_multiple_paragraphs_combined(self):
        """Should combine short paragraphs into chunks."""
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        config = ChunkingConfiguration(target_size=2500)
        chunks = chunk_text_by_characters(text, config)
        assert len(chunks) == 1
        assert "First" in chunks[0].content
        assert "Second" in chunks[0].content
        assert "Third" in chunks[0].content

    def test_respects_max_size_tolerance(self):
        """Should not exceed max size tolerance."""
        # Create text that would exceed max size if combined
        para = "X" * 1000 + "."
        text = f"{para}\n\n{para}\n\n{para}"
        config = ChunkingConfiguration(target_size=2500, min_tolerance=0.8, max_tolerance=1.2)
        chunks = chunk_text_by_characters(text, config)

        for chunk in chunks:
            # Max size is 2500 * 1.2 = 3000
            # Each chunk should respect this (except possibly the last one)
            if chunk.chunk_index < len(chunks) - 1:
                assert chunk.character_count <= config.max_size

    def test_creates_chunks_in_target_range(self):
        """Should create chunks within target size range."""
        # Create multiple paragraphs of moderate size
        para = "This is a test paragraph with some content. " * 20  # ~900 chars
        text = "\n\n".join([para] * 10)
        config = ChunkingConfiguration(target_size=2500, min_tolerance=0.8, max_tolerance=1.2)
        chunks = chunk_text_by_characters(text, config)

        # Check that most chunks (except possibly the last) are in range
        in_range_count = 0
        for i, chunk in enumerate(chunks[:-1]):  # Exclude last chunk
            if config.min_size <= chunk.character_count <= config.max_size:
                in_range_count += 1

        if len(chunks) > 1:
            # At least 80% should be in range
            assert in_range_count / (len(chunks) - 1) >= 0.8

    def test_preserves_chunk_order(self):
        """Should preserve chunk order with sequential indices."""
        # Use longer paragraphs to create multiple chunks with valid target_size
        para = "This is paragraph content that should be long enough. " * 20
        text = f"{para}\n\n{para}\n\n{para}\n\n{para}"
        config = ChunkingConfiguration(target_size=500, min_tolerance=0.8, max_tolerance=1.2)
        chunks = chunk_text_by_characters(text, config)

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_chapter_id_preserved(self):
        """Should preserve chapter_id in all chunks."""
        text = "Some text content.\n\nMore content here."
        config = ChunkingConfiguration(target_size=2500)
        chunks = chunk_text_by_characters(text, config, chapter_id="chapter_1", chapter_index=0)

        for chunk in chunks:
            assert chunk.chapter_id == "chapter_1"
            assert chunk.chapter_index == 0

    def test_chunk_status_is_created(self):
        """Should set chunk status to CREATED."""
        text = "A simple paragraph."
        config = ChunkingConfiguration(target_size=2500)
        chunks = chunk_text_by_characters(text, config)

        for chunk in chunks:
            assert chunk.status == ChunkStatus.CREATED

    def test_boundary_type_assigned(self):
        """Should assign appropriate boundary types."""
        text = "First sentence. Second sentence."
        config = ChunkingConfiguration(target_size=2500)
        chunks = chunk_text_by_characters(text, config)

        assert chunks[0].boundary_type in [BoundaryType.SENTENCE_END, BoundaryType.PARAGRAPH_END]

    def test_header_detection_marks_chunk(self):
        """Should mark chunks containing headers."""
        text = "# Chapter Title\n\nThis is the content of the chapter."
        config = ChunkingConfiguration(target_size=2500)
        chunks = chunk_text_by_characters(text, config)

        # First chunk should have has_header=True
        assert chunks[0].has_header is True

    def test_context_before_added(self):
        """Should add context from previous chunk."""
        # Create text that will split into multiple chunks
        para = "A" * 1500 + "."
        text = f"{para}\n\n{para}\n\n{para}"
        config = ChunkingConfiguration(target_size=2500, min_tolerance=0.8, max_tolerance=1.2)
        chunks = chunk_text_by_characters(text, config)

        if len(chunks) > 1:
            # Second chunk should have context from first
            assert chunks[1].context_before != ""
            # Context should be from previous chunk
            assert chunks[1].context_before in chunks[0].content or chunks[0].content.endswith(chunks[1].context_before)

    def test_context_after_added(self):
        """Should add context from next chunk."""
        # Create text that will split into multiple chunks
        para = "B" * 1500 + "."
        text = f"{para}\n\n{para}\n\n{para}"
        config = ChunkingConfiguration(target_size=2500, min_tolerance=0.8, max_tolerance=1.2)
        chunks = chunk_text_by_characters(text, config)

        if len(chunks) > 1:
            # First chunk should have context after
            assert chunks[0].context_after != ""
            # Context should be from next chunk
            assert chunks[0].context_after in chunks[1].content or chunks[1].content.startswith(chunks[0].context_after)

    def test_default_config_used_when_none_provided(self):
        """Should use default config when none provided."""
        text = "Some text."
        chunks = chunk_text_by_characters(text)  # No config passed
        assert len(chunks) == 1
        assert chunks[0].content == text

    def test_no_text_loss(self):
        """Should not lose any text during chunking."""
        # Use a paragraph that's long enough for valid config
        para = "This is a paragraph with content that should be preserved. " * 10
        original = f"First {para}\n\nSecond {para}\n\nThird {para}"
        config = ChunkingConfiguration(target_size=500, min_tolerance=0.8, max_tolerance=1.2)
        chunks = chunk_text_by_characters(original, config)

        # Combine all chunk content
        combined = "\n\n".join([c.content for c in chunks])

        # All original key words should be present
        for word in ["First", "Second", "Third", "paragraph", "content", "preserved"]:
            assert word in combined

    def test_very_long_single_paragraph_split(self):
        """Should split very long paragraphs at sentence boundaries."""
        # Create a very long paragraph with multiple sentences
        long_para = " ".join(["This is sentence number {}.".format(i) for i in range(100)])
        config = ChunkingConfiguration(target_size=500, min_tolerance=0.8, max_tolerance=1.2)
        chunks = chunk_text_by_characters(long_para, config)

        # Should create multiple chunks
        assert len(chunks) > 1

        # Each chunk should end at sentence boundary (except possibly forced splits)
        for chunk in chunks:
            content = chunk.content.rstrip()
            if content:
                # Should end with period, or be forced split
                assert content[-1] in '.!?' or chunk.boundary_type == BoundaryType.FORCED_SIZE


class TestSplitIntoParagraphs:
    """Test paragraph splitting helper."""

    def test_splits_on_double_newlines(self):
        """Should split on double newlines."""
        text = "Para one.\n\nPara two.\n\nPara three."
        paras = _split_into_paragraphs(text)
        assert len(paras) == 3
        assert paras[0].strip() == "Para one."
        assert paras[1].strip() == "Para two."
        assert paras[2].strip() == "Para three."

    def test_handles_carriage_returns(self):
        """Should normalize Windows line endings."""
        text = "Para one.\r\n\r\nPara two."
        paras = _split_into_paragraphs(text)
        assert len(paras) == 2

    def test_filters_empty_paragraphs(self):
        """Should filter out empty paragraphs."""
        text = "Para one.\n\n\n\nPara two."
        paras = _split_into_paragraphs(text)
        assert len(paras) == 2

    def test_single_paragraph(self):
        """Should handle single paragraph."""
        text = "Just one paragraph."
        paras = _split_into_paragraphs(text)
        assert len(paras) == 1
        assert paras[0].strip() == "Just one paragraph."


class TestSplitLongParagraph:
    """Test splitting very long paragraphs."""

    def test_splits_at_sentence_boundaries(self):
        """Should split long paragraphs at sentence boundaries."""
        # Create a long text with many sentences that exceeds the config max size
        long_text = " ".join(["This is sentence number {}.".format(i) for i in range(50)])
        config = ChunkingConfiguration(target_size=500, min_tolerance=0.8, max_tolerance=1.2)
        chunks = _split_long_paragraph(long_text, config, "ch1", 0, 0, False)

        assert len(chunks) > 1
        # Check each chunk ends properly
        for chunk in chunks:
            content = chunk.content.rstrip()
            if content:
                # Should end with sentence terminator
                assert content[-1] in '.!?' or chunk.boundary_type == BoundaryType.FORCED_SIZE

    def test_preserves_header_flag_on_first_chunk(self):
        """Should set has_header only on first chunk."""
        # Create a long text that will split into multiple chunks
        long_text = " ".join(["This is sentence number {}.".format(i) for i in range(50)])
        config = ChunkingConfiguration(target_size=500, min_tolerance=0.8, max_tolerance=1.2)
        chunks = _split_long_paragraph(long_text, config, "ch1", 0, 0, has_header=True)

        if len(chunks) > 1:
            assert chunks[0].has_header is True
            assert chunks[1].has_header is False

    def test_handles_text_that_fits_in_one_chunk(self):
        """Should handle text that fits in single chunk."""
        text = "Short text."
        config = ChunkingConfiguration(target_size=500)
        chunks = _split_long_paragraph(text, config, "ch1", 0, 0, False)

        assert len(chunks) == 1
        assert chunks[0].content == text


class TestChunkProperties:
    """Test TextChunk computed properties."""

    def test_is_within_tolerance_true(self):
        """Should identify chunks within tolerance."""
        config = ChunkingConfiguration(target_size=2500)  # min=2000, max=3000
        chunk = TextChunk(
            content="x" * 2500,
            character_count=2500,
            chunk_index=0,
            chapter_id="ch1",
            chapter_index=0,
            boundary_type=BoundaryType.SENTENCE_END
        )
        assert chunk.is_within_tolerance(config) is True

    def test_is_within_tolerance_at_min(self):
        """Should accept chunk at minimum tolerance."""
        config = ChunkingConfiguration(target_size=2500)  # min=2000
        chunk = TextChunk(
            content="x" * 2000,
            character_count=2000,
            chunk_index=0,
            chapter_id="ch1",
            chapter_index=0,
            boundary_type=BoundaryType.SENTENCE_END
        )
        assert chunk.is_within_tolerance(config) is True

    def test_is_within_tolerance_at_max(self):
        """Should accept chunk at maximum tolerance."""
        config = ChunkingConfiguration(target_size=2500)  # max=3000
        chunk = TextChunk(
            content="x" * 3000,
            character_count=3000,
            chunk_index=0,
            chapter_id="ch1",
            chapter_index=0,
            boundary_type=BoundaryType.SENTENCE_END
        )
        assert chunk.is_within_tolerance(config) is True

    def test_is_oversized_true(self):
        """Should identify oversized chunks."""
        config = ChunkingConfiguration(target_size=2500)  # max=3000
        chunk = TextChunk(
            content="x" * 3500,
            character_count=3500,
            chunk_index=0,
            chapter_id="ch1",
            chapter_index=0,
            boundary_type=BoundaryType.SENTENCE_END
        )
        assert chunk.is_oversized(config) is True

    def test_is_warning_size_true(self):
        """Should identify chunks exceeding warning threshold."""
        config = ChunkingConfiguration(target_size=2500, warning_threshold=1.5)  # warning=3750
        chunk = TextChunk(
            content="x" * 4000,
            character_count=4000,
            chunk_index=0,
            chapter_id="ch1",
            chapter_index=0,
            boundary_type=BoundaryType.SENTENCE_END
        )
        assert chunk.is_warning_size(config) is True

    def test_character_count_auto_corrected(self):
        """Should auto-correct character count in __post_init__."""
        chunk = TextChunk(
            content="12345",
            character_count=10,  # Wrong count
            chunk_index=0,
            chapter_id="ch1",
            chapter_index=0,
            boundary_type=BoundaryType.SENTENCE_END
        )
        # Should be corrected to 5
        assert chunk.character_count == 5


# =============================================================================
# Phase 5: User Story 3 - Semantic Boundary Preservation Tests
# =============================================================================

class TestHeaderGroupingLogic:
    """Test header grouping logic (T036) - headers stay with following content."""

    def test_header_grouped_with_content(self):
        """Header should be grouped with following content paragraph."""
        text = "# Chapter One\n\nThis is the first paragraph of the chapter."
        config = ChunkingConfiguration(target_size=2500)
        chunks = chunk_text_by_characters(text, config)

        assert len(chunks) == 1
        assert "Chapter One" in chunks[0].content
        assert "first paragraph" in chunks[0].content
        assert chunks[0].has_header is True

    def test_multiple_headers_grouped_correctly(self):
        """Multiple headers should each be grouped with their content."""
        text = (
            "# First Section\n\n"
            "Content for first section.\n\n"
            "## Subsection A\n\n"
            "Content for subsection A."
        )
        config = ChunkingConfiguration(target_size=2500)
        chunks = chunk_text_by_characters(text, config)

        # Should combine all into one chunk (short text)
        assert len(chunks) == 1
        assert chunks[0].has_header is True
        assert "First Section" in chunks[0].content
        assert "Subsection A" in chunks[0].content

    def test_header_never_isolated(self):
        """Header should never appear as the only content in a chunk."""
        text = "# Lonely Header\n\nSome content follows."
        config = ChunkingConfiguration(target_size=2500)
        chunks = chunk_text_by_characters(text, config)

        # Should have content with the header
        assert chunks[0].has_header is True
        assert "Some content" in chunks[0].content

    def test_all_caps_header_grouped(self):
        """All caps headers should be grouped with content."""
        text = "CHAPTER ONE\n\nThe story begins here."
        config = ChunkingConfiguration(target_size=2500)
        chunks = chunk_text_by_characters(text, config)

        assert chunks[0].has_header is True
        assert "CHAPTER ONE" in chunks[0].content
        assert "story begins" in chunks[0].content

    def test_header_with_long_following_content(self):
        """Header should be included even if following content is long."""
        long_para = "This is a very long paragraph. " * 100  # ~3000 chars
        text = f"# Important Section\n\n{long_para}"
        config = ChunkingConfiguration(target_size=2500, min_tolerance=0.8, max_tolerance=1.2)
        chunks = chunk_text_by_characters(text, config)

        # First chunk should have the header
        assert chunks[0].has_header is True
        assert "Important Section" in chunks[0].content


class TestQuotedTextPreservation:
    """Test quoted text preservation (T037) - keep quotes together when possible."""

    def test_short_quote_preserved(self):
        """Short quoted text should be kept together."""
        text = 'He said "Hello, how are you?" She replied "I am fine."'
        config = ChunkingConfiguration(target_size=2500)
        chunks = chunk_text_by_characters(text, config)

        assert len(chunks) == 1
        assert '"Hello, how are you?"' in chunks[0].content
        assert '"I am fine."' in chunks[0].content

    def test_quoted_sentence_not_broken(self):
        """Sentence ending inside quotes should be recognized."""
        text = 'He exclaimed "Stop right there!" Then he ran away.'
        config = ChunkingConfiguration(target_size=2500)
        chunks = chunk_text_by_characters(text, config)

        # Should keep the quoted exclamation together
        assert '"Stop right there!"' in chunks[0].content

    def test_nested_quotes_handled(self):
        """Nested quotes should be handled gracefully."""
        text = 'She said "He told me \'Go away\' yesterday." It was rude.'
        config = ChunkingConfiguration(target_size=2500)
        chunks = chunk_text_by_characters(text, config)

        assert "'Go away'" in chunks[0].content

    def test_long_quoted_passage(self):
        """Long quoted passages may need to be chunked."""
        long_quote = '"' + "This is a very long quote. " * 100 + '"'  # ~2800 chars
        text = f"The speaker said {long_quote} and everyone applauded."
        config = ChunkingConfiguration(target_size=1000, min_tolerance=0.8, max_tolerance=1.2)
        chunks = chunk_text_by_characters(text, config)

        # With very long quotes, may need to split
        # But should prefer sentence boundaries within the quote
        assert len(chunks) >= 1


class TestOversizedSentenceHandling:
    """Test handling of oversized single sentences (T045)."""

    def test_very_long_sentence_allowed_oversized(self):
        """Single sentence exceeding max size should be allowed (logged warning)."""
        # Create a sentence longer than max_size
        long_sentence = "This " + "very " * 300 + "long sentence ends here."  # ~1500 chars
        config = ChunkingConfiguration(target_size=500, min_tolerance=0.8, max_tolerance=1.2)
        chunks = chunk_text_by_characters(long_sentence, config)

        # Should create at least one chunk
        assert len(chunks) >= 1
        # The sentence should be preserved (possibly split at forced boundaries)
        combined = " ".join([c.content for c in chunks])
        assert "sentence ends here" in combined

    def test_oversized_chunk_has_boundary_type(self):
        """Oversized chunks should have appropriate boundary type."""
        long_para = "Word " * 1000 + "end."  # Very long paragraph
        config = ChunkingConfiguration(target_size=500, min_tolerance=0.8, max_tolerance=1.2)
        chunks = chunk_text_by_characters(long_para, config)

        # Check boundary types
        for chunk in chunks:
            assert chunk.boundary_type in [
                BoundaryType.SENTENCE_END,
                BoundaryType.PARAGRAPH_END,
                BoundaryType.FORCED_SIZE,
                BoundaryType.SECTION_END,
                BoundaryType.CHAPTER_END
            ]


class TestBoundaryTypeTracking:
    """Test boundary_type tracking in chunks (T043)."""

    def test_sentence_end_boundary_type(self):
        """Chunks ending at sentences should have SENTENCE_END type."""
        text = "First sentence. Second sentence."
        config = ChunkingConfiguration(target_size=2500)
        chunks = chunk_text_by_characters(text, config)

        # Single chunk, ends at sentence
        assert chunks[0].boundary_type in [BoundaryType.SENTENCE_END, BoundaryType.PARAGRAPH_END]

    def test_paragraph_end_boundary_type(self):
        """Chunks ending at paragraphs should have PARAGRAPH_END type."""
        text = "First paragraph content.\n\nSecond paragraph content."
        config = ChunkingConfiguration(target_size=2500)
        chunks = chunk_text_by_characters(text, config)

        # Should track paragraph boundaries
        assert chunks[0].boundary_type in [BoundaryType.SENTENCE_END, BoundaryType.PARAGRAPH_END]

    def test_multiple_chunks_have_boundary_types(self):
        """All chunks should have boundary types assigned."""
        para = "This is a test paragraph with content. " * 50  # ~2000 chars
        text = f"{para}\n\n{para}\n\n{para}"
        config = ChunkingConfiguration(target_size=2500, min_tolerance=0.8, max_tolerance=1.2)
        chunks = chunk_text_by_characters(text, config)

        for chunk in chunks:
            assert chunk.boundary_type is not None
            assert isinstance(chunk.boundary_type, BoundaryType)
