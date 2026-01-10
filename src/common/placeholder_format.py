"""
Centralized placeholder format detection and manipulation.

This module provides a unified interface for working with placeholders,
eliminating duplication across the codebase.
"""
import re
from typing import Optional, Tuple

from src.config import (
    PLACEHOLDER_PREFIX,
    PLACEHOLDER_SUFFIX,
    PLACEHOLDER_PATTERN,
)


class PlaceholderFormat:
    """
    Encapsulates placeholder format detection and manipulation.

    This class centralizes all placeholder-related operations:
    - Format detection from text or config
    - Placeholder creation
    - Index extraction from placeholders
    - Pattern matching

    Example:
        >>> fmt = PlaceholderFormat.from_text("[id0]Hello[id1]")
        >>> fmt.create(5)
        '[id5]'
        >>> fmt.parse('[id42]')
        42
        >>> fmt.matches('[id99]')
        True
    """

    def __init__(self, prefix: str, suffix: str, pattern: str):
        """
        Initialize placeholder format.

        Args:
            prefix: Placeholder prefix (e.g., "[id")
            suffix: Placeholder suffix (e.g., "]")
            pattern: Regex pattern (e.g., r'\[id(\d+)\]')
        """
        self.prefix = prefix
        self.suffix = suffix
        self.pattern = pattern
        self._compiled_pattern = re.compile(pattern)

    @classmethod
    def from_config(cls) -> 'PlaceholderFormat':
        """
        Create PlaceholderFormat from global config constants.

        Returns:
            PlaceholderFormat instance with default format [idN]

        Example:
            >>> fmt = PlaceholderFormat.from_config()
            >>> fmt.prefix
            '[id'
        """
        return cls(PLACEHOLDER_PREFIX, PLACEHOLDER_SUFFIX, PLACEHOLDER_PATTERN)

    @classmethod
    def from_text(cls, text: str) -> 'PlaceholderFormat':
        """
        Detect placeholder format from existing text.

        Currently always returns the unified format [idN], but this method
        is kept for backward compatibility and future extensibility.

        Args:
            text: Text containing placeholders (unused, kept for compatibility)

        Returns:
            PlaceholderFormat instance with detected format

        Example:
            >>> fmt = PlaceholderFormat.from_text("[id0]Hello[id1]")
            >>> fmt.create(2)
            '[id2]'
        """
        # For now, always return unified format
        # In the future, this could detect legacy formats if needed
        return cls.from_config()

    @classmethod
    def from_tag_map(cls, tag_map: dict) -> 'PlaceholderFormat':
        """
        Detect placeholder format from a tag map.

        Args:
            tag_map: Dictionary with placeholder keys (e.g., {"[id0]": "<p>"})

        Returns:
            PlaceholderFormat instance

        Example:
            >>> tag_map = {"[id0]": "<p>", "[id1]": "</p>"}
            >>> fmt = PlaceholderFormat.from_tag_map(tag_map)
            >>> fmt.prefix
            '[id'
        """
        if not tag_map:
            return cls.from_config()

        # Get first placeholder as sample
        sample = next(iter(tag_map.keys()))
        return cls.from_text(sample)

    def create(self, index: int) -> str:
        """
        Create a placeholder for the given index.

        Args:
            index: Placeholder index (e.g., 0, 1, 2, ...)

        Returns:
            Placeholder string

        Example:
            >>> fmt = PlaceholderFormat.from_config()
            >>> fmt.create(42)
            '[id42]'
        """
        return f"{self.prefix}{index}{self.suffix}"

    def parse(self, placeholder: str) -> Optional[int]:
        """
        Extract index from a placeholder string.

        Args:
            placeholder: Placeholder string (e.g., "[id42]")

        Returns:
            Index as integer, or None if invalid

        Example:
            >>> fmt = PlaceholderFormat.from_config()
            >>> fmt.parse('[id42]')
            42
            >>> fmt.parse('invalid')
            None
        """
        match = self._compiled_pattern.match(placeholder)
        if match:
            return int(match.group(1))
        return None

    def matches(self, text: str) -> bool:
        """
        Check if text matches the placeholder pattern.

        Args:
            text: Text to check

        Returns:
            True if text is a valid placeholder

        Example:
            >>> fmt = PlaceholderFormat.from_config()
            >>> fmt.matches('[id42]')
            True
            >>> fmt.matches('not a placeholder')
            False
        """
        return bool(self._compiled_pattern.match(text))

    def find_all(self, text: str) -> list:
        """
        Find all placeholders in text.

        Args:
            text: Text to search

        Returns:
            List of (start_pos, end_pos, placeholder_text, index) tuples

        Example:
            >>> fmt = PlaceholderFormat.from_config()
            >>> fmt.find_all("[id0]Hello[id1]")
            [(0, 5, '[id0]', 0), (10, 15, '[id1]', 1)]
        """
        results = []
        for match in self._compiled_pattern.finditer(text):
            results.append((
                match.start(),
                match.end(),
                match.group(0),
                int(match.group(1))
            ))
        return results

    def remove_all(self, text: str) -> str:
        """
        Remove all placeholders from text.

        Args:
            text: Text containing placeholders

        Returns:
            Text with placeholders removed

        Example:
            >>> fmt = PlaceholderFormat.from_config()
            >>> fmt.remove_all("[id0]Hello[id1] world[id2]")
            'Hello world'
        """
        return self._compiled_pattern.sub('', text)

    def get_max_index(self, text: str) -> Optional[int]:
        """
        Find the highest placeholder index in text.

        Args:
            text: Text containing placeholders

        Returns:
            Maximum index found, or None if no placeholders

        Example:
            >>> fmt = PlaceholderFormat.from_config()
            >>> fmt.get_max_index("[id0]Hello[id5]world[id2]")
            5
        """
        placeholders = self.find_all(text)
        if not placeholders:
            return None
        return max(idx for _, _, _, idx in placeholders)

    def renumber(self, text: str, offset: int = 0) -> Tuple[str, dict]:
        """
        Renumber all placeholders sequentially starting from offset.

        Args:
            text: Text with placeholders
            offset: Starting index (default: 0)

        Returns:
            Tuple of (renumbered_text, mapping_dict)
            mapping_dict maps old_placeholder -> new_placeholder

        Example:
            >>> fmt = PlaceholderFormat.from_config()
            >>> text, mapping = fmt.renumber("[id5]Hello[id2]world[id8]", offset=0)
            >>> text
            '[id0]Hello[id1]world[id2]'
            >>> mapping
            {'[id5]': '[id0]', '[id2]': '[id1]', '[id8]': '[id2]'}
        """
        placeholders = self.find_all(text)

        # Build renumbering map (preserving order of appearance)
        mapping = {}
        seen = set()
        new_index = offset

        for _, _, placeholder, _ in placeholders:
            if placeholder not in seen:
                mapping[placeholder] = self.create(new_index)
                seen.add(placeholder)
                new_index += 1

        # Apply renumbering in reverse order to avoid conflicts
        # (e.g., [id10] -> [id1]0 if we replace [id1] first)
        result = text
        for old_placeholder in sorted(mapping.keys(),
                                      key=lambda p: self.parse(p) or 0,
                                      reverse=True):
            result = result.replace(old_placeholder, mapping[old_placeholder])

        return result, mapping

    def as_tuple(self) -> Tuple[str, str, str]:
        """
        Return format as (prefix, suffix, pattern) tuple.

        Useful for backward compatibility with code expecting tuples.

        Returns:
            Tuple of (prefix, suffix, pattern)

        Example:
            >>> fmt = PlaceholderFormat.from_config()
            >>> fmt.as_tuple()
            ('[id', ']', r'\\[id(\\d+)\\]')
        """
        return (self.prefix, self.suffix, self.pattern)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"PlaceholderFormat(prefix={self.prefix!r}, suffix={self.suffix!r})"

    def __eq__(self, other) -> bool:
        """Equality comparison."""
        if not isinstance(other, PlaceholderFormat):
            return False
        return (self.prefix == other.prefix and
                self.suffix == other.suffix and
                self.pattern == other.pattern)
