"""
Adaptateur DOCX pour l'orchestrateur générique.

Pipeline:
- Document → HTML (mammoth)
- HTML → placeholders (TagPreserver)
- Placeholders → chunks (HtmlChunker)
- Translation chunks
- Chunks → HTML restored (TagPreserver)
- HTML → Document (python-docx)
"""

import io
from typing import Any, Callable, Dict, List, Optional, Tuple
from docx import Document

from ..common.translation_orchestrator import TranslationAdapter
from .converter import DocxHtmlConverter
from ..epub.tag_preservation import TagPreserver
from ..epub.html_chunker import HtmlChunker
from ..epub.container import TranslationContainer


class DocxTranslationAdapter(TranslationAdapter[str, bytes]):
    """
    Adaptateur pour traduire des documents DOCX.

    Note: Utilise le chemin du fichier DOCX (str) comme SourceT plutôt que
    Document directement car la conversion mammoth nécessite un chemin de fichier.
    """

    def __init__(self):
        """Initialise l'adaptateur DOCX."""
        self.converter = DocxHtmlConverter()
        self.container = TranslationContainer()
        self.tag_preserver = self.container.tag_preserver
        self.html_chunker = self.container.chunker

    def extract_content(
        self,
        source: str,
        log_callback: Optional[Callable]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Extrait le contenu HTML depuis le fichier DOCX.

        Args:
            source: Chemin vers le fichier DOCX
            log_callback: Callback de logging

        Returns:
            (html_content, context)
            - html_content: HTML extrait via mammoth
            - context: Dict avec metadata DOCX et tag preserver
        """
        # Convert DOCX → HTML
        html_content, metadata = self.converter.to_html(source)

        if log_callback:
            log_callback("extract_done", f"Extracted {len(html_content)} chars HTML from DOCX")

        context = {
            'metadata': metadata,
            'preserver': self.tag_preserver,
            'source_path': source
        }
        return html_content, context

    def preserve_structure(
        self,
        content: str,
        context: Dict[str, Any],
        log_callback: Optional[Callable]
    ) -> Tuple[str, Dict[str, str], Tuple[str, str]]:
        """
        Préserve les tags HTML via placeholders.

        Réutilise TagPreserver d'EPUB.

        Args:
            content: HTML content
            context: Context dict avec preserver
            log_callback: Callback de logging

        Returns:
            (text_with_placeholders, tag_map, placeholder_format)
        """
        preserver = context['preserver']
        text_with_placeholders, tag_map = preserver.preserve_tags(content)
        placeholder_format = (
            preserver.placeholder_format.prefix,
            preserver.placeholder_format.suffix
        )

        if log_callback:
            log_callback("tags_preserved", f"Preserved {len(tag_map)} tag groups")

        return text_with_placeholders, tag_map, placeholder_format

    def create_chunks(
        self,
        text: str,
        structure_map: Dict[str, str],
        max_tokens: int,
        log_callback: Optional[Callable]
    ) -> List[Dict]:
        """
        Découpe via HtmlChunker.

        Réutilise HtmlChunker d'EPUB.

        Args:
            text: Text with placeholders
            structure_map: Map of placeholders
            max_tokens: Max tokens per chunk
            log_callback: Callback de logging

        Returns:
            List of chunks
        """
        chunks = self.html_chunker.chunk_html_with_placeholders(
            text, structure_map
        )

        if log_callback:
            log_callback("chunks_created", f"Created {len(chunks)} chunks")

        return chunks

    def reconstruct_content(
        self,
        translated_chunks: List[str],
        structure_map: Dict[str, str],
        context: Dict[str, Any]
    ) -> str:
        """
        Reconstruit le HTML depuis les chunks traduits.

        Réutilise TagPreserver d'EPUB.

        Args:
            translated_chunks: Translated chunks
            structure_map: Map of placeholders
            context: Context dict avec preserver

        Returns:
            Reconstructed HTML
        """
        preserver = context['preserver']
        full_translated_text = ''.join(translated_chunks)
        final_html = preserver.restore_tags(full_translated_text, structure_map)
        return final_html

    def finalize_output(
        self,
        reconstructed_content: str,
        source: str,
        context: Dict[str, Any],
        log_callback: Optional[Callable]
    ) -> bytes:
        """
        Reconstruit DOCX depuis HTML traduit.

        Args:
            reconstructed_content: Reconstructed HTML content
            source: Source file path (not used, metadata from context)
            context: Context dict avec metadata
            log_callback: Callback de logging

        Returns:
            DOCX file as bytes
        """
        # Get metadata from context
        metadata = context['metadata']

        # Convert HTML → DOCX in memory
        output_buffer = io.BytesIO()

        # Create temporary file for conversion
        # (python-docx requires a file path or file object)
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode='w', suffix='.docx', delete=False, encoding='utf-8') as tmp:
            tmp_path = tmp.name

        try:
            # Convert and save to temp file
            self.converter.from_html(reconstructed_content, metadata, tmp_path)

            # Read back as bytes
            with open(tmp_path, 'rb') as f:
                docx_bytes = f.read()
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        if log_callback:
            log_callback("docx_rebuilt", f"DOCX document reconstructed ({len(docx_bytes)} bytes)")

        return docx_bytes
