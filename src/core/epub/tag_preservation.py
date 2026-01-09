"""
Tag preservation system for EPUB translation

This module handles the preservation of HTML/XML tags during translation by
replacing them with simple placeholders that LLMs won't modify.

Key features:
- Groups adjacent tags AND non-translatable content into single placeholders
- Strict validation ensures placeholder integrity post-translation
- Automatic mutation detection and correction
- Boundary tag optimization (first/last tags not sent to LLM)
"""
import re
from typing import Dict, List, Tuple


def is_non_translatable(text: str) -> bool:
    """
    Check if text contains only non-translatable content.

    Non-translatable content includes:
    - Whitespace only (spaces, tabs, newlines)
    - Non-breaking spaces and invisible Unicode characters
    - Simple numbers (digits, with optional dots/dashes for numbering)
    - Roman numerals (I, II, III, IV, etc.)

    Does NOT include:
    - Punctuation alone (could be meaningful)
    - Emojis or symbols
    - Any alphabetic text (except roman numerals)

    Args:
        text: Text to check

    Returns:
        True if text contains only non-translatable content
    """
    if not text:
        return True

    # Strip whitespace
    stripped = text.strip()
    if not stripped:
        return True  # Whitespace only

    # Check if it's just numbers/roman numerals with optional formatting
    # Matches: "1", "1.", "1.2", "42", "III", "IV.", "1-", "1)", "(1)"
    # Also matches invisible Unicode characters
    non_translatable_pattern = r'^[\d\.\-\–\—\)\(\s\u00A0\u2000-\u200F\u2028\u2029IVXLCDM]+$'
    return bool(re.match(non_translatable_pattern, stripped, re.IGNORECASE))

from src.config import (
    PLACEHOLDER_PREFIX_SAFE,
    PLACEHOLDER_SUFFIX_SAFE,
    PLACEHOLDER_PATTERN_SAFE,
    PLACEHOLDER_PREFIX_SIMPLE,
    PLACEHOLDER_SUFFIX_SIMPLE,
    PLACEHOLDER_PATTERN_SIMPLE,
    create_placeholder,
    get_mutation_variants,
    detect_placeholder_mode,
)


