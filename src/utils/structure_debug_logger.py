"""
Debug logging system for HTML structure preservation in EPUB translation

This module provides specialized logging to trace the exact origin of HTML structure corruption.
It logs at every critical step of the translation pipeline to identify where tags get misaligned.

Log file location: translated_files/structure_debug_{translation_id}.log
"""
import os
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
from lxml import etree
import re


class StructureDebugLogger:
    """
    Logs detailed information about HTML structure preservation through the translation pipeline.

    Tracks:
    1. Original HTML structure (tag counts, nesting)
    2. Tag preservation (placeholder mapping)
    3. Chunking (how chunks split the structure)
    4. Translation (placeholder changes per chunk)
    5. Reconstruction (tag restoration)
    6. Final validation (XML parsing errors)
    """

    def __init__(self, output_dir: str = "translated_files", translation_id: str = None):
        self.output_dir = output_dir
        self.translation_id = translation_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(output_dir, f"structure_debug_{self.translation_id}.log")

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Initialize log file with header
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("HTML STRUCTURE DEBUG LOG\n")
            f.write(f"Translation ID: {self.translation_id}\n")
            f.write(f"Started: {datetime.now().isoformat()}\n")
            f.write("="*80 + "\n\n")

    def _write(self, section: str, message: str):
        """Write a log entry with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] [{section}] {message}\n")

    def _write_separator(self, title: str = ""):
        """Write a visual separator"""
        with open(self.log_file, 'a', encoding='utf-8') as f:
            if title:
                f.write(f"\n{'='*80}\n{title.center(80)}\n{'='*80}\n\n")
            else:
                f.write(f"\n{'-'*80}\n\n")

    def log_original_html(self, html: str, file_path: str = None):
        """
        Log the original HTML structure before processing

        Args:
            html: Original HTML content
            file_path: Optional file path for context
        """
        self._write_separator("ORIGINAL HTML STRUCTURE")

        if file_path:
            self._write("FILE", f"Processing: {file_path}")

        # Basic stats
        self._write("LENGTH", f"{len(html)} characters")

        # Count tags
        opening_tags = re.findall(r'<(\w+)[^>]*>', html)
        closing_tags = re.findall(r'</(\w+)>', html)

        self._write("TAGS", f"Opening tags: {len(opening_tags)}, Closing tags: {len(closing_tags)}")

        # Tag balance check
        from collections import Counter
        opening_count = Counter(opening_tags)
        closing_count = Counter(closing_tags)

        self._write("TAG_BALANCE", "Tag balance:")
        for tag in sorted(set(opening_tags + closing_tags)):
            open_c = opening_count.get(tag, 0)
            close_c = closing_count.get(tag, 0)
            balance = "✓" if open_c == close_c else "✗ UNBALANCED"
            self._write("TAG_BALANCE", f"  <{tag}>: {open_c} opening, {close_c} closing {balance}")

        # Calculate HTML hash for integrity checking
        html_hash = hashlib.md5(html.encode('utf-8')).hexdigest()[:8]
        self._write("HASH", f"HTML hash: {html_hash}")

        # Save snippet for reference
        snippet = html[:500] if len(html) > 500 else html
        self._write("SNIPPET", f"First 500 chars:\n{snippet}")

    def log_tag_preservation(self, text_with_placeholders: str, tag_map: Dict[str, str], placeholder_format: tuple):
        """
        Log tag preservation details

        Args:
            text_with_placeholders: Text after tag replacement
            tag_map: Mapping of placeholders to original tags
            placeholder_format: (prefix, suffix) tuple
        """
        self._write_separator("TAG PRESERVATION")

        prefix, suffix = placeholder_format
        self._write("FORMAT", f"Placeholder format: {prefix}N{suffix}")
        self._write("COUNT", f"Created {len(tag_map)} placeholders")

        # Log each placeholder mapping
        self._write("MAPPING", "Placeholder → Tag mapping:")
        for placeholder, tag in sorted(tag_map.items(), key=lambda x: x[0]):
            # Truncate long tags for readability
            tag_display = tag if len(tag) <= 100 else tag[:97] + "..."
            self._write("MAPPING", f"  {placeholder} → {tag_display}")

        # Verify placeholder sequence
        pattern = re.escape(prefix) + r'(\d+)' + re.escape(suffix)
        found_indices = [int(m) for m in re.findall(pattern, text_with_placeholders)]
        expected_indices = list(range(len(tag_map)))

        if found_indices == expected_indices:
            self._write("SEQUENCE", f"✓ Placeholder sequence is correct: {expected_indices}")
        else:
            self._write("SEQUENCE", f"✗ SEQUENCE MISMATCH!")
            self._write("SEQUENCE", f"  Expected: {expected_indices}")
            self._write("SEQUENCE", f"  Found: {found_indices}")

    def log_chunk_creation(self, chunks: List[Dict], global_tag_map: Dict[str, str]):
        """
        Log chunking details

        Args:
            chunks: List of chunk dictionaries
            global_tag_map: Global tag map for reference
        """
        self._write_separator("CHUNKING")

        self._write("COUNT", f"Created {len(chunks)} chunks")

        for i, chunk in enumerate(chunks):
            self._write_separator(f"Chunk {i+1}/{len(chunks)}")

            text = chunk.get('text', '')
            local_tag_map = chunk.get('local_tag_map', {})
            global_indices = chunk.get('global_indices', [])

            self._write("LENGTH", f"{len(text)} characters")
            self._write("PLACEHOLDERS", f"{len(local_tag_map)} local placeholders")
            self._write("GLOBAL_INDICES", f"Maps to global indices: {global_indices}")

            # Show local to global mapping
            self._write("LOCAL_TO_GLOBAL", "Local → Global mapping:")
            for local_idx, global_idx in enumerate(global_indices):
                local_ph = list(local_tag_map.keys())[local_idx] if local_idx < len(local_tag_map) else "N/A"
                global_ph = f"[[{global_idx}]]"  # Assuming safe format for display
                tag = local_tag_map.get(local_ph, "N/A")
                tag_display = tag if len(tag) <= 60 else tag[:57] + "..."
                self._write("LOCAL_TO_GLOBAL", f"  {local_ph} ({local_idx}) → {global_ph} ({global_idx}): {tag_display}")

            # Show chunk text snippet
            snippet = text[:200] if len(text) > 200 else text
            self._write("TEXT_SNIPPET", f"Text preview:\n{snippet}")

    def log_translation_request(self, chunk_index: int, original_text: str, has_placeholders: bool):
        """
        Log translation request details (ONLY for chunks that will fail)

        Args:
            chunk_index: Index of chunk being translated
            original_text: Original text sent to LLM
            has_placeholders: Whether chunk contains placeholders
        """
        # We'll log this only if the chunk fails - store in memory for now
        pass  # Actual logging will happen in log_translation_response if validation fails

    def log_translation_response(self, chunk_index: int, translated_text: str,
                                 expected_placeholder_count: int, validation_result: bool,
                                 retry_attempt: int = 0):
        """
        Log translation response and validation (ONLY FOR FAILURES)

        Args:
            chunk_index: Index of chunk being translated
            translated_text: Translated text from LLM
            expected_placeholder_count: Expected number of placeholders
            validation_result: Whether validation passed
            retry_attempt: Which retry attempt (0 = first try, 1 = first retry, etc.)
        """
        # Only log validation failures
        if validation_result:
            return

        self._write_separator(f"⚠️ VALIDATION FAILED - Chunk {chunk_index} - Attempt {retry_attempt + 1}")

        # Count placeholders in response
        pattern = r'\[\[(\d+)\]\]|\[(\d+)\]|/(\d+)|\$(\d+)\$|\[id(\d+)\]'
        matches = re.findall(pattern, translated_text)
        actual_count = len(matches)

        # Extract indices
        indices = []
        for match in matches:
            for group in match:
                if group:
                    indices.append(int(group))
                    break

        self._write("PLACEHOLDER_COUNT", f"Expected: {expected_placeholder_count}, Found: {actual_count}")
        self._write("PLACEHOLDER_INDICES", f"Found indices: {indices}")

        # Detailed error analysis
        expected_indices = set(range(expected_placeholder_count))
        found_indices = set(indices)

        missing = expected_indices - found_indices
        extra = found_indices - expected_indices
        duplicates = [idx for idx in indices if indices.count(idx) > 1]

        if missing:
            self._write("ERROR", f"❌ Missing placeholders: {sorted(missing)}")
        if extra:
            self._write("ERROR", f"❌ Extra/wrong placeholders: {sorted(extra)}")
        if duplicates:
            self._write("ERROR", f"❌ Duplicate placeholders: {sorted(set(duplicates))}")
        if indices != sorted(indices):
            self._write("ERROR", f"❌ Out of order: {indices} != {sorted(indices)}")

        # DO NOT log translated text content - too verbose

    def log_fallback_usage(self, chunk_index: int, fallback_type: str, reason: str,
                          original_text: str = None, translated_text: str = None,
                          positions_before: Dict = None, positions_after: Dict = None,
                          result_with_placeholders: str = None):
        """
        Log when fallback mechanism is used

        Args:
            chunk_index: Index of chunk
            fallback_type: Type of fallback (proportional, original, etc.)
            reason: Why fallback was triggered
            original_text: Original text with placeholders (for proportional fallback)
            translated_text: Translated text WITHOUT placeholders (for proportional fallback)
            positions_before: Original placeholder positions dict
            positions_after: Sequential positions dict after processing
            result_with_placeholders: Final result after reinserting placeholders
        """
        self._write_separator(f"🔴 FALLBACK USED - Chunk {chunk_index}")

        self._write("TYPE", f"Fallback type: {fallback_type}")
        self._write("REASON", reason)

        if fallback_type == "proportional":
            # Log detailed proportional fallback info
            if original_text:
                self._write("ORIGINAL_LENGTH", f"{len(original_text)} chars")
                # Count placeholders in original
                pattern = r'\[\[(\d+)\]\]|\[(\d+)\]|/(\d+)|\$(\d+)\$|\[id(\d+)\]'
                orig_ph_count = len(re.findall(pattern, original_text))
                self._write("ORIGINAL_PLACEHOLDERS", f"{orig_ph_count} placeholders")
                self._write("ORIGINAL_SNIPPET", f"First 200 chars:\n{original_text[:200]}")

            if translated_text:
                self._write("TRANSLATED_LENGTH", f"{len(translated_text)} chars")
                trans_ph_count = len(re.findall(pattern, translated_text))
                self._write("TRANSLATED_PLACEHOLDERS", f"{trans_ph_count} placeholders")
                self._write("TRANSLATED_SNIPPET", f"First 200 chars:\n{translated_text[:200]}")

            if positions_before:
                self._write("POSITIONS_BEFORE", f"Original positions: {positions_before}")

            if positions_after:
                self._write("POSITIONS_AFTER", f"Sequential positions: {positions_after}")

            if result_with_placeholders:
                self._write("RESULT_LENGTH", f"{len(result_with_placeholders)} chars")
                result_ph_count = len(re.findall(pattern, result_with_placeholders))
                self._write("RESULT_PLACEHOLDERS", f"{result_ph_count} placeholders reinserted")
                self._write("RESULT_SNIPPET", f"First 300 chars:\n{result_with_placeholders[:300]}")

                # Show where placeholders were inserted
                ph_matches = re.finditer(pattern, result_with_placeholders)
                ph_positions = [(m.group(), m.start()) for m in ph_matches]
                if ph_positions:
                    self._write("PLACEHOLDER_POSITIONS", "Placeholder insertion points:")
                    for ph, pos in ph_positions[:10]:  # Show first 10
                        context_start = max(0, pos - 20)
                        context_end = min(len(result_with_placeholders), pos + 30)
                        context = result_with_placeholders[context_start:context_end]
                        self._write("PLACEHOLDER_POSITIONS", f"  {ph} at pos {pos}: ...{context}...")
                    if len(ph_positions) > 10:
                        self._write("PLACEHOLDER_POSITIONS", f"  ... and {len(ph_positions) - 10} more")

    def log_global_restoration(self, chunk_index: int, local_text: str, global_text: str,
                              global_indices: List[int], is_fallback: bool = False):
        """
        Log restoration of global placeholder indices (ONLY FOR FAILURES OR FALLBACK)

        Args:
            chunk_index: Index of chunk
            local_text: Text with local placeholders (0, 1, 2...)
            global_text: Text with global placeholders (restored)
            global_indices: Mapping used for restoration
            is_fallback: True if this is from a fallback scenario
        """
        # Extract local placeholders (support all formats including [idN])
        pattern_local = r'\[id(\d+)\]|\[\[(\d+)\]\]|\[(\d+)\]|/(\d+)|\$(\d+)\$'
        local_matches = re.findall(pattern_local, local_text)
        local_indices = []
        for match in local_matches:
            for group in match:
                if group:
                    local_indices.append(int(group))
                    break

        # Extract global placeholders
        global_matches = re.findall(pattern_local, global_text)
        global_indices_found = []
        for match in global_matches:
            for group in match:
                if group:
                    global_indices_found.append(int(group))
                    break

        # Only log if there's a problem OR if this is a fallback
        has_problem = (len(local_indices) != len(global_indices) or
                      len(global_indices_found) != len(global_indices))

        if not has_problem and not is_fallback:
            return  # Skip logging for successful non-fallback restorations

        self._write_separator(f"🔍 GLOBAL RESTORATION - Chunk {chunk_index}")

        self._write("EXPECTED_MAPPING", f"{global_indices}")
        self._write("LOCAL_INDICES_FOUND", f"Before restoration: {local_indices}")
        self._write("GLOBAL_INDICES_FOUND", f"After restoration: {global_indices_found}")

        # Verify mapping
        if len(local_indices) == len(global_indices):
            if len(global_indices_found) == len(global_indices):
                self._write("STATUS", "✓ Restoration successful")
            else:
                self._write("STATUS", f"⚠️ Restoration incomplete: {len(global_indices_found)}/{len(global_indices)} placeholders")
        else:
            self._write("STATUS", f"❌ COUNT MISMATCH: {len(local_indices)} local vs {len(global_indices)} expected")

    def log_tag_restoration(self, text_with_placeholders: str, restored_html: str, tag_map: Dict[str, str]):
        """
        Log tag restoration from placeholders back to HTML

        Args:
            text_with_placeholders: Text with global placeholders
            restored_html: HTML after tag restoration
            tag_map: Tag map used for restoration
        """
        self._write_separator("TAG RESTORATION")

        # Count placeholders before restoration (support all formats including [idN])
        pattern = r'\[id(\d+)\]|\[\[(\d+)\]\]|\[(\d+)\]|/(\d+)|\$(\d+)\$'
        placeholders_before = len(re.findall(pattern, text_with_placeholders))

        self._write("PLACEHOLDERS_BEFORE", f"Placeholders to restore: {placeholders_before}")
        self._write("TAG_MAP_SIZE", f"Tag map size: {len(tag_map)}")

        # Check if all placeholders were restored
        placeholders_after = len(re.findall(pattern, restored_html))

        if placeholders_after == 0:
            self._write("RESTORATION", "✓ All placeholders restored to HTML tags")
        else:
            self._write("RESTORATION", f"✗ {placeholders_after} placeholders remain in output!")

            # Show which placeholders were not restored
            remaining = re.findall(pattern, restored_html)
            self._write("UNREPLACED", f"Unreplaced placeholders: {remaining}")

        # Count tags in restored HTML
        opening_tags = re.findall(r'<(\w+)[^>]*>', restored_html)
        closing_tags = re.findall(r'</(\w+)>', restored_html)

        self._write("RESTORED_TAGS", f"Opening tags: {len(opening_tags)}, Closing tags: {len(closing_tags)}")

        # Calculate hash for comparison
        html_hash = hashlib.md5(restored_html.encode('utf-8')).hexdigest()[:8]
        self._write("HASH", f"Restored HTML hash: {html_hash}")

    def log_xml_validation(self, html: str, success: bool, errors: List[str] = None):
        """
        Log XML parsing validation results

        Args:
            html: HTML being validated
            success: Whether parsing succeeded
            errors: List of XML parsing errors
        """
        self._write_separator("XML VALIDATION")

        if success:
            self._write("STATUS", "✓ XML parsing successful")
        else:
            self._write("STATUS", "✗ XML parsing FAILED")

        if errors:
            self._write("ERROR_COUNT", f"{len(errors)} errors detected:")
            for error in errors:
                self._write("ERROR", error)

        # Try to identify specific structural issues
        opening_tags = re.findall(r'<(\w+)[^>]*>', html)
        closing_tags = re.findall(r'</(\w+)>', html)

        from collections import Counter
        opening_count = Counter(opening_tags)
        closing_count = Counter(closing_tags)

        imbalanced_tags = []
        for tag in set(opening_tags + closing_tags):
            if opening_count[tag] != closing_count[tag]:
                imbalanced_tags.append(f"{tag}: {opening_count[tag]} open, {closing_count[tag]} close")

        if imbalanced_tags:
            self._write("IMBALANCED_TAGS", "Tag balance issues:")
            for issue in imbalanced_tags:
                self._write("IMBALANCED_TAGS", f"  {issue}")

    def log_summary(self, stats: Any):
        """
        Log final summary with statistics

        Args:
            stats: TranslationStats object
        """
        self._write_separator("FINAL SUMMARY")

        self._write("STATS", f"Total chunks: {stats.total_chunks}")
        self._write("STATS", f"Success 1st try: {stats.successful_first_try} ({stats._pct(stats.successful_first_try)}%)")
        self._write("STATS", f"Success after retry: {stats.successful_after_retry} ({stats._pct(stats.successful_after_retry)}%)")
        self._write("STATS", f"Retry attempts: {stats.retry_attempts}")
        self._write("STATS", f"Fallback used: {stats.fallback_used} ({stats._pct(stats.fallback_used)}%)")

        self._write("COMPLETION", f"Log saved to: {self.log_file}")
        self._write("COMPLETION", f"Finished: {datetime.now().isoformat()}")
