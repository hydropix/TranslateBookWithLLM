"""
EPUB audio extraction for TTS conversion

This module handles extraction of chapter text from EPUB files for
audio conversion purposes.
"""
import os
import zipfile
import tempfile
import html
import re
import aiofiles
from typing import Dict
from lxml import etree


class EPUBProcessor:
    """Handles EPUB-specific processing for audio conversion"""

    def __init__(self):
        self.namespaces = {
            'opf': 'http://www.idpf.org/2007/opf',
            'xhtml': 'http://www.w3.org/1999/xhtml',
            'dc': 'http://purl.org/dc/elements/1.1/'
        }

    async def extract_chapters_for_audio(self, epub_path: str) -> Dict[str, str]:
        """
        Extract chapter text from EPUB for audio conversion

        Args:
            epub_path: Path to EPUB file

        Returns:
            Dictionary mapping chapter titles to text content
        """
        chapters = {}

        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract EPUB
            with zipfile.ZipFile(epub_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # Find content.opf
            opf_path = None
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith('.opf'):
                        opf_path = os.path.join(root, file)
                        break
                if opf_path:
                    break

            if not opf_path:
                raise ValueError("No OPF file found in EPUB")

            # Parse OPF to get reading order
            tree = etree.parse(opf_path)
            root = tree.getroot()

            # Get spine items (reading order)
            spine = root.find('.//{http://www.idpf.org/2007/opf}spine')
            if spine is None:
                raise ValueError("No spine found in OPF")

            # Get manifest to map IDs to files
            manifest = root.find('.//{http://www.idpf.org/2007/opf}manifest')
            if manifest is None:
                raise ValueError("No manifest found in OPF")

            # Create ID to href mapping
            id_to_href = {}
            for item in manifest.findall('.//{http://www.idpf.org/2007/opf}item'):
                item_id = item.get('id')
                href = item.get('href')
                if item_id and href:
                    id_to_href[item_id] = href

            # Process spine items in order
            opf_dir = os.path.dirname(opf_path)
            chapter_num = 0

            for itemref in spine.findall('.//{http://www.idpf.org/2007/opf}itemref'):
                idref = itemref.get('idref')
                if idref and idref in id_to_href:
                    href = id_to_href[idref]
                    content_path = os.path.join(opf_dir, href)

                    if os.path.exists(content_path):
                        # Extract text from HTML/XHTML
                        text = await self._extract_text_from_html(content_path)

                        if text.strip():  # Only include non-empty chapters
                            chapter_num += 1
                            # Try to find chapter title
                            title = await self._find_chapter_title(content_path)
                            if not title:
                                title = f"Chapter {chapter_num}"

                            chapters[title] = text

        return chapters

    async def _extract_text_from_html(self, html_path: str) -> str:
        """Extract plain text from HTML/XHTML file"""
        async with aiofiles.open(html_path, 'r', encoding='utf-8') as f:
            content = await f.read()

        try:
            tree = etree.fromstring(content.encode('utf-8'), parser=etree.HTMLParser())
        except:
            # Try XML parser if HTML parser fails
            tree = etree.fromstring(content.encode('utf-8'))

        # Remove script and style elements
        for element in tree.xpath('.//script | .//style'):
            element.getparent().remove(element)

        # Extract text
        text_parts = []
        for element in tree.iter():
            if element.text:
                text_parts.append(element.text.strip())
            if element.tail:
                text_parts.append(element.tail.strip())

        # Join and clean up
        text = ' '.join(text_parts)
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)
        # Remove HTML entities
        text = html.unescape(text)

        return text.strip()

    async def _find_chapter_title(self, html_path: str) -> str:
        """Try to find chapter title from HTML"""
        async with aiofiles.open(html_path, 'r', encoding='utf-8') as f:
            content = await f.read()

        try:
            tree = etree.fromstring(content.encode('utf-8'), parser=etree.HTMLParser())
        except:
            tree = etree.fromstring(content.encode('utf-8'))

        # Look for common title elements
        for xpath in ['//h1', '//h2', '//title', '//*[@class="chapter-title"]']:
            elements = tree.xpath(xpath)
            if elements and elements[0].text:
                return elements[0].text.strip()

        return ""
