"""
Abstract base class for file format adapters.

Each file format (TXT, SRT, EPUB, PDF) implements this interface to provide
format-specific translation logic while maintaining a unified API.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional

from .translation_unit import TranslationUnit


class FormatAdapter(ABC):
    """
    Abstract interface for adapting a file format to the generic translation system.

    Each format adapter is responsible for:
    1. Preparing the input file for translation
    2. Breaking it into translation units
    3. Saving translated units
    4. Reconstructing the final output file
    5. Supporting resume from checkpoint
    6. Cleaning up temporary resources

    Subclasses must implement all abstract methods.
    """

    def __init__(self, input_file_path: str, output_file_path: str, config: Dict[str, Any]):
        """
        Initialize the adapter.

        Args:
            input_file_path: Path to the input file to translate
            output_file_path: Path where the translated file should be written
            config: Format-specific configuration dictionary
        """
        self.input_file_path = Path(input_file_path)
        self.output_file_path = Path(output_file_path)
        self.config = config
        self.work_dir: Optional[Path] = None

    @abstractmethod
    async def prepare_for_translation(self) -> bool:
        """
        Prepare the file for translation.

        This method performs any necessary setup before translation can begin:
        - TXT: Read file into memory
        - SRT: Parse subtitle file
        - EPUB: Extract archive to temporary directory
        - PDF: Extract text and structure (future)

        Returns:
            True if preparation was successful, False otherwise
        """
        pass

    @abstractmethod
    def get_translation_units(self) -> List[TranslationUnit]:
        """
        Get all translation units from the prepared file.

        Returns:
            Ordered list of translation units to be processed
        """
        pass

    @abstractmethod
    async def save_unit_translation(
        self,
        unit_id: str,
        translated_content: str
    ) -> bool:
        """
        Save the translation of a single unit.

        This method is called after each unit is successfully translated.
        The adapter should store the translation in memory or write it to disk
        as appropriate for the format.

        Args:
            unit_id: Identifier of the translated unit
            translated_content: The translated text

        Returns:
            True if save was successful, False otherwise
        """
        pass

    @abstractmethod
    async def reconstruct_output(self, bilingual: bool = False) -> bytes:
        """
        Reconstruct the final output file from all translated units.

        This method is called after all units have been translated.
        It should combine all translated content into the final output format.

        Args:
            bilingual: If True, interleave original and translated content
                      for language learning or review purposes.

        Returns:
            Complete output file as bytes
        """
        pass

    @abstractmethod
    async def resume_from_checkpoint(
        self,
        checkpoint_data: Dict[str, Any]
    ) -> int:
        """
        Restore adapter state from a checkpoint.

        This method is called when resuming an interrupted translation.
        The adapter should restore any previously translated content from
        the checkpoint data.

        Args:
            checkpoint_data: Checkpoint data from the database

        Returns:
            Index of the first unit that needs to be translated (resume point)
        """
        pass

    @abstractmethod
    async def cleanup(self):
        """
        Clean up temporary resources.

        This method is called after translation is complete (or failed).
        It should remove temporary files, directories, or other resources.
        """
        pass

    @property
    @abstractmethod
    def format_name(self) -> str:
        """
        Get the format identifier.

        Returns:
            Format name (e.g., "txt", "srt", "epub", "pdf")
        """
        pass

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"input={self.input_file_path.name}, "
            f"output={self.output_file_path.name})"
        )
