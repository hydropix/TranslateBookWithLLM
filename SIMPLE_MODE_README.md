# EPUB Simple Mode - Production Documentation

## Overview

The Simple Mode EPUB processor provides a **robust, production-ready** solution for translating EPUB files by converting them to pure text, translating, and rebuilding compliant EPUB 2.0 files.

## Key Features

### ✅ Maximum Compatibility
- **EPUB 2.0 format** - Compatible with ALL readers including strict ones (Aquile Reader, Adobe Digital Editions, etc.)
- **Flat directory structure** - No OEBPS folder for better compatibility
- **Correct ZIP file ordering** - Follows EPUB specification exactly
- **UTF-8 encoding** - Proper character encoding throughout

### ✅ Robust Processing
- **Pure text extraction** - Eliminates ALL HTML/XML tag issues
- **Intelligent chunking** - Respects paragraph boundaries
- **Error resilience** - Continues processing even if individual chapters fail
- **Comprehensive validation** - Checks EPUB structure at every step

### ✅ Production Ready
- **Proper error handling** - Clear error messages for all failure modes
- **Logging integration** - Optional callbacks for progress tracking
- **Clean code** - Well-documented, maintainable codebase
- **No data loss** - Preserves all text content

## How It Works

### 1. Text Extraction
```
EPUB Input → Extract Pure Text → Remove ALL Tags → Output: Plain Text
```

The extractor:
- Finds and parses the OPF file (package document)
- Reads content files in spine order (reading order)
- Strips ALL HTML/XML tags using lxml
- Preserves paragraph structure
- Handles malformed HTML gracefully

### 2. Translation
```
Plain Text → Split into Chunks → Translate via LLM → Join Results
```

Uses the standard text translation pipeline:
- Chunks respect sentence boundaries
- Context from previous chunks maintained
- Configurable chunk size
- Retry logic for failed translations

### 3. EPUB Rebuild
```
Translated Text → Auto-split Chapters → Generate EPUB 2.0 → Valid Output
```

The builder creates:
- **mimetype** (uncompressed, first file)
- **META-INF/container.xml** (points to content.opf)
- **content.opf** (EPUB 2.0 package document)
- **toc.ncx** (navigation for EPUB 2 readers)
- **stylesheet.css** (clean, readable styling)
- **chapter_NNN.xhtml** (content files)

### Critical: ZIP File Order

The EPUB specification requires files in this exact order:
```
1. mimetype (MUST be first, MUST be uncompressed)
2. META-INF/container.xml (MUST be second)
3. content.opf
4. toc.ncx
5. stylesheet.css
6. chapter_001.xhtml
7. chapter_002.xhtml
...
```

**This order is critical for strict EPUB readers!**

## Technical Specifications

### EPUB Structure
```
output.epub
├── mimetype                    # Application type (20 bytes)
├── META-INF/
│   └── container.xml          # Points to content.opf
├── content.opf                # Package document (EPUB 2.0)
├── toc.ncx                    # Navigation (EPUB 2 compatibility)
├── stylesheet.css             # Clean styling
├── chapter_001.xhtml          # Content chapters
├── chapter_002.xhtml
└── chapter_NNN.xhtml
```

### File Formats

#### content.opf (EPUB 2.0)
```xml
<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="uuid_id">
  <metadata xmlns:opf="http://www.idpf.org/2007/opf"
            xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Book Title</dc:title>
    <dc:creator opf:role="aut">Author Name</dc:creator>
    <dc:language>fr</dc:language>
    <dc:identifier id="uuid_id" opf:scheme="uuid">...</dc:identifier>
  </metadata>
  <manifest>
    <item id="html1" href="chapter_001.xhtml" media-type="application/xhtml+xml"/>
    ...
  </manifest>
  <spine toc="ncx">
    <itemref idref="html1"/>
    ...
  </spine>
</package>
```

#### chapter_NNN.xhtml
```xml
<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml" lang="fr" xml:lang="fr">
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
    <title>Chapter 1</title>
    <link rel="stylesheet" type="text/css" href="stylesheet.css"/>
  </head>
  <body>
    <h1>Chapter 1</h1>
    <p>Content here...</p>
  </body>
</html>
```

## Usage

### Command Line

```bash
# Basic usage
python translate.py -i input.epub -o output.epub --simple-mode

# With specific languages
python translate.py -i book.epub -o book_fr.epub -sl English -tl French --simple-mode

# With custom model
python translate.py -i book.epub -o book_pt.epub -tl Portuguese -m mistral-large --simple-mode
```

