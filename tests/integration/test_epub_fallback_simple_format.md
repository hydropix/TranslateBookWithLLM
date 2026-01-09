# Integration Test: EPUB Fallback with Simple Format [N]

**Test ID:** Step 17 - Integration Test
**Priority:** CRITICAL
**Objective:** Verify that the proportional fallback uses the correct simple format `[N]` on a real EPUB

## Prerequisites

1. A small test EPUB file (2-5 pages)
2. The EPUB should contain text without brackets `[` in the content (to trigger simple format detection)
3. LLM provider configured (Ollama, Gemini, OpenAI, or OpenRouter)

## Test Procedure

### Step 1: Prepare Test EPUB

Use a small EPUB without brackets in the text. You can create one or use an existing one.

### Step 2: Force the Fallback

To force the proportional fallback to trigger, you have two options:

**Option A: Temporarily modify configuration**
```python
# In src/config.py, temporarily set:
MAX_PLACEHOLDER_CORRECTION_ATTEMPTS = 0
```

**Option B: Use an LLM known to remove placeholders**
Use a smaller model or configure the LLM to be more aggressive in its translations.

### Step 3: Execute Translation

```bash
cd "C:\Users\Bruno\Documents\GitHub\TranslateBookWithLLM"
python translate.py -i test.epub -o test_translated.epub -sl English -tl French
```

### Step 4: Verify Logs

Check the console output for:

1. ✅ Look for message: "Proportional fallback used"
2. ✅ Look for message: "Format: [N]" (single brackets)
3. ❌ Should NOT see: "Format: [[N]]" (double brackets)
4. ❌ Should NOT see XML errors like "Opening and ending tag mismatch"

### Step 5: Verify the Result

1. **Open the translated EPUB:**
   ```bash
   # Use your preferred EPUB reader (Calibre, Adobe Digital Editions, etc.)
   start test_translated.epub
   ```

2. **Check for errors:**
   - ✅ EPUB should open without errors
   - ✅ Formatting should be preserved
   - ✅ No duplicate tags (e.g., `</span></span>`)

3. **Extract and inspect HTML (optional):**
   ```bash
   # Extract EPUB
   unzip test_translated.epub -d test_extracted/

   # Check for remaining placeholders (should be NONE)
   grep -r "\[.\+\]" test_extracted/OEBPS/

   # Validate XML
   xmllint --noout test_extracted/OEBPS/*.xhtml
   ```

## Expected Results

| Check | Expected Result |
|-------|----------------|
| Translation completes | ✅ Success |
| Fallback triggered | ✅ "Proportional fallback used" in logs |
| Format detected | ✅ "Format: [N]" (simple format) |
| No format mixing | ✅ No mix of `[N]` and `[[N]]` |
| EPUB opens | ✅ Opens correctly in reader |
| XML valid | ✅ No parsing errors |
| No placeholders remain | ✅ All placeholders restored to HTML tags |

## Success Criteria

- [x] EPUB translates successfully
- [x] Proportional fallback uses simple format `[N]`
- [x] No mixed formats in the same document
- [x] EPUB is valid and readable
- [x] No XML parsing errors

## Troubleshooting

**If fallback doesn't trigger:**
- Set `MAX_PLACEHOLDER_CORRECTION_ATTEMPTS = 0` in [src/config.py](../../src/config.py)
- Use a less capable LLM model
- Use a longer text chunk

**If format is wrong:**
- Check that the original EPUB has no `[` characters in text
- Verify `detect_placeholder_format_in_text()` is being called
- Check logs for format detection messages

## Cleanup

After testing, remember to restore original settings:
```python
# In src/config.py, restore:
MAX_PLACEHOLDER_CORRECTION_ATTEMPTS = 3  # or original value
```

## Test Status

- [ ] Test prepared
- [ ] Test executed
- [ ] Results verified
- [ ] Test passed

**Date:** ___________
**Tester:** ___________
**Result:** PASS / FAIL
**Notes:** ___________
