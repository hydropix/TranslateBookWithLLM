# Test Fixtures

This directory contains sample EPUB files for testing the EPUB chunking and translation pipeline.

## Available Fixtures

### simple.epub
- Single chapter
- Basic text content
- Tests single-chapter processing

### multi_chapter.epub
- Three chapters of varying lengths
- Short, medium, and long chapters
- Tests per-chapter chunking and statistics aggregation

### long_sentences.epub
- Contains unusually long sentences
- Tests boundary detection edge cases
- Includes abbreviations (Dr., Mr., Corp., Inc.)
- Tests oversized chunk handling

### mixed_content.epub
- Multiple content types
- Headers, quotes, abbreviations
- URLs and technical terms
- Consecutive blank lines
- Tests comprehensive boundary detection

## Regenerating Fixtures

To regenerate the sample EPUB files:

```bash
python tests/fixtures/create_sample_epubs.py
```

## Using Fixtures in Tests

```python
import os

fixtures_dir = os.path.join(os.path.dirname(__file__), '..', 'fixtures')
epub_path = os.path.join(fixtures_dir, 'simple.epub')
```

## EPUB Structure

All fixtures are valid EPUB 2.0 files with:
- Correct mimetype (first, uncompressed)
- Valid META-INF/container.xml
- Complete content.opf manifest
- NCX navigation document
- Basic CSS stylesheet
- Well-formed XHTML chapter files

## Validation

These EPUBs should pass epubcheck validation:

```bash
epubcheck tests/fixtures/simple.epub
```
