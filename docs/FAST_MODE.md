# EPUB Fast Mode

Fast Mode is an alternative EPUB translation method that works with pure text instead of HTML.

---

## When to Use Fast Mode

| Use Fast Mode | Use Standard Mode |
|---------------|-------------------|
| Placeholders appear in output (⟦TAG0⟧) | No placeholder issues |
| EPUB won't open in your reader | EPUB opens correctly |
| You don't need complex formatting | Complex formatting needed |

---

## How It Works

### Standard Mode (default)
1. Parses EPUB XML structure
2. Replaces HTML tags with placeholders (`⟦TAG0⟧`) during translation
3. Restores tags after translation

**Note**: The model must preserve placeholders exactly in its output.

### Fast Mode
1. Extracts pure text from EPUB (strips all HTML)
2. Translates clean text (no placeholders)
3. Rebuilds a new EPUB 2.0 with basic formatting

---

## What's Preserved

| Element | Fast Mode | Standard Mode |
|---------|-----------|---------------|
| Text content | Yes | Yes |
| Chapters | Yes | Yes |
| Paragraphs | Yes | Yes |
| Images | Yes (optional) | Yes |
| Bold/Italic | Basic | Full |
| Complex CSS | No | Yes |
| Tables | Simplified | Full |
| Custom fonts | No | Yes |

---

## Usage

### Web Interface

Check the "Fast Mode" checkbox before starting translation.

### Command Line

```bash
python translate.py -i book.epub -o book_translated.epub --fast-mode
```

### Without Images

Images are preserved by default. To disable:

```bash
python translate.py -i book.epub -o book_translated.epub --fast-mode --no-images
```

---

## Output Format

Fast Mode produces **EPUB 2.0** files with:

- Flat directory structure (no OEBPS folder)
- Correct ZIP ordering (mimetype first)
- Standard NCX navigation
- Basic HTML chapters

---

## Automatic Recommendation

TBL detects models ≤12B parameters and displays a recommendation to use Fast Mode:

- **CLI**: Message before translation starts
- **Web**: Recommendation when selecting a small model

---

## Troubleshooting

### "Placeholders remain in text" (⟦TAG0⟧)

The model did not preserve the placeholder tags.

**Solution**: Use Fast Mode.

### "EPUB won't open in my reader"

Some readers are strict about EPUB format.

**Solutions**:
1. Use Fast Mode for EPUB 2.0 output
2. Test with Calibre

### "Lost formatting"

Fast Mode simplifies formatting by design.

**Solution**: Use Standard Mode if formatting is important.
