"""
Protocol interfaces for EPUB translation components.

Defines formal contracts for translation pipeline components,
enabling better testability and alternative implementations.
"""

from typing import Protocol, Dict, List, Tuple
from lxml import etree


class ITagPreserver(Protocol):
    """Interface for tag preservation strategies."""

    def preserve_tags(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Replace tags with placeholders.

        Args:
            text: HTML/XML text to process

        Returns:
            Tuple of (text_with_placeholders, tag_map)
        """
        ...

    def restore_tags(self, text: str, tag_map: Dict[str, str]) -> str:
        """Restore original tags from placeholders.

        Args:
            text: Text with placeholders
            tag_map: Mapping of placeholders to tags

        Returns:
            Text with tags restored
        """
        ...


class IChunker(Protocol):
    """Interface for text chunking strategies."""

    def chunk_html_with_placeholders(
        self,
        text: str,
        tag_map: Dict[str, str]
    ) -> List[Dict]:
        """Chunk HTML text into translatable segments.

        Args:
            text: Text with placeholders
            tag_map: Global tag map

        Returns:
            List of chunk dictionaries with keys:
                - text: Chunk text with local renumbering
                - local_tag_map: Local placeholder map
                - global_offset: Offset in global map
                - global_indices: List of global indices
        """
        ...


class IValidator(Protocol):
    """Interface for placeholder validation."""

    def validate_strict(
        self,
        text: str,
        expected_tag_map: Dict[str, str]
    ) -> Tuple[bool, str]:
        """Validate placeholders with detailed error reporting.

        Args:
            text: Text to validate
            expected_tag_map: Expected placeholder map

        Returns:
            Tuple of (is_valid, error_message)
        """
        ...


class ITranslator(Protocol):
    """Interface for translation strategies."""

    async def translate_chunk(
        self,
        chunk: Dict,
        source_language: str,
        target_language: str
    ) -> str:
        """Translate a single chunk.

        Args:
            chunk: Chunk dictionary from chunker
            source_language: Source language name
            target_language: Target language name

        Returns:
            Translated text with placeholders
        """
        ...


class IContextManager(Protocol):
    """Interface for context window management."""

    def adjust_context_for_chunk(
        self,
        chunk_size: int,
        model_name: str
    ) -> int:
        """Calculate required context window size.

        Args:
            chunk_size: Size of chunk in tokens
            model_name: LLM model name

        Returns:
            Required context window size
        """
        ...
