"""
DOCX ↔ HTML conversion for translation.

Uses:
- mammoth: Conversion DOCX → HTML (semantic, clean)
- python-docx: Metadata extraction + DOCX reconstruction
"""

import io
import mammoth
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from typing import Tuple, Dict, Any, Optional
from lxml import etree


class DocxHtmlConverter:
    """Converts DOCX to/from HTML for translation."""

    def to_html(self, docx_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Convert DOCX → HTML + metadata.

        Process:
        1. Use mammoth for clean HTML conversion
        2. Extract metadata with python-docx (styles, fonts, etc.)
        3. Return HTML + metadata dict

        Args:
            docx_path: Path to input DOCX file

        Returns:
            (html_content, metadata)
            - html_content: Semantic HTML (<p>, <strong>, <em>, etc.)
            - metadata: Dict with styles, fonts, page settings
        """
        # 1. Conversion via mammoth (clean semantic HTML)
        with open(docx_path, 'rb') as docx_file:
            result = mammoth.convert_to_html(docx_file)
            html_content = result.value

            # Log warnings if any
            if result.messages:
                warnings = [msg.message for msg in result.messages]
                # Store warnings in metadata for potential debugging

        # 2. Extract metadata via python-docx
        doc = Document(docx_path)
        metadata = self._extract_metadata(doc)

        return html_content, metadata

    def from_html(
        self,
        html_content: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Reconstruct DOCX from translated HTML + metadata.

        Process:
        1. Parse HTML with lxml
        2. Create empty Document() with python-docx
        3. For each HTML element, create DOCX paragraph/run
        4. Apply styles from metadata
        5. Save DOCX

        Args:
            html_content: Translated HTML content
            metadata: Original document metadata (styles, fonts, etc.)
            output_path: Path to output DOCX file
        """
        # Parse HTML
        html_tree = etree.HTML(html_content)

        # Create DOCX document
        doc = Document()

        # Apply page metadata (page size, margins, etc.)
        self._apply_page_metadata(doc, metadata)

        # Convert HTML → DOCX paragraphs
        if html_tree is not None:
            body = html_tree.find('.//body')
            if body is not None:
                for element in body:
                    self._convert_html_element_to_docx(doc, element, metadata)

        # Save
        doc.save(output_path)

    def _extract_metadata(self, doc: Document) -> Dict[str, Any]:
        """
        Extract styles, fonts, page settings from DOCX.

        Args:
            doc: python-docx Document instance

        Returns:
            Dict with document metadata
        """
        metadata = {
            'styles': {},
            'default_font': None,
            'page_size': None,
            'margins': None,
        }

        # Extract page settings from first section
        if doc.sections:
            section = doc.sections[0]
            metadata['page_size'] = {
                'width': section.page_width.inches if section.page_width else None,
                'height': section.page_height.inches if section.page_height else None
            }
            metadata['margins'] = {
                'top': section.top_margin.inches if section.top_margin else None,
                'bottom': section.bottom_margin.inches if section.bottom_margin else None,
                'left': section.left_margin.inches if section.left_margin else None,
                'right': section.right_margin.inches if section.right_margin else None
            }

        # Extract default font if available
        # Note: python-docx doesn't provide easy access to default font,
        # so we'll use a common default
        metadata['default_font'] = {
            'name': 'Calibri',
            'size': 11
        }

        return metadata

    def _apply_page_metadata(self, doc: Document, metadata: Dict[str, Any]) -> None:
        """
        Apply page settings to document.

        Args:
            doc: python-docx Document instance
            metadata: Document metadata
        """
        if not doc.sections:
            return

        section = doc.sections[0]

        # Apply page size
        page_size = metadata.get('page_size', {})
        if page_size.get('width') is not None:
            section.page_width = Inches(page_size['width'])
        if page_size.get('height') is not None:
            section.page_height = Inches(page_size['height'])

        # Apply margins
        margins = metadata.get('margins', {})
        if margins.get('top') is not None:
            section.top_margin = Inches(margins['top'])
        if margins.get('bottom') is not None:
            section.bottom_margin = Inches(margins['bottom'])
        if margins.get('left') is not None:
            section.left_margin = Inches(margins['left'])
        if margins.get('right') is not None:
            section.right_margin = Inches(margins['right'])

    def _convert_html_element_to_docx(
        self,
        doc: Document,
        element: etree._Element,
        metadata: Dict[str, Any]
    ):
        """
        Convert an HTML element to appropriate DOCX element.

        Args:
            doc: python-docx Document instance
            element: lxml HTML element
            metadata: Document metadata for styling
        """
        tag = element.tag

        if tag == 'p':
            self._convert_paragraph(doc, element, metadata)
        elif tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            self._convert_heading(doc, element, tag, metadata)
        elif tag in ['ul', 'ol']:
            self._convert_list(doc, element, metadata)
        elif tag == 'table':
            self._convert_table(doc, element, metadata)
        elif tag == 'br':
            doc.add_paragraph()  # Empty paragraph for line break
        # Skip other tags (div, span handled within paragraphs)

    def _convert_paragraph(
        self,
        doc: Document,
        element: etree._Element,
        metadata: Dict[str, Any]
    ):
        """Convert HTML <p> to DOCX paragraph."""
        p = doc.add_paragraph()
        self._add_runs_from_element(p, element, metadata)

    def _convert_heading(
        self,
        doc: Document,
        element: etree._Element,
        tag: str,
        metadata: Dict[str, Any]
    ):
        """Convert HTML heading to DOCX heading."""
        level = int(tag[1])  # h1 → 1, h2 → 2, etc.
        text = self._get_text_content(element)
        doc.add_heading(text, level=level)

    def _convert_list(
        self,
        doc: Document,
        element: etree._Element,
        metadata: Dict[str, Any]
    ):
        """Convert HTML list to DOCX list."""
        is_ordered = element.tag == 'ol'

        for li in element.findall('.//li'):
            text = self._get_text_content(li)
            p = doc.add_paragraph(text, style='List Number' if is_ordered else 'List Bullet')

    def _convert_table(
        self,
        doc: Document,
        element: etree._Element,
        metadata: Dict[str, Any]
    ):
        """Convert HTML table to DOCX table."""
        rows = element.findall('.//tr')
        if not rows:
            return

        # Count columns from first row
        first_row = rows[0]
        cols = len(first_row.findall('.//td')) + len(first_row.findall('.//th'))

        if cols == 0:
            return

        # Create table
        table = doc.add_table(rows=len(rows), cols=cols)
        table.style = 'Table Grid'

        # Fill cells
        for row_idx, tr in enumerate(rows):
            cells = tr.findall('.//td') + tr.findall('.//th')
            for col_idx, cell in enumerate(cells):
                if col_idx < cols:
                    text = self._get_text_content(cell)
                    table.rows[row_idx].cells[col_idx].text = text

    def _add_runs_from_element(
        self,
        paragraph,
        element: etree._Element,
        metadata: Dict[str, Any]
    ):
        """
        Add runs to paragraph from HTML element, preserving inline formatting.

        Handles <strong>, <em>, <b>, <i>, etc.
        """
        # Handle direct text
        if element.text:
            paragraph.add_run(element.text)

        # Handle child elements
        for child in element:
            if child.tag == 'strong' or child.tag == 'b':
                text = self._get_text_content(child)
                run = paragraph.add_run(text)
                run.bold = True
            elif child.tag == 'em' or child.tag == 'i':
                text = self._get_text_content(child)
                run = paragraph.add_run(text)
                run.italic = True
            elif child.tag == 'u':
                text = self._get_text_content(child)
                run = paragraph.add_run(text)
                run.underline = True
            else:
                # For other tags, just extract text
                text = self._get_text_content(child)
                paragraph.add_run(text)

            # Handle tail text (text after closing tag)
            if child.tail:
                paragraph.add_run(child.tail)

    def _get_text_content(self, element: etree._Element) -> str:
        """Extract all text content from an element and its children."""
        return ''.join(element.itertext())