### Web Interface

1. Upload EPUB file
2. Select source and target languages
3. Enable "Simple Mode" checkbox
4. Click "Translate"

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `FileNotFoundError` | EPUB file doesn't exist | Check file path |
| `BadZipFile` | Corrupted EPUB | Try re-downloading the file |
| `ValueError: No OPF file found` | Invalid EPUB structure | File may not be a valid EPUB |
| `ValueError: No text content extracted` | Empty EPUB | Check source file has readable content |

### Error Recovery

The processor is designed to be resilient:
- **Per-chapter errors**: Logs warning and continues with other chapters
- **Metadata errors**: Uses sensible defaults (title="Untitled", etc.)
- **Malformed HTML**: lxml parser handles with `recover=True`

## Configuration

### Chapter Size

Default: 5000 words per chapter (~15-20 pages)

Adjust in `_auto_split_into_chapters()`:
```python
chapters = _auto_split_into_chapters(text, words_per_chapter=3000)  # Shorter chapters
```

### CSS Styling

Edit `_create_simple_css()` to customize appearance:
```python
def _create_simple_css() -> str:
    return '''
    body {
        font-family: Georgia, serif;
        line-height: 1.6;
        margin: 2em;
    }
    '''
```

## Troubleshooting

### EPUB won't open in reader

**Symptoms**: File opens in Calibre but not in other readers

**Diagnosis**:
```bash
# Check ZIP file order
python -m zipfile -l output.epub | head -10
```

Should show:
```
1. mimetype
2. META-INF/container.xml
3. content.opf
...
```

**Solution**: Ensure you're using the latest version of the processor (file order fix applied).

### Missing content

**Symptoms**: Translated EPUB is much smaller than original

**Possible causes**:
1. Translation failed for most chunks
2. Original EPUB had mostly images/non-text content
3. Extraction error

**Diagnosis**: Check logs for extraction errors

### Character encoding issues

**Symptoms**: Accented characters appear as �

**This should NOT happen** - UTF-8 is handled correctly throughout.

If you see this:
1. Check your terminal encoding (display issue, not file issue)
2. Open the EPUB in a reader to verify actual content
3. Extract a chapter XHTML and check with a hex editor

## Performance

### Typical Processing Time

| EPUB Size | Text Length | Translation Time |
|-----------|-------------|------------------|
| 1 MB | ~50k words | 2-5 minutes |
| 5 MB | ~250k words | 10-30 minutes |
| 10 MB | ~500k words | 20-60 minutes |

*Times vary based on LLM speed and chunk size*

### Optimization Tips

1. **Increase chunk size** for faster processing (but may reduce quality)
2. **Use faster LLM model** (e.g., mistral-small vs mistral-large)
3. **Enable parallel processing** if supported by your LLM provider

## Validation

### Manual Validation

1. **Open in multiple readers**:
   - Calibre (lenient)
   - Adobe Digital Editions (strict)
   - Aquile Reader (very strict)

2. **Check structure**:
   ```bash
   unzip -l output.epub
   ```

3. **Validate with epubcheck**:
   ```bash
   java -jar epubcheck.jar output.epub
   ```

### Automated Testing

The processor includes validation at every step:
- ZIP file integrity
- OPF parsing
- Manifest/spine validation
- Content extraction success
- Final EPUB structure

## Maintenance

### Code Location

- Main processor: `src/core/epub/epub_simple_processor.py`
- Configuration: `src/config.py`
- Text translation: `src/core/text_processor.py`
- LLM integration: `src/core/translator.py`

### Testing

When making changes, test with:
1. Small EPUB (< 1MB)
2. Large EPUB (> 5MB)
3. Complex EPUB (lots of formatting)
4. Multiple EPUB readers

### Logging

Enable debug logging:
```python
def my_log_callback(event, message):
    print(f"[{event}] {message}")

await extract_pure_text_from_epub(path, log_callback=my_log_callback)
```

## Support

For issues or questions:
1. Check this documentation
2. Review error messages carefully
3. Test with a minimal example
4. Check GitHub issues

## License

Same as parent project.

---

**Version**: 1.0.0 (Production Ready)
**Last Updated**: 2025-11-09
**Status**: ✅ Validated with strict EPUB readers
