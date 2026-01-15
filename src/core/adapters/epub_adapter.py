"""
EPUB format adapter for the generic translation system.

This adapter handles EPUB files by:
1. Extracting the EPUB archive to a temporary directory
2. Parsing the OPF manifest to get content files
3. Creating translation units (one per XHTML file)
4. Saving translated files through checkpoint manager
5. Reconstructing and repackaging the EPUB
6. Supporting resume from checkpoint by restoring translated files
"""

import os
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from lxml import etree

from .format_adapter import FormatAdapter
from .translation_unit import TranslationUnit
from src.config import NAMESPACES


class EpubAdapter(FormatAdapter):
    """
    Adapter for EPUB (.epub) files.

    EPUB files are complex archives containing XHTML files, metadata, and assets.
    Each XHTML content file is treated as a single translation unit.

    Key features:
    - Extracts EPUB to temporary directory
    - Preserves EPUB structure during translation
    - Saves translated files incrementally via checkpoint manager
    - Supports resume by restoring previously translated files
    """

    def __init__(self, input_file_path: str, output_file_path: str, config: Dict[str, Any]):
        """
        Initialize the EPUB adapter.

        Args:
            input_file_path: Path to input .epub file
            output_file_path: Path to output translated .epub file
            config: Configuration dict with keys:
                - checkpoint_manager: CheckpointManager instance (required for file persistence)
                - translation_id: Translation job ID (required for file persistence)
                - source_language: Source language
                - target_language: Target language
                - ... (other EPUB-specific configs)
        """
        super().__init__(input_file_path, output_file_path, config)
        self.work_dir: Optional[Path] = None
        self.opf_path: Optional[Path] = None
        self.opf_tree: Optional[etree._ElementTree] = None
        self.opf_dir: Optional[Path] = None
        self.content_files: List[str] = []
        self.checkpoint_manager = config.get('checkpoint_manager')
        self.translation_id = config.get('translation_id')

    async def prepare_for_translation(self) -> bool:
        """
        Extract EPUB and parse manifest.

        Returns:
            True if preparation was successful
        """
        try:
            # Create temporary work directory
            self.work_dir = Path(tempfile.mkdtemp(prefix='epub_translation_'))

            # Extract EPUB
            with zipfile.ZipFile(self.input_file_path, 'r') as zip_ref:
                zip_ref.extractall(self.work_dir)

            # Find OPF file
            self.opf_path = self._find_opf_file()
            if not self.opf_path:
                return False

            # Parse OPF to get content files
            self.opf_tree = etree.parse(str(self.opf_path))
            opf_root = self.opf_tree.getroot()
            self.opf_dir = self.opf_path.parent

            manifest = opf_root.find('.//opf:manifest', namespaces=NAMESPACES)
            spine = opf_root.find('.//opf:spine', namespaces=NAMESPACES)

            if manifest is None or spine is None:
                return False

            # Get content files from spine (in reading order)
            for itemref in spine.findall('.//opf:itemref', namespaces=NAMESPACES):
                idref = itemref.get('idref')
                item = manifest.find(f'.//opf:item[@id="{idref}"]', namespaces=NAMESPACES)
                if item is not None:
                    media_type = item.get('media-type')
                    href = item.get('href')
                    if media_type in ['application/xhtml+xml', 'text/html'] and href:
                        self.content_files.append(href)

            return True

        except Exception:
            return False

    def _find_opf_file(self) -> Optional[Path]:
        """
        Find the OPF file in the extracted EPUB.

        Returns:
            Path to OPF file or None if not found
        """
        for file_path in self.work_dir.rglob('*.opf'):
            return file_path
        return None

    def get_translation_units(self) -> List[TranslationUnit]:
        """
        Create translation units from EPUB content files.

        Each XHTML file becomes one translation unit.

        NOTE: For EPUB, the content field contains the file href, NOT the actual XHTML content.
        This is because EPUB translation requires complex processing (HTML chunking,
        tag preservation, etc.) that happens in translate_xhtml_simplified(), not in
        the generic translator.

        The EpubAdapter delegates to translate_epub_file() for actual translation,
        bypassing the generic translator's unit-by-unit translation logic.

        Returns:
            List of TranslationUnit objects, one per XHTML file
        """
        units = []

        for file_idx, content_href in enumerate(self.content_files):
            file_path = self.opf_dir / content_href

            if not file_path.exists():
                continue

            # Context: previous and next file names (for coherence)
            context_before = ""
            context_after = ""
            if file_idx > 0:
                context_before = f"Previous file: {self.content_files[file_idx - 1]}"
            if file_idx < len(self.content_files) - 1:
                context_after = f"Next file: {self.content_files[file_idx + 1]}"

            # The content for EPUB units is just the file href
            # Actual translation happens via translate_epub_file() called by EpubAdapter
            unit = TranslationUnit(
                unit_id=f"file_{file_idx}",
                content=content_href,  # File identifier, not actual content
                context_before=context_before,
                context_after=context_after,
                metadata={
                    'file_index': file_idx,
                    'file_href': content_href,
                    'file_path': str(file_path),
                    'total_files': len(self.content_files)
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
        Save a translated XHTML file.

        For EPUB, the translated file is already saved in work_dir by the
        orchestrator (via translate_xhtml_simplified). This method persists
        the file to checkpoint storage for resume capability.

        Args:
            unit_id: Unit identifier (e.g., "file_0")
            translated_content: File href (not actual content for EPUB)

        Returns:
            True if save was successful
        """
        # Extract file index from unit_id
        file_idx = int(unit_id.split('_')[1])
        file_href = self.content_files[file_idx]
        file_path = self.opf_dir / file_href

        if not file_path.exists():
            return False

        # Persist the translated file to checkpoint storage
        if self.checkpoint_manager and self.translation_id:
            try:
                with open(file_path, 'rb') as f:
                    file_content = f.read()

                success = self.checkpoint_manager.save_epub_file(
                    translation_id=self.translation_id,
                    file_href=file_href,
                    file_content=file_content
                )

                return success
            except Exception:
                return False
        else:
            # No checkpoint manager - just confirm file exists in work_dir
            return file_path.exists()

    async def reconstruct_output(self, bilingual: bool = False) -> bytes:
        """
        Repackage the EPUB from work_dir.

        Args:
            bilingual: If True, the XHTML files should already contain
                      bilingual content (handled during translation phase).

        Returns:
            Complete EPUB file as bytes
        """
        output_path = Path(tempfile.mktemp(suffix='.epub'))

        try:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as epub_zip:
                # Add mimetype first (uncompressed, as per EPUB spec)
                mimetype_path = self.work_dir / 'mimetype'
                if mimetype_path.exists():
                    epub_zip.write(
                        mimetype_path,
                        'mimetype',
                        compress_type=zipfile.ZIP_STORED
                    )

                # Add all other files
                for file_path in self.work_dir.rglob('*'):
                    if file_path.is_file() and file_path.name != 'mimetype':
                        arcname = file_path.relative_to(self.work_dir)
                        epub_zip.write(file_path, arcname)

            # Read as bytes
            with open(output_path, 'rb') as f:
                epub_bytes = f.read()

            return epub_bytes

        finally:
            # Clean up temporary output file
            if output_path.exists():
                output_path.unlink()

    async def resume_from_checkpoint(
        self,
        checkpoint_data: Dict[str, Any]
    ) -> int:
        """
        Restore translated XHTML files from checkpoint to work_dir.

        This is the key feature that enables EPUB resume functionality.

        Args:
            checkpoint_data: Checkpoint data from database

        Returns:
            Index of the first unit that needs to be translated (resume point)
        """
        if self.checkpoint_manager and self.translation_id and self.work_dir:
            # Restore all previously translated files to work_dir
            success = self.checkpoint_manager.restore_epub_files(
                translation_id=self.translation_id,
                work_dir=self.work_dir
            )

        # Return resume index from checkpoint
        return checkpoint_data.get('resume_from_index', 0)

    async def cleanup(self):
        """
        Remove temporary work directory.
        """
        if self.work_dir and self.work_dir.exists():
            try:
                shutil.rmtree(self.work_dir)
            except Exception:
                pass

    @property
    def format_name(self) -> str:
        """
        Get the format identifier.

        Returns:
            "epub"
        """
        return "epub"
