"""
Translation unit abstraction.

A TranslationUnit represents a single, indivisible unit of translation work.
Different file formats define units differently:
- TXT: a text chunk (based on token count)
- SRT: a block of subtitles
- EPUB: an XHTML file
- PDF: a page or section (future)
"""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class TranslationUnit:
    """
    Represents a single unit of translation work.

    Attributes:
        unit_id: Unique identifier for this unit (e.g., "chunk_0", "block_5", "file_3")
        content: The content to be translated
        context_before: Context from before this unit (for coherence)
        context_after: Context from after this unit (for coherence)
        metadata: Format-specific metadata (e.g., chunk index, file path, subtitle timings)
    """
    unit_id: str
    content: str
    context_before: str = ""
    context_after: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize to dictionary for storage.

        Returns:
            Dictionary representation suitable for JSON/database storage
        """
        return {
            'unit_id': self.unit_id,
            'content': self.content,
            'context_before': self.context_before,
            'context_after': self.context_after,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TranslationUnit':
        """
        Deserialize from dictionary.

        Args:
            data: Dictionary containing unit data

        Returns:
            TranslationUnit instance
        """
        return cls(
            unit_id=data['unit_id'],
            content=data['content'],
            context_before=data.get('context_before', ''),
            context_after=data.get('context_after', ''),
            metadata=data.get('metadata', {})
        )

    def __repr__(self) -> str:
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"TranslationUnit(id={self.unit_id}, content='{content_preview}')"
