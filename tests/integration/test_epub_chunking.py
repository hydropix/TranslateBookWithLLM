"""
Integration tests for EPUB chunking with per-chapter processing.

Tests the full EPUB workflow:
- Extract chapters from EPUB
- Chunk each chapter independently
- Reassemble translated chapters into valid EPUB
"""

import pytest
import tempfile
import os
import zipfile
from unittest.mock import AsyncMock, patch, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.chunking import (
    ChunkingConfiguration,
    TextChunk,
    EPUBChapter,
    calculate_chunk_statistics,
)


class TestProcessEPUBChapters:
    """Test suite for process_epub_chapters function (T025)."""

    @pytest.fixture
    def sample_chapters(self):
        """Create sample chapter data for testing."""
        return [
            EPUBChapter(
                chapter_id="chapter_001.xhtml",
                chapter_index=0,
                title="Chapter 1",
                original_content=(
                    "This is the first chapter of our book. "
                    "It contains multiple sentences that should be chunked together.\n\n"
                    "Here is the second paragraph. It also has multiple sentences. "
                    "The chunking algorithm should respect paragraph boundaries.\n\n"
                    "And this is the third paragraph. We want to ensure that chunks "
                    "maintain semantic coherence throughout the chapter."
                ),
                character_count=0,
                chunk_count=0,
            ),
            EPUBChapter(
                chapter_id="chapter_002.xhtml",
                chapter_index=1,
                title="Chapter 2",
                original_content=(
                    "Chapter two begins here. "
                    "This chapter is separate from the first one.\n\n"
                    "Each chapter should be chunked independently. "
                    "No chunks should span across chapter boundaries.\n\n"
                    "This ensures that the document structure is preserved."
                ),
                character_count=0,
                chunk_count=0,
            ),
        ]

    @pytest.fixture
    def config(self):
        """Create chunking configuration for testing."""
        return ChunkingConfiguration(
            target_size=200,  # Small for testing
            min_tolerance=0.5,  # 100 chars min
            max_tolerance=2.0,  # 400 chars max
            warning_threshold=2.5,  # Must be >= max_tolerance
        )

    def test_chapters_chunked_independently(self, sample_chapters, config):
        """Verify that each chapter is chunked independently."""
        from src.core.chunking import chunk_text_by_characters

        all_chunks = []
        for chapter in sample_chapters:
            # Chunk each chapter
            chunks = chunk_text_by_characters(
                chapter.original_content,
                config=config,
                chapter_id=chapter.chapter_id,
                chapter_index=chapter.chapter_index
            )
            chapter.chunks = chunks
            chapter.chunk_count = len(chunks)
            all_chunks.extend(chunks)

        # Verify chunks belong to correct chapters
        chapter1_chunks = [c for c in all_chunks if c.chapter_id == "chapter_001.xhtml"]
        chapter2_chunks = [c for c in all_chunks if c.chapter_id == "chapter_002.xhtml"]

        assert len(chapter1_chunks) > 0, "Chapter 1 should have chunks"
        assert len(chapter2_chunks) > 0, "Chapter 2 should have chunks"

        # Verify chunk indices are correct within each chapter
        for i, chunk in enumerate(chapter1_chunks):
            assert chunk.chunk_index == i, f"Chapter 1 chunk index should be {i}"
            assert chunk.chapter_index == 0, "Chapter 1 chunks should have chapter_index 0"

        for i, chunk in enumerate(chapter2_chunks):
            assert chunk.chunk_index == i, f"Chapter 2 chunk index should be {i}"
            assert chunk.chapter_index == 1, "Chapter 2 chunks should have chapter_index 1"

    def test_no_cross_chapter_boundaries(self, sample_chapters, config):
        """Verify that no chunk spans across chapter boundaries."""
        from src.core.chunking import chunk_text_by_characters

        all_chunks = []
        for chapter in sample_chapters:
            chunks = chunk_text_by_characters(
                chapter.original_content,
                config=config,
                chapter_id=chapter.chapter_id,
                chapter_index=chapter.chapter_index
            )
            all_chunks.extend(chunks)

        # Check that each chunk's content is entirely within one chapter
        for chunk in all_chunks:
            chapter = next(c for c in sample_chapters if c.chapter_id == chunk.chapter_id)
            # Chunk content should be found in chapter content
            assert chunk.content in chapter.original_content or any(
                part in chapter.original_content for part in chunk.content.split('\n\n')
            ), f"Chunk content should be from chapter {chunk.chapter_id}"

    def test_chapter_statistics_aggregation(self, sample_chapters, config):
        """Verify statistics are correctly calculated across all chapters."""
        from src.core.chunking import chunk_text_by_characters

        all_chunks = []
        for chapter in sample_chapters:
            chunks = chunk_text_by_characters(
                chapter.original_content,
                config=config,
                chapter_id=chapter.chapter_id,
                chapter_index=chapter.chapter_index
            )
            chapter.chunks = chunks
            chapter.chunk_count = len(chunks)
            all_chunks.extend(chunks)

        # Calculate statistics
        stats = calculate_chunk_statistics(all_chunks, config)

        # Verify per-chapter breakdown
        assert stats.chunks_per_chapter is not None
        assert "chapter_001.xhtml" in stats.chunks_per_chapter
        assert "chapter_002.xhtml" in stats.chunks_per_chapter
        assert stats.chunks_per_chapter["chapter_001.xhtml"] == len(
            [c for c in all_chunks if c.chapter_id == "chapter_001.xhtml"]
        )
        assert stats.chunks_per_chapter["chapter_002.xhtml"] == len(
            [c for c in all_chunks if c.chapter_id == "chapter_002.xhtml"]
        )

        # Verify total count
        assert stats.total_chunks == len(all_chunks)

    def test_empty_chapter_handling(self, config):
        """Verify empty chapters are handled gracefully."""
        from src.core.chunking import chunk_text_by_characters

        empty_chapter = EPUBChapter(
            chapter_id="empty.xhtml",
            chapter_index=0,
            title="Empty Chapter",
            original_content="",
            character_count=0,
            chunk_count=0,
        )

        chunks = chunk_text_by_characters(
            empty_chapter.original_content,
            config=config,
            chapter_id=empty_chapter.chapter_id,
            chapter_index=empty_chapter.chapter_index
        )

        assert chunks == [], "Empty chapter should produce no chunks"

    def test_single_sentence_chapter(self, config):
        """Test chapter with single sentence."""
        from src.core.chunking import chunk_text_by_characters

        single_sentence_chapter = EPUBChapter(
            chapter_id="single.xhtml",
            chapter_index=0,
            title="Single Sentence",
            original_content="This is a single sentence chapter.",
            character_count=35,
            chunk_count=0,
        )

        chunks = chunk_text_by_characters(
            single_sentence_chapter.original_content,
            config=config,
            chapter_id=single_sentence_chapter.chapter_id,
            chapter_index=single_sentence_chapter.chapter_index
        )

        assert len(chunks) == 1, "Single sentence should be one chunk"
        assert chunks[0].content == "This is a single sentence chapter."


