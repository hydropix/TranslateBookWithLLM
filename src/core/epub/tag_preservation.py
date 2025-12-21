"""
Tag preservation system for EPUB translation

This module handles the preservation of HTML/XML tags during translation by
replacing them with simple placeholders that LLMs won't modify.
"""
import re
from typing import Dict, List, Tuple

from src.config import (
    PLACEHOLDER_PREFIX,
    PLACEHOLDER_SUFFIX,
    create_placeholder,
    get_mutation_variants,
)


class TagPreserver:
    """
    Preserves HTML/XML tags during translation by replacing them with simple placeholders

    The TagPreserver converts tags like <em>text</em> into [TAG0]text[TAG1] before
    translation, then restores them afterward. This prevents LLMs from modifying
    or hallucinating HTML/XML structure.
    """

    def __init__(self):
        self.tag_map: Dict[str, str] = {}
        self.counter: int = 0
        self.placeholder_prefix: str = PLACEHOLDER_PREFIX
        self.placeholder_suffix: str = PLACEHOLDER_SUFFIX

    def preserve_tags(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Replace HTML/XML tags with simple placeholders

        Args:
            text: Text containing HTML/XML tags

        Returns:
            Tuple of (processed_text, tag_map)

        Example:
            >>> preserver = TagPreserver()
            >>> text, tag_map = preserver.preserve_tags("<em>Hello</em> world")
            >>> text
            '⟦TAG0⟧Hello⟦TAG1⟧ world'
        """
        # Reset for new text
        self.tag_map = {}
        self.counter = 0

        # Pattern to match any HTML/XML tag (opening, closing, or self-closing)
        tag_pattern = r'<[^>]+>'

        def replace_tag(match: re.Match) -> str:
            tag = match.group(0)
            # Create a simple placeholder
            placeholder = f"{self.placeholder_prefix}{self.counter}{self.placeholder_suffix}"
            self.tag_map[placeholder] = tag
            self.counter += 1
            return placeholder

        # Replace all tags with placeholders
        processed_text = re.sub(tag_pattern, replace_tag, text)

        return processed_text, self.tag_map.copy()

    def restore_tags(self, text: str, tag_map: Dict[str, str]) -> str:
        """
        Restore HTML/XML tags from placeholders

        Args:
            text: Text with placeholders
            tag_map: Dictionary mapping placeholders to original tags

        Returns:
            Text with restored tags

        Example:
            >>> preserver = TagPreserver()
            >>> tag_map = {'⟦TAG0⟧': '<em>', '⟦TAG1⟧': '</em>'}
            >>> preserver.restore_tags('⟦TAG0⟧Hello⟦TAG1⟧', tag_map)
            '<em>Hello</em>'
        """
        restored_text = text

        # Sort placeholders by reverse order to avoid partial replacements
        placeholders = sorted(
            tag_map.keys(),
            key=lambda x: int(x[len(self.placeholder_prefix):-len(self.placeholder_suffix)]),
            reverse=True
        )

        for placeholder in placeholders:
            if placeholder in restored_text:
                restored_text = restored_text.replace(placeholder, tag_map[placeholder])

        return restored_text

    def validate_placeholders(self, text: str, tag_map: Dict[str, str]) -> Tuple[bool, List[str], List[Tuple[str, str]]]:
        """
        Validate that all expected placeholders are present in the text

        This function checks if the LLM preserved all placeholders during translation
        and detects common mutations (like [[TAG0]] instead of ⟦TAG0⟧).

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
            if placeholder not in text:
                missing_placeholders.append(placeholder)

                # Check for common mutations
                # Extract tag number
                tag_num_str = placeholder[len(self.placeholder_prefix):-len(self.placeholder_suffix)]

                # Check various mutation patterns using centralized function
                mutations = get_mutation_variants(tag_num_str)

                for mutation in mutations:
                    if mutation in text:
                        mutated_placeholders.append((placeholder, mutation))
                        break

        is_valid = len(missing_placeholders) == 0 and len(mutated_placeholders) == 0
        return is_valid, missing_placeholders, mutated_placeholders

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
