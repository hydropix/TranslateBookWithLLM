"""
SRT Adapter for the generic translation system.
Handles SRT subtitle file format with local index renumbering.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path

from .format_adapter import FormatAdapter
from .translation_unit import TranslationUnit


class SrtAdapter(FormatAdapter):
    """Adapter for SRT (subtitle) files."""

    def __init__(self, input_file_path: str, output_file_path: str, config: Dict[str, Any]):
        super().__init__(input_file_path, output_file_path, config)
        self.subtitles: List[Dict] = []
        self.blocks: List[List[Dict]] = []
        self.translations: Dict[int, str] = {}  # global_index -> translated_text
        self.processor = None

    async def prepare_for_translation(self) -> bool:
        """Parse SRT file and group subtitles into blocks."""
        try:
            # Import here to avoid circular dependency
            from src.core.srt_processor import SRTProcessor
            self.processor = SRTProcessor()

            # Read and parse SRT
            with open(self.input_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            self.subtitles = self.processor.parse_srt(content)

            if not self.subtitles:
                return False

            # Group subtitles into blocks for translation
            lines_per_block = self.config.get('lines_per_block', 5)
            self.blocks = self.processor.group_subtitles_for_translation(
                self.subtitles,
                lines_per_block=lines_per_block
            )

            return True

        except Exception as e:
            print(f"Error preparing SRT file: {e}")
            return False

    def get_translation_units(self) -> List[TranslationUnit]:
        """Create translation units from subtitle blocks."""
        units = []

        for block_idx, block in enumerate(self.blocks):
            # Build block text with local indices
            block_text_lines = []
            local_to_global = {}

            for local_idx, subtitle in enumerate(block):
                # Find global index of this subtitle
                global_idx = self.subtitles.index(subtitle)
                local_to_global[local_idx] = global_idx
                block_text_lines.append(f"[{local_idx}]{subtitle['text']}")

            block_text = '\n'.join(block_text_lines)

            # Context from adjacent blocks
            context_before = ""
            context_after = ""

            if block_idx > 0:
                prev_block = self.blocks[block_idx - 1]
                context_before = prev_block[-1]['text']

            if block_idx < len(self.blocks) - 1:
                next_block = self.blocks[block_idx + 1]
                context_after = next_block[0]['text']

            unit = TranslationUnit(
                unit_id=f"block_{block_idx}",
                content=block_text,
                context_before=context_before,
                context_after=context_after,
                metadata={
                    'block_index': block_idx,
                    'local_to_global': local_to_global,
                    'block_subtitles': [self.subtitles.index(s) for s in block]
                }
            )
            units.append(unit)

        return units

    async def save_unit_translation(self, unit_id: str, translated_content: str) -> bool:
        """Extract translations from block and store by global index."""
        try:
            # Extract block index from unit_id
            block_idx = int(unit_id.split('_')[1])
            units = self.get_translation_units()

            if block_idx >= len(units):
                return False

            unit = units[block_idx]

            # Extract translations using remapping
            local_to_global = unit.metadata['local_to_global']
            block_translations = self.processor.extract_block_translations_with_remapping(
                translated_content,
                local_to_global
            )

            # Store translations by global index
            self.translations.update(block_translations)

            return True

        except Exception as e:
            print(f"Error saving unit translation: {e}")
            return False

    async def reconstruct_output(self) -> bytes:
        """Reconstruct SRT file with translations."""
        try:
            # Update subtitles with translations
            updated_subtitles = self.processor.update_translated_subtitles(
                self.subtitles,
                self.translations
            )

            # Reconstruct SRT format
            srt_content = self.processor.reconstruct_srt(updated_subtitles)

            return srt_content.encode('utf-8')

        except Exception as e:
            print(f"Error reconstructing SRT output: {e}")
            # Fallback: return original file
            with open(self.input_file_path, 'rb') as f:
                return f.read()

    async def resume_from_checkpoint(self, checkpoint_data: Dict[str, Any]) -> int:
        """Restore translations from checkpoint."""
        try:
            # Restore translations from completed chunks
            for chunk_data in checkpoint_data.get('chunks', []):
                if chunk_data.get('status') == 'completed':
                    metadata = chunk_data.get('chunk_data', {})
                    translated_text = chunk_data.get('translated_text', '')

                    if 'local_to_global' in metadata and translated_text:
                        # Extract translations from stored text
                        # Convert JSON string keys back to integers
                        local_to_global_raw = metadata['local_to_global']
                        local_to_global = {
                            int(k): v for k, v in local_to_global_raw.items()
                        }

                        block_translations = self.processor.extract_block_translations_with_remapping(
                            translated_text,
                            local_to_global
                        )
                        self.translations.update(block_translations)

            return checkpoint_data.get('resume_from_index', 0)

        except Exception as e:
            print(f"Error resuming from checkpoint: {e}")
            return 0

    async def cleanup(self):
        """No cleanup needed for SRT files."""
        pass

    @property
    def format_name(self) -> str:
        """Format identifier."""
        return "srt"