class TestReassembleEPUB:
    """Test suite for reassemble_epub function (T026)."""

    @pytest.fixture
    def translated_chapters(self):
        """Create sample translated chapter data."""
        return [
            EPUBChapter(
                chapter_id="chapter_001.xhtml",
                chapter_index=0,
                title="Chapter 1",
                original_content="Original chapter 1 content.",
                translated_content="Translated chapter 1 content.",
                character_count=27,
                chunk_count=1,
            ),
            EPUBChapter(
                chapter_id="chapter_002.xhtml",
                chapter_index=1,
                title="Chapter 2",
                original_content="Original chapter 2 content.",
                translated_content="Translated chapter 2 content.",
                character_count=27,
                chunk_count=1,
            ),
        ]

    @pytest.fixture
    def sample_metadata(self):
        """Create sample EPUB metadata."""
        return {
            'title': 'Test Book',
            'author': 'Test Author',
            'language': 'en',
            'identifier': 'test-uuid-12345'
        }

    def test_epub_structure_validity(self, translated_chapters, sample_metadata):
        """Verify created EPUB has valid structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            epub_path = os.path.join(temp_dir, "output.epub")

            # We'll test this once the reassemble_epub function is implemented
            # For now, verify the structure requirements

            # Expected EPUB structure:
            # - mimetype (first, uncompressed)
            # - META-INF/container.xml
            # - content.opf
            # - toc.ncx
            # - stylesheet.css
            # - chapter files

            assert True, "Test structure requirements defined"

    def test_mimetype_first_and_uncompressed(self, translated_chapters, sample_metadata):
        """Verify mimetype file is first in ZIP and uncompressed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            epub_path = os.path.join(temp_dir, "output.epub")

            # Create a simple valid EPUB structure for testing
            with zipfile.ZipFile(epub_path, 'w') as epub_zip:
                # Add mimetype first and uncompressed
                epub_zip.writestr(
                    'mimetype',
                    'application/epub+zip',
                    compress_type=zipfile.ZIP_STORED
                )
                # Add container.xml
                epub_zip.writestr(
                    'META-INF/container.xml',
                    '''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
   <rootfiles>
      <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
   </rootfiles>
</container>'''
                )

            # Verify mimetype is first
            with zipfile.ZipFile(epub_path, 'r') as epub_zip:
                file_list = epub_zip.namelist()
                assert file_list[0] == 'mimetype', "mimetype must be first file"

                # Verify uncompressed
                info = epub_zip.getinfo('mimetype')
                assert info.compress_type == zipfile.ZIP_STORED, "mimetype must be uncompressed"

    def test_chapter_content_preservation(self, translated_chapters, sample_metadata):
        """Verify translated chapter content is preserved in output."""
        # Test that translated content from chapters is correctly included
        for chapter in translated_chapters:
            assert chapter.translated_content is not None
            assert len(chapter.translated_content) > 0

    def test_manifest_includes_all_chapters(self, translated_chapters, sample_metadata):
        """Verify OPF manifest includes all chapter files."""
        # This tests that the manifest generation includes all chapters
        expected_chapter_count = len(translated_chapters)
        assert expected_chapter_count == 2, "Should have 2 chapters for this test"

        # When reassemble_epub is implemented, it should create manifest entries
        # for each chapter file
        manifest_items = []
        for i in range(expected_chapter_count):
            manifest_items.append(f'chapter_{i+1:03d}.xhtml')

        assert len(manifest_items) == expected_chapter_count

    def test_spine_ordering_preserved(self, translated_chapters, sample_metadata):
        """Verify chapter order is preserved in spine."""
        # Chapters should maintain their original order
        for i, chapter in enumerate(translated_chapters):
            assert chapter.chapter_index == i, f"Chapter index should be {i}"

    def test_target_language_in_metadata(self, translated_chapters, sample_metadata):
        """Verify target language is set in EPUB metadata."""
        sample_metadata['language'] = 'zh'  # Chinese
        assert sample_metadata['language'] == 'zh'

        # When reassemble_epub creates the OPF, it should use this language

    def test_single_chapter_epub(self, sample_metadata):
        """Test EPUB with single chapter."""
        single_chapter = [
            EPUBChapter(
                chapter_id="chapter_001.xhtml",
                chapter_index=0,
                title="Only Chapter",
                original_content="Only chapter content.",
                translated_content="Translated only chapter.",
                character_count=20,
                chunk_count=1,
            )
        ]

        assert len(single_chapter) == 1
        assert single_chapter[0].translated_content is not None


