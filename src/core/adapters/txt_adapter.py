"""
TXT format adapter for the generic translation system.

This adapter handles plain text files by:
1. Reading the entire file into memory
2. Splitting it into token-based chunks
3. Storing translated chunks in memory
4. Reconstructing the output by joining chunks
"""

from pathlib import Path
from typing import List, Dict, Any, Optional

from .format_adapter import FormatAdapter
from .translation_unit import TranslationUnit


class TxtAdapter(FormatAdapter):
    """
    Adapter for plain text (.txt) files.

    Uses token-based chunking to split large text files into manageable units
    while preserving context between chunks for translation coherence.
    """

    def __init__(self, input_file_path: str, output_file_path: str, config: Dict[str, Any]):
        """
        Initialize the TXT adapter.

        Args:
            input_file_path: Path to input .txt file
            output_file_path: Path to output translated .txt file
            config: Configuration dict with optional keys:
                - max_tokens_per_chunk: Maximum tokens per chunk (default: from config)
                - soft_limit_ratio: Soft limit for chunk splitting (default: from config)
        """
        super().__init__(input_file_path, output_file_path, config)
        self.text: str = ""
        self.chunks: List[Dict[str, str]] = []
        self.translated_chunks: List[Optional[str]] = []

    async def prepare_for_translation(self) -> bool:
        """
        Read the text file and split it into chunks.

        Returns:
            True if file was successfully read and chunked
        """
        try:
            # Read the entire file
            with open(self.input_file_path, 'r', encoding='utf-8') as f:
                self.text = f.read()

            # Split into chunks using token chunker
            from src.core.text_processor import split_text_into_chunks

            self.chunks = split_text_into_chunks(
                text=self.text,
                max_tokens_per_chunk=self.config.get('max_tokens_per_chunk'),
                soft_limit_ratio=self.config.get('soft_limit_ratio')
            )

            # Initialize translation storage (None = not yet translated)
            self.translated_chunks = [None] * len(self.chunks)

            return True

        except Exception as e:
            print(f"Error preparing TXT file: {e}")
            return False

    def get_translation_units(self) -> List[TranslationUnit]:
        """
        Convert chunks into translation units.

        Returns:
            List of TranslationUnit objects, one per chunk
        """
        units = []

        for i, chunk in enumerate(self.chunks):
            unit = TranslationUnit(
                unit_id=f"chunk_{i}",
                content=chunk['main_content'],
                context_before=chunk.get('context_before', ''),
                context_after=chunk.get('context_after', ''),
                metadata={
                    'chunk_index': i,
                    'total_chunks': len(self.chunks)
                }
            )
            units.append(unit)

        return units

    async def save_unit_translation(
        self,
        unit_id: str,
        translated_content: str
    ) -> bool:
        """
        Save a translated chunk to memory.

        Args:
            unit_id: Unit identifier (format: "chunk_{index}")
            translated_content: The translated text

        Returns:
            True if save was successful
        """
        try:
            # Extract chunk index from unit_id
            chunk_index = int(unit_id.split('_')[1])

            if 0 <= chunk_index < len(self.translated_chunks):
                self.translated_chunks[chunk_index] = translated_content
                return True
            else:
                print(f"Invalid chunk index: {chunk_index}")
                return False

        except Exception as e:
            print(f"Error saving translated chunk: {e}")
            return False

    async def reconstruct_output(self) -> bytes:
        """
        Reconstruct the complete translated text file.

        If a chunk wasn't translated, uses the original text as fallback.

        Returns:
            Complete translated file as bytes
        """
        # Join all chunks, using original text for untranslated chunks
        text_chunks = []

        for i, translated_chunk in enumerate(self.translated_chunks):
            if translated_chunk is not None:
                text_chunks.append(translated_chunk)
            else:
                # Fallback to original content
                text_chunks.append(self.chunks[i]['main_content'])

        # Join with newlines (preserving paragraph structure)
        final_text = '\n'.join(text_chunks)

        return final_text.encode('utf-8')

    async def resume_from_checkpoint(
        self,
        checkpoint_data: Dict[str, Any]
    ) -> int:
        """
        Restore translated chunks from checkpoint data.

        Args:
            checkpoint_data: Checkpoint data containing 'chunks' list

        Returns:
            Index of the first unit that needs translation (resume point)
        """
        try:
            chunks_data = checkpoint_data.get('chunks', [])

            # Restore each completed chunk
            for chunk_data in chunks_data:
                if chunk_data.get('status') == 'completed':
                    metadata = chunk_data.get('chunk_data', {})
                    chunk_index = metadata.get('chunk_index')
                    translated_text = chunk_data.get('translated_text')

                    if chunk_index is not None and translated_text is not None:
                        if 0 <= chunk_index < len(self.translated_chunks):
                            self.translated_chunks[chunk_index] = translated_text

            # Return resume index
            return checkpoint_data.get('resume_from_index', 0)

        except Exception as e:
            print(f"Error resuming from checkpoint: {e}")
            return 0

    async def cleanup(self):
        """
        Clean up resources.

        For TXT adapter, there are no temporary resources to clean up.
        """
        # No cleanup needed for TXT files (everything is in memory)
        pass

    @property
    def format_name(self) -> str:
        """
        Get the format identifier.

        Returns:
            "txt"
        """
        return "txt"

    def __repr__(self) -> str:
        return (
            f"TxtAdapter("
            f"input={self.input_file_path.name}, "
            f"output={self.output_file_path.name}, "
            f"chunks={len(self.chunks)})"
        )
