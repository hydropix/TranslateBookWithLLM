"""
XHTML Translation State Management

This module provides serializable state management for XHTML translation,
enabling interruption and resume at the chunk level.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime


@dataclass
class XHTMLTranslationState:
    """
    Serializable state for partial XHTML translation.

    This class captures the complete translation state at any point during
    XHTML processing, allowing for interruption and exact resume from the
    last translated chunk.
    """

    # Identification
    file_path: str
    translation_id: str
    file_href: str  # Relative path in EPUB (e.g., "OEBPS/chapter1.xhtml")

    # Translation Configuration
    source_language: str
    target_language: str
    model_name: str
    max_tokens_per_chunk: int
    max_retries: int

    # Chunking State
    chunks: List[Dict[str, Any]]  # Complete list of chunks
    # Each chunk contains:
    #   - text: str (with local placeholders)
    #   - local_tag_map: Dict[str, str]
    #   - global_indices: List[int]

    global_tag_map: Dict[str, str]  # Global placeholder → HTML tag mapping
    placeholder_format: Tuple[str, str]  # (prefix, suffix) e.g., ("[[", "]]")

    # Translation Progress
    translated_chunks: List[str]  # Already translated chunks (with global indices)
    current_chunk_index: int  # Next chunk to translate (0-based)

    # Original Document Metadata
    original_body_html: str  # Original body HTML (for reference)
    doc_metadata: Dict[str, Any]  # Namespaces, attributes, etc.

    # Statistics
    stats: Dict[str, Any]  # Serialized TranslationMetrics (file-local)

    # Timestamps
    created_at: str  # ISO 8601 format
    updated_at: str  # ISO 8601 format

    # Global Statistics (for EPUB with multiple XHTML files)
    global_stats: Optional[Dict[str, Any]] = None  # Global stats across all files

    # Options (with defaults - must come after non-default fields)
    prompt_options: Optional[Dict[str, Any]] = None
    bilingual: bool = False
    original_chunks: Optional[List[Dict[str, Any]]] = None  # For bilingual mode

    # Technical Content Protection (always enabled)
    protect_technical: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize state to JSON-compatible dictionary.

        Returns:
            Dictionary containing all state information
        """
        return {
            'file_path': self.file_path,
            'translation_id': self.translation_id,
            'file_href': self.file_href,
            'source_language': self.source_language,
            'target_language': self.target_language,
            'model_name': self.model_name,
            'max_tokens_per_chunk': self.max_tokens_per_chunk,
            'max_retries': self.max_retries,
            'chunks': self.chunks,
            'global_tag_map': self.global_tag_map,
            'placeholder_format': list(self.placeholder_format),  # Convert tuple to list for JSON
            'translated_chunks': self.translated_chunks,
            'current_chunk_index': self.current_chunk_index,
            'original_body_html': self.original_body_html,
            'doc_metadata': self.doc_metadata,
            'stats': self.stats,
            'prompt_options': self.prompt_options,
            'bilingual': self.bilingual,
            'original_chunks': self.original_chunks,
            'protect_technical': self.protect_technical,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'global_stats': self.global_stats,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'XHTMLTranslationState':
        """
        Deserialize state from dictionary.

        Args:
            data: Dictionary containing serialized state

        Returns:
            XHTMLTranslationState instance
        """
        return cls(
            file_path=data['file_path'],
            translation_id=data['translation_id'],
            file_href=data['file_href'],
            source_language=data['source_language'],
            target_language=data['target_language'],
            model_name=data['model_name'],
            max_tokens_per_chunk=data['max_tokens_per_chunk'],
            max_retries=data['max_retries'],
            chunks=data['chunks'],
            global_tag_map=data['global_tag_map'],
            placeholder_format=tuple(data['placeholder_format']),  # Convert list back to tuple
            translated_chunks=data['translated_chunks'],
            current_chunk_index=data['current_chunk_index'],
            original_body_html=data['original_body_html'],
            doc_metadata=data['doc_metadata'],
            stats=data['stats'],
            prompt_options=data.get('prompt_options'),
            bilingual=data.get('bilingual', False),
            original_chunks=data.get('original_chunks'),
            protect_technical=data.get('protect_technical', True),
            created_at=data['created_at'],
            updated_at=data['updated_at'],
            global_stats=data.get('global_stats'),
        )

    def validate(self) -> bool:
        """
        Validate the consistency of the state.

        Returns:
            True if state is valid, False otherwise
        """
        # Check that current_chunk_index is within bounds
        if self.current_chunk_index < 0 or self.current_chunk_index > len(self.chunks):
            return False

        # Check that translated_chunks matches current_chunk_index
        if len(self.translated_chunks) != self.current_chunk_index:
            return False

        # Check that placeholder_format is valid
        if not isinstance(self.placeholder_format, tuple) or len(self.placeholder_format) != 2:
            return False

        # Check required fields are not empty
        if not self.file_path or not self.translation_id or not self.file_href:
            return False

        # Check chunks structure
        if not isinstance(self.chunks, list):
            return False

        for chunk in self.chunks:
            if not isinstance(chunk, dict):
                return False
            if 'text' not in chunk or 'local_tag_map' not in chunk or 'global_indices' not in chunk:
                return False

        return True

    def get_progress_percentage(self) -> float:
        """
        Calculate translation progress as percentage.

        Returns:
            Progress percentage (0.0 to 100.0)
        """
        if not self.chunks:
            return 0.0
        return (self.current_chunk_index / len(self.chunks)) * 100.0

    def get_remaining_chunks(self) -> int:
        """
        Get number of remaining chunks to translate.

        Returns:
            Number of chunks remaining
        """
        return len(self.chunks) - self.current_chunk_index

    def __repr__(self) -> str:
        """String representation for debugging."""
        progress = self.get_progress_percentage()
        return (
            f"XHTMLTranslationState("
            f"file_href='{self.file_href}', "
            f"progress={progress:.1f}%, "
            f"chunks={self.current_chunk_index}/{len(self.chunks)}, "
            f"updated_at='{self.updated_at}'"
            f")"
        )
