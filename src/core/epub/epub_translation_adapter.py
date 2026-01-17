"""
Adaptateur EPUB pour l'orchestrateur générique.

Migre le code existant de xhtml_translator.py vers le nouveau pattern.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple
from lxml import etree

from ..common.translation_orchestrator import TranslationAdapter
from .body_serializer import extract_body_html, replace_body_content
from .container import TranslationContainer
from .exceptions import XmlParsingError, BodyExtractionError


class EpubTranslationAdapter(TranslationAdapter[etree._Element, bool]):
    """
    Adaptateur pour traduire des documents XHTML/EPUB.

    Réutilise tous les modules EPUB existants via le nouveau pattern.
    """

    def __init__(self, container: Optional[TranslationContainer] = None):
        """
        Initialise l'adaptateur EPUB.

        Args:
            container: Container avec composants réutilisables
        """
        self.container = container or TranslationContainer()
        self.tag_preserver = self.container.tag_preserver
        self.html_chunker = self.container.chunker

    def extract_content(
        self,
        source: etree._Element,
        log_callback: Optional[Callable]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Extrait le body HTML depuis l'ElementTree.

        Args:
            source: etree._Element root
            log_callback: Callback de logging

        Returns:
            (body_html, context)
            - body_html: HTML content from body
            - context: Dict avec body_element et preserver
        """
        body_html, body_element = extract_body_html(source)

        if log_callback:
            log_callback("body_extracted", f"Extracted {len(body_html)} chars from XHTML body")

        context = {
            'body_element': body_element,
            'preserver': self.tag_preserver,
            'doc_root': source
        }
        return body_html, context

    def preserve_structure(
        self,
        content: str,
        context: Dict[str, Any],
        log_callback: Optional[Callable]
    ) -> Tuple[str, Dict[str, str], Tuple[str, str]]:
        """
        Préserve les tags HTML via placeholders.

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
        Reconstruit le HTML.

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
        source: etree._Element,
        context: Dict[str, Any],
        log_callback: Optional[Callable]
    ) -> bool:
        """
        Replace body content in XHTML.

        Args:
            reconstructed_content: Reconstructed HTML content
            source: Source etree._Element (not used, body_element from context)
            context: Context dict avec body_element
            log_callback: Callback de logging

        Returns:
            True if successful, False otherwise
        """
        body_element = context['body_element']

        try:
            replace_body_content(body_element, reconstructed_content)

            if log_callback:
                log_callback("body_replaced", "Body content replaced successfully")

            return True
        except (XmlParsingError, BodyExtractionError) as e:
            if log_callback:
                log_callback("replace_body_error", str(e))
            return False