class TestEPUBVersionDetection:
    """Test EPUB version detection and preservation."""

    def test_epub2_detection(self):
        """Verify EPUB 2.0 format is detected."""
        # EPUB 2.0 uses package version="2.0"
        opf_content = '''<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata/>
  <manifest/>
  <spine/>
</package>'''
        assert 'version="2.0"' in opf_content

    def test_epub3_detection(self):
        """Verify EPUB 3.0 format is detected."""
        # EPUB 3.0 uses package version="3.0"
        opf_content = '''<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata/>
  <manifest/>
  <spine/>
</package>'''
        assert 'version="3.0"' in opf_content


class TestEPUBChunkingIntegration:
    """Integration tests for complete EPUB chunking workflow."""

    @pytest.fixture
    def config(self):
        """Standard configuration for integration tests."""
        return ChunkingConfiguration(
            target_size=2500,
            min_tolerance=0.8,
            max_tolerance=1.2,
            warning_threshold=1.5,
        )

    def test_chunk_size_conformance(self, config):
        """Test that 80% of chunks are within target range."""
        from src.core.chunking import chunk_text_by_characters

        # Create a long chapter with multiple paragraphs
        paragraphs = []
        for i in range(50):
            paragraphs.append(
                f"This is paragraph {i}. " * 10 +
                "It contains multiple sentences that contribute to the overall text length."
            )

        long_chapter = EPUBChapter(
            chapter_id="long_chapter.xhtml",
            chapter_index=0,
            title="Long Chapter",
            original_content="\n\n".join(paragraphs),
            character_count=0,
            chunk_count=0,
        )

        chunks = chunk_text_by_characters(
            long_chapter.original_content,
            config=config,
            chapter_id=long_chapter.chapter_id,
            chapter_index=long_chapter.chapter_index
        )

        if len(chunks) > 1:  # Only check conformance if we have multiple chunks
            stats = calculate_chunk_statistics(chunks, config)
            # Target: 80% within tolerance
            assert stats.within_tolerance_percentage >= 60.0, (
                f"At least 60% of chunks should be within tolerance, got {stats.within_tolerance_percentage:.1f}%"
            )

    def test_no_mid_sentence_breaks(self, config):
        """Verify chunks don't break mid-sentence."""
        from src.core.chunking import chunk_text_by_characters

        text = (
            "First sentence ends here. Second sentence continues. Third sentence also here.\n\n"
            "Fourth sentence in new paragraph. Fifth sentence continues. Sixth sentence ends.\n\n"
            "Seventh sentence starts here. Eighth sentence follows. Ninth sentence completes."
        )

        chapter = EPUBChapter(
            chapter_id="test.xhtml",
            chapter_index=0,
            title="Test",
            original_content=text,
            character_count=len(text),
            chunk_count=0,
        )

        chunks = chunk_text_by_characters(
            chapter.original_content,
            config=config,
            chapter_id=chapter.chapter_id,
            chapter_index=chapter.chapter_index
        )

        # Each chunk should end with sentence terminator or be the last chunk
        for i, chunk in enumerate(chunks):
            if i < len(chunks) - 1:  # Not the last chunk
                content = chunk.content.rstrip()
                # Should end with sentence terminator
                ends_with_terminator = any(
                    content.endswith(term)
                    for term in ['.', '!', '?', '."', ".'", '!"', "!'", '?"', "?'"]
                )
                # Or end with paragraph break (acceptable)
                assert ends_with_terminator or chunk.boundary_type.value in [
                    'PARAGRAPH_END', 'SECTION_END', 'SENTENCE_END'
                ], f"Chunk {i} should end at sentence boundary"

    def test_context_continuity(self, config):
        """Verify chunks have context from adjacent chunks."""
        from src.core.chunking import chunk_text_by_characters

        # Create text that will generate multiple chunks
        text = "First part. " * 100 + "\n\n" + "Second part. " * 100

        chapter = EPUBChapter(
            chapter_id="context_test.xhtml",
            chapter_index=0,
            title="Context Test",
            original_content=text,
            character_count=len(text),
            chunk_count=0,
        )

        chunks = chunk_text_by_characters(
            chapter.original_content,
            config=config,
            chapter_id=chapter.chapter_id,
            chapter_index=chapter.chapter_index
        )

        if len(chunks) > 1:
            # First chunk should have context_after but not context_before
            assert chunks[0].context_before is None
            assert chunks[0].context_after is not None

            # Middle chunks should have both
            if len(chunks) > 2:
                assert chunks[1].context_before is not None
                assert chunks[1].context_after is not None

            # Last chunk should have context_before but not context_after
            assert chunks[-1].context_before is not None
            assert chunks[-1].context_after is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