class TagPreserver:
    """
    Preserves HTML/XML tags during translation by replacing them with simple placeholders

    The TagPreserver converts tags like <p><span>text</span></p> into placeholders
    before translation, then restores them afterward. Adjacent tags are grouped
    into single placeholders to reduce token usage and LLM confusion.

    Adaptive placeholder format (automatic detection):
        - Uses [0], [1], [2] when text has no brackets (simplified, saves ~50% tokens)
        - Uses [[0]], [[1]], [[2]] when text contains [ or ] (safe mode)
        - Automatically detects the best format for each text by analyzing content

    Boundary tag optimization:
        The first and last placeholders (boundary tags) are always present in HTML
        content and are stored separately. They are NOT sent to the LLM, reducing
        token usage and potential confusion. They are automatically restored after
        translation.

    Example:
        Input:  <p class="body"><span>Hello world</span></p>
        With boundary optimization (text has no brackets):
            Text sent to LLM: "Hello world" (no placeholders!)
            Boundary tags stored: prefix='<p class="body"><span>', suffix='</span></p>'
            Format used: [N] (simplified)
        Without boundary optimization:
            Text sent to LLM: "[0]Hello world[1]" (simplified format saves tokens)
    """

    def __init__(self):
        self.tag_map: Dict[str, str] = {}
        self.counter: int = 0
        # These will be set by detect_placeholder_mode() during preserve_tags()
        self.placeholder_prefix: str = PLACEHOLDER_PREFIX_SAFE
        self.placeholder_suffix: str = PLACEHOLDER_SUFFIX_SAFE
        self.placeholder_pattern: str = PLACEHOLDER_PATTERN_SAFE
        self.use_simple_format: bool = False  # Track which format is being used
        # Boundary tags (first and last) - stored separately, not sent to LLM
        self.boundary_prefix: str = ""
        self.boundary_suffix: str = ""

    def preserve_tags(self, text: str, strip_boundaries: bool = True) -> Tuple[str, Dict[str, str]]:
        """
        Replace HTML/XML tags with grouped placeholders.

        Tags and non-translatable content (whitespace, numbers) are merged into
        single placeholders to reduce the number of placeholders the LLM needs
        to preserve.

        Boundary optimization (strip_boundaries=True):
            The first and last tag groups are stored separately and NOT included
            in the returned text. This reduces tokens sent to the LLM since these
            boundary tags are always present in HTML content.

        Args:
            text: Text containing HTML/XML tags
            strip_boundaries: If True, remove first and last placeholders from text
                            and store them as boundary_prefix/boundary_suffix

        Returns:
            Tuple of (processed_text, tag_map)
            Note: tag_map includes ALL tags (including boundaries) for restoration

        Example with strip_boundaries=True:
            >>> preserver = TagPreserver()
            >>> text, tag_map = preserver.preserve_tags("<p><span>Hello</span></p>")
            >>> text
            'Hello'
            >>> preserver.boundary_prefix
            '<p><span>'
            >>> preserver.boundary_suffix
            '</span></p>'

        Example with strip_boundaries=False:
            >>> preserver = TagPreserver()
            >>> text, tag_map = preserver.preserve_tags("<p><span>Hello</span></p>", strip_boundaries=False)
            >>> text
            '[[0]]Hello[[1]]'

        Example with non-translatable content grouping:
            >>> preserver = TagPreserver()
            >>> text, tag_map = preserver.preserve_tags("<p> </p><p>1.</p><p>Hello</p>", strip_boundaries=False)
            >>> text
            '[[0]]Hello[[1]]'
            # [[0]] contains "<p> </p><p>1.</p><p>" (empty paragraphs + chapter number grouped)
        """
        # Reset for new text
        self.tag_map = {}
        self.counter = 0
        self.boundary_prefix = ""
        self.boundary_suffix = ""

        # Auto-detect placeholder format based on text content
        # This removes HTML tags first to check only the actual text content
        text_without_tags = re.sub(r'<[^>]+>', '', text)
        self.placeholder_prefix, self.placeholder_suffix, self.placeholder_pattern = \
            detect_placeholder_mode(text_without_tags)
        self.use_simple_format = (self.placeholder_prefix == PLACEHOLDER_PREFIX_SIMPLE)

        # Split text into segments: tags vs non-tags
        # This preserves the order and allows us to analyze each segment
        segments = re.split(r'(<[^>]+>)', text)

        # Build output by grouping tags and non-translatable content
        merged_segments = []
        current_group = []

        for segment in segments:
            if not segment:
                continue

            is_tag = segment.startswith('<') and segment.endswith('>')
            is_non_trans = is_non_translatable(segment)

            if is_tag or is_non_trans:
                # Add to current group (tags and non-translatable content)
                current_group.append(segment)
            else:
                # Found translatable text - flush the group as a placeholder
                if current_group:
                    merged_content = ''.join(current_group)
                    placeholder = f"{self.placeholder_prefix}{self.counter}{self.placeholder_suffix}"
                    self.tag_map[placeholder] = merged_content
                    merged_segments.append(placeholder)
                    self.counter += 1
                    current_group = []
                # Add the translatable text directly
                merged_segments.append(segment)

        # Flush remaining group at the end
        if current_group:
            merged_content = ''.join(current_group)
            placeholder = f"{self.placeholder_prefix}{self.counter}{self.placeholder_suffix}"
            self.tag_map[placeholder] = merged_content
            merged_segments.append(placeholder)
            self.counter += 1

        processed_text = ''.join(merged_segments)

        # If strip_boundaries is enabled and we have at least 2 placeholders,
        # extract the first and last as boundary tags
        if strip_boundaries and self.counter >= 2:
            first_placeholder = f"{self.placeholder_prefix}0{self.placeholder_suffix}"
            last_placeholder = f"{self.placeholder_prefix}{self.counter - 1}{self.placeholder_suffix}"

            # Check if text starts with first placeholder and ends with last
            if processed_text.startswith(first_placeholder) and processed_text.endswith(last_placeholder):
                # Store boundary tags
                self.boundary_prefix = self.tag_map[first_placeholder]
                self.boundary_suffix = self.tag_map[last_placeholder]

                # Remove boundary placeholders from text
                processed_text = processed_text[len(first_placeholder):]
                processed_text = processed_text[:-len(last_placeholder)]

                # Renumber remaining placeholders (shift by -1)
                if self.counter > 2:
                    # We need to renumber [[1]] -> [[0]], [[2]] -> [[1]], etc.
                    new_tag_map = {}
                    for i in range(1, self.counter - 1):
                        old_placeholder = f"{self.placeholder_prefix}{i}{self.placeholder_suffix}"
                        new_placeholder = f"{self.placeholder_prefix}{i - 1}{self.placeholder_suffix}"
                        new_tag_map[new_placeholder] = self.tag_map[old_placeholder]
                        processed_text = processed_text.replace(old_placeholder, new_placeholder)

                    # Keep boundary tags in tag_map for reference but with special keys
                    new_tag_map["__boundary_prefix__"] = self.boundary_prefix
                    new_tag_map["__boundary_suffix__"] = self.boundary_suffix
                    self.tag_map = new_tag_map
                else:
                    # Only 2 placeholders (boundaries only, no internal tags)
                    self.tag_map = {
                        "__boundary_prefix__": self.boundary_prefix,
                        "__boundary_suffix__": self.boundary_suffix
                    }

        return processed_text, self.tag_map.copy()

    def restore_tags(self, text: str, tag_map: Dict[str, str], include_boundaries: bool = True) -> str:
        """
        Restore HTML/XML tags from placeholders

        Args:
            text: Text with placeholders
            tag_map: Dictionary mapping placeholders to original tags
            include_boundaries: If True, also restore boundary_prefix and boundary_suffix
                              stored in the TagPreserver instance

        Returns:
            Text with restored tags

        Example without boundaries:
            >>> preserver = TagPreserver()
            >>> tag_map = {'[[0]]': '<p><span>', '[[1]]': '</span></p>'}
            >>> preserver.restore_tags('[[0]]Hello[[1]]', tag_map)
            '<p><span>Hello</span></p>'

        Example with boundaries:
            >>> preserver = TagPreserver()
            >>> preserver.boundary_prefix = '<p><span>'
            >>> preserver.boundary_suffix = '</span></p>'
            >>> preserver.restore_tags('Hello', {})
            '<p><span>Hello</span></p>'
        """
        restored_text = text

        # Detect placeholder format from tag_map keys (not from instance variables!)
        # This ensures we use the correct format even if the instance was reused
        detected_prefix = self.placeholder_prefix
        detected_suffix = self.placeholder_suffix

        # Find first non-boundary placeholder in tag_map to detect format
        for key in tag_map.keys():
            if not key.startswith("__"):
                # Detect format from this key
                if key.startswith("[[") and key.endswith("]]"):
                    detected_prefix = "[["
                    detected_suffix = "]]"
                elif key.startswith("[") and key.endswith("]"):
                    detected_prefix = "["
                    detected_suffix = "]"
                break

        # Sort placeholders by number in reverse order to avoid partial replacements
        # e.g., replace [[10]] before [[1]]
        def get_placeholder_num(placeholder: str) -> int:
            # Skip special boundary keys
            if placeholder.startswith("__"):
                return -1
            try:
                return int(placeholder[len(detected_prefix):-len(detected_suffix)])
            except (ValueError, IndexError):
                return 0

        # Filter out special boundary keys from tag_map
        regular_placeholders = [k for k in tag_map.keys() if not k.startswith("__")]

        placeholders = sorted(
            regular_placeholders,
            key=get_placeholder_num,
            reverse=True
        )

        for placeholder in placeholders:
            if placeholder in restored_text:
                restored_text = restored_text.replace(placeholder, tag_map[placeholder])

        # Restore boundary tags if enabled
        if include_boundaries:
            # Try to get boundaries from tag_map first (for chunks that received tag_map with boundaries)
            prefix = tag_map.get("__boundary_prefix__", "") or self.boundary_prefix
            suffix = tag_map.get("__boundary_suffix__", "") or self.boundary_suffix

            if prefix or suffix:
                restored_text = prefix + restored_text + suffix

        return restored_text

    def validate_placeholders(self, text: str, tag_map: Dict[str, str]) -> Tuple[bool, List[str], List[Tuple[str, str]]]:
        """
        Validate that all expected placeholders are present in the text

        This function checks if the LLM preserved all placeholders during translation
        and detects common mutations (like [0] instead of [[0]]).

        Args:
            text: Text to validate
            tag_map: Dictionary mapping placeholders to original tags

        Returns:
            Tuple of (is_valid, missing_placeholders, mutated_placeholders)
            - is_valid: True if all placeholders present and unmutated
            - missing_placeholders: List of missing placeholder strings
            - mutated_placeholders: List of (original, mutated) tuples
        """
        missing_placeholders = []
        mutated_placeholders = []

        for placeholder in tag_map.keys():
            # Skip special boundary keys - they are not in the text
            if placeholder.startswith("__"):
                continue

            # For simple format [N], use regex to avoid false positives with [[N]]
            # For safe format [[N]], simple substring matching works fine
            if self.use_simple_format:
                # Build pattern for this specific placeholder: (?<!\[)\[0\](?!\])
                num = placeholder[len(self.placeholder_prefix):-len(self.placeholder_suffix)]
                specific_pattern = rf'(?<!\[)\[{re.escape(num)}\](?!\])'
                placeholder_found = bool(re.search(specific_pattern, text))
            else:
                # Safe format - simple substring match works
                placeholder_found = placeholder in text

            if not placeholder_found:
                missing_placeholders.append(placeholder)

                # Check for common mutations
                # Extract tag number from placeholder like [[0]] or [0]
                tag_num_str = placeholder[len(self.placeholder_prefix):-len(self.placeholder_suffix)]

                # Check various mutation patterns using centralized function
                # Pass simple format flag to avoid treating the opposite format as a mutation
                mutations = get_mutation_variants(tag_num_str, self.use_simple_format)

                for mutation in mutations:
                    if mutation in text:
                        mutated_placeholders.append((placeholder, mutation))
                        break

        is_valid = len(missing_placeholders) == 0 and len(mutated_placeholders) == 0
        return is_valid, missing_placeholders, mutated_placeholders

    def validate_placeholders_strict(
        self,
        translated_text: str,
        tag_map: Dict[str, str]
    ) -> Tuple[bool, str]:
        """
        Strict validation of placeholders post-translation.

        Validates:
        1. Correct number of placeholders
        2. Placeholders appear in sequential order (0, 1, 2, ...)

        Args:
            translated_text: Text with placeholders after translation
            tag_map: Dictionary mapping placeholders to original tags

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if validation passes
            - error_message: Description of the validation failure (empty if valid)
        """
        # Count only regular placeholders (not boundary keys)
        expected_count = len([k for k in tag_map.keys() if not k.startswith("__")])

        if expected_count == 0:
            return True, ""

        # Extract placeholder numbers in order of appearance
        # Pattern adapts based on format: [[0]], [[1]] (safe) or [0], [1] (simple)
        if self.use_simple_format:
            # Use negative lookahead/behind to avoid matching [[0]] when looking for [0]
            pattern = r'(?<!\[)\[(\d+)\](?!\])'
        else:
            pattern = r'\[\[(\d+)\]\]'
        found_numbers = re.findall(pattern, translated_text)

        # Verification 1: Correct count
        if len(found_numbers) != expected_count:
            return False, f"Expected {expected_count} placeholders, found {len(found_numbers)}"

        # Verification 2: Sequential order (0, 1, 2, ...)
        expected_order = [str(i) for i in range(expected_count)]
        if found_numbers != expected_order:
            return False, f"Wrong order. Expected {expected_order}, found {found_numbers}"

        return True, ""

    def fix_mutated_placeholders(self, text: str, mutated_placeholders: List[Tuple[str, str]]) -> str:
        """
        Attempt to fix common placeholder mutations

        Args:
            text: Text with mutated placeholders
            mutated_placeholders: List of (original, mutated) placeholder pairs

        Returns:
            Text with fixed placeholders
        """
        fixed_text = text
        for original, mutated in mutated_placeholders:
            fixed_text = fixed_text.replace(mutated, original)
        return fixed_text

    def try_fix_all_mutations(self, text: str, tag_map: Dict[str, str]) -> str:
        """
        Try to fix all possible mutations in the text.

        Scans the text for any mutation variants and replaces them
        with the correct placeholder format.

        Args:
            text: Text potentially containing mutated placeholders
            tag_map: Dictionary mapping placeholders to original tags

        Returns:
            Text with mutations fixed where possible
        """
        fixed_text = text

        for placeholder in tag_map.keys():
            # Skip special boundary keys
            if placeholder.startswith("__"):
                continue

            if placeholder in fixed_text:
                continue  # Already correct

            # Extract tag number
            tag_num_str = placeholder[len(self.placeholder_prefix):-len(self.placeholder_suffix)]

            # Try each mutation variant (with format awareness)
            for mutation in get_mutation_variants(tag_num_str, self.use_simple_format):
                if mutation in fixed_text:
                    fixed_text = fixed_text.replace(mutation, placeholder)
                    break

        return fixed_text
