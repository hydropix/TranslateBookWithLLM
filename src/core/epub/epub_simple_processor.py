"""
Simple EPUB processor that extracts pure text, translates it, and rebuilds a minimal EPUB.

This module provides a simplified workflow for EPUB translation that:
1. Extracts all text content from EPUB (removing ALL HTML tags)
2. Translates the text using the standard text translation pipeline
3. Reconstructs a minimal but valid EPUB 3.0 structure

The approach eliminates all placeholder management issues by working with pure text.
"""

import os
import zipfile
import tempfile
import re
import uuid
from lxml import etree
from datetime import datetime
import aiofiles

from src.config import NAMESPACES, DEFAULT_MODEL, MAIN_LINES_PER_CHUNK, API_ENDPOINT
from ..text_processor import split_text_into_chunks_with_context
from ..translator import translate_chunks


async def extract_pure_text_from_epub(epub_path: str, log_callback=None) -> tuple[str, dict]:
    """
    Extract pure text from EPUB, removing all HTML tags.

    Args:
        epub_path: Path to input EPUB file
        log_callback: Optional logging callback

    Returns:
        tuple: (extracted_text, metadata_dict)
            - extracted_text: Pure text with chapter markers
            - metadata_dict: Dict containing title, author, language, etc.
    """
    if log_callback:
        log_callback("simple_mode_extraction_start", "Simple mode: Extracting pure text from EPUB")

    metadata = {
        'title': 'Untitled',
        'author': 'Unknown',
        'language': 'en',
        'identifier': str(uuid.uuid4())
    }

    chapters = []

    with tempfile.TemporaryDirectory() as temp_dir:
        # Extract EPUB
        with zipfile.ZipFile(epub_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # Find OPF file
        opf_path = None
        for root, _, files in os.walk(temp_dir):
            for file in files:
                if file.endswith('.opf'):
                    opf_path = os.path.join(root, file)
                    break
            if opf_path:
                break

        if not opf_path:
            raise FileNotFoundError("No OPF file found in EPUB")

        # Parse OPF to extract metadata
        opf_tree = etree.parse(opf_path)
        opf_root = opf_tree.getroot()

        # Extract metadata
        metadata_elem = opf_root.find('.//opf:metadata', namespaces=NAMESPACES)
        if metadata_elem is not None:
            title_elem = metadata_elem.find('.//dc:title', namespaces=NAMESPACES)
            if title_elem is not None and title_elem.text:
                metadata['title'] = title_elem.text.strip()

            creator_elem = metadata_elem.find('.//dc:creator', namespaces=NAMESPACES)
            if creator_elem is not None and creator_elem.text:
                metadata['author'] = creator_elem.text.strip()

            lang_elem = metadata_elem.find('.//dc:language', namespaces=NAMESPACES)
            if lang_elem is not None and lang_elem.text:
                metadata['language'] = lang_elem.text.strip()

            id_elem = metadata_elem.find('.//dc:identifier', namespaces=NAMESPACES)
            if id_elem is not None and id_elem.text:
                metadata['identifier'] = id_elem.text.strip()

        # Get content files from spine
        manifest = opf_root.find('.//opf:manifest', namespaces=NAMESPACES)
        spine = opf_root.find('.//opf:spine', namespaces=NAMESPACES)

        if manifest is None or spine is None:
            raise ValueError("No manifest or spine found in EPUB")

        # Build ID to href mapping
        id_to_href = {}
        for item in manifest.findall('.//opf:item', namespaces=NAMESPACES):
            item_id = item.get('id')
            href = item.get('href')
            media_type = item.get('media-type')
            if item_id and href and media_type in ['application/xhtml+xml', 'text/html']:
                id_to_href[item_id] = href

        # Process spine items in reading order
        opf_dir = os.path.dirname(opf_path)

        for itemref in spine.findall('.//opf:itemref', namespaces=NAMESPACES):
            idref = itemref.get('idref')
            if idref and idref in id_to_href:
                href = id_to_href[idref]
                content_path = os.path.join(opf_dir, href)

                if os.path.exists(content_path):
                    # Extract text from this chapter
                    chapter_title, chapter_text = await _extract_text_from_xhtml(content_path)

                    if chapter_text.strip():
                        chapters.append({
                            'title': chapter_title,
                            'text': chapter_text
                        })

    # Build the complete text with chapter markers
    text_parts = []
    for chapter in chapters:
        if chapter['title']:
            text_parts.append(f"# CHAPTER: {chapter['title']}\n")
        text_parts.append(chapter['text'])
        text_parts.append("\n\n")  # Double newline between chapters

    full_text = "".join(text_parts).strip()

    if log_callback:
        log_callback("simple_mode_extraction_complete",
                    f"Simple mode: Extracted {len(chapters)} chapters, {len(full_text)} characters")

    return full_text, metadata


async def _extract_text_from_xhtml(xhtml_path: str) -> tuple[str, str]:
    """
    Extract pure text from XHTML file, removing all tags.

    Args:
        xhtml_path: Path to XHTML/HTML file

    Returns:
        tuple: (chapter_title, plain_text)
    """
    async with aiofiles.open(xhtml_path, 'r', encoding='utf-8') as f:
        content = await f.read()

    try:
        # Parse as XML first, fall back to HTML
        parser = etree.XMLParser(recover=True, remove_blank_text=True)
        tree = etree.fromstring(content.encode('utf-8'), parser)
    except:
        parser = etree.HTMLParser()
        tree = etree.fromstring(content.encode('utf-8'), parser)

    # Try to extract chapter title from h1, h2, or title tags
    chapter_title = ""
    for xpath in ['.//h1', './/h2', './/title']:
        title_elems = tree.xpath(xpath, namespaces=NAMESPACES)
        if title_elems and hasattr(title_elems[0], 'text') and title_elems[0].text:
            chapter_title = title_elems[0].text.strip()
            break

    # Remove script and style elements
    for element in tree.xpath('.//script | .//style', namespaces=NAMESPACES):
        parent = element.getparent()
        if parent is not None:
            parent.remove(element)

    # Extract text from body
    body = tree.xpath('.//body', namespaces=NAMESPACES)
    if body:
        text_root = body[0]
    else:
        text_root = tree

    # Recursively extract text
    text_parts = []
    _extract_text_recursive(text_root, text_parts)

    # Join and clean up text
    plain_text = "\n".join(text_parts)

    # Clean up multiple consecutive newlines (max 2 in a row)
    plain_text = re.sub(r'\n{3,}', '\n\n', plain_text)

    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in plain_text.split('\n')]
    plain_text = '\n'.join(lines)

    return chapter_title, plain_text.strip()


def _extract_text_recursive(element, text_parts: list):
    """
    Recursively extract text from element and its children.

    Args:
        element: lxml element
        text_parts: List to append text to
    """
    # Block-level tags that should add paragraph breaks
    block_tags = {
        'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'blockquote', 'pre', 'li', 'tr', 'section', 'article'
    }

    # Get tag name without namespace
    tag = element.tag
    if isinstance(tag, str):
        # Remove namespace
        if '}' in tag:
            tag = tag.split('}', 1)[1]
    else:
        tag = ''

    # Handle element text
    if hasattr(element, 'text') and element.text:
        text = element.text.strip()
        if text:
            text_parts.append(text)

    # Process children
    for child in element:
        _extract_text_recursive(child, text_parts)

        # Handle tail text (text after child element)
        if hasattr(child, 'tail') and child.tail:
            tail = child.tail.strip()
            if tail:
                text_parts.append(tail)

    # Add paragraph break after block elements
    if tag.lower() in block_tags and text_parts and text_parts[-1] != '':
        text_parts.append('')  # Empty string creates paragraph break


async def create_simple_epub(translated_text: str, output_path: str, metadata: dict,
                            target_language: str, log_callback=None) -> None:
    """
    Create a minimal but valid EPUB 3.0 from translated text.

    Args:
        translated_text: Translated text with chapter markers
        output_path: Path for output EPUB file
        metadata: Dictionary with title, author, language, identifier
        target_language: Target language code
        log_callback: Optional logging callback
    """
    if log_callback:
        log_callback("simple_mode_rebuild_start", "Simple mode: Rebuilding EPUB structure")

    # Parse chapters from translated text
    chapters = _parse_chapters_from_text(translated_text)

    if log_callback:
        log_callback("simple_mode_chapters_parsed", f"Simple mode: Parsed {len(chapters)} chapters")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create EPUB directory structure
        oebps_dir = os.path.join(temp_dir, 'OEBPS')
        meta_inf_dir = os.path.join(temp_dir, 'META-INF')
        os.makedirs(oebps_dir, exist_ok=True)
        os.makedirs(meta_inf_dir, exist_ok=True)

        # Create mimetype file
        mimetype_path = os.path.join(temp_dir, 'mimetype')
        async with aiofiles.open(mimetype_path, 'w', encoding='utf-8') as f:
            await f.write('application/epub+zip')

        # Create container.xml
        container_xml = _create_container_xml()
        container_path = os.path.join(meta_inf_dir, 'container.xml')
        async with aiofiles.open(container_path, 'w', encoding='utf-8') as f:
            await f.write(container_xml)

        # Create CSS file
        css_content = _create_simple_css()
        css_path = os.path.join(oebps_dir, 'styles.css')
        async with aiofiles.open(css_path, 'w', encoding='utf-8') as f:
            await f.write(css_content)

        # Create chapter XHTML files
        chapter_files = []
        for i, chapter in enumerate(chapters, 1):
            filename = f'chapter_{i:02d}.xhtml'
            chapter_files.append(filename)

            xhtml_content = _create_chapter_xhtml(chapter['title'], chapter['text'])
            xhtml_path = os.path.join(oebps_dir, filename)
            async with aiofiles.open(xhtml_path, 'w', encoding='utf-8') as f:
                await f.write(xhtml_content)

        # Update metadata with target language
        metadata['language'] = target_language.lower()[:2] if target_language else metadata.get('language', 'en')

        # Create content.opf
        opf_content = _create_content_opf(metadata, chapter_files)
        opf_path = os.path.join(oebps_dir, 'content.opf')
        async with aiofiles.open(opf_path, 'w', encoding='utf-8') as f:
            await f.write(opf_content)

        # Create toc.ncx
        ncx_content = _create_toc_ncx(metadata, chapters)
        ncx_path = os.path.join(oebps_dir, 'toc.ncx')
        async with aiofiles.open(ncx_path, 'w', encoding='utf-8') as f:
            await f.write(ncx_content)

        # Create EPUB zip file
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as epub_zip:
            # Add mimetype first (uncompressed as per EPUB spec)
            epub_zip.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)

            # Add all other files
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file != 'mimetype':
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        epub_zip.write(file_path, arcname)

    if log_callback:
        log_callback("simple_mode_epub_created", f"Simple mode: EPUB created successfully at {output_path}")


def _parse_chapters_from_text(text: str) -> list[dict]:
    """
    Parse chapter structure from text with chapter markers.

    Args:
        text: Text with '# CHAPTER: Title' markers

    Returns:
        List of chapter dictionaries with 'title' and 'text' keys
    """
    chapters = []

    # Split by chapter markers
    chapter_pattern = r'^# CHAPTER:\s*(.+)$'
    lines = text.split('\n')

    current_chapter = None
    current_text = []

    for line in lines:
        match = re.match(chapter_pattern, line.strip())
        if match:
            # Save previous chapter if exists
            if current_chapter is not None:
                chapters.append({
                    'title': current_chapter,
                    'text': '\n'.join(current_text).strip()
                })

            # Start new chapter
            current_chapter = match.group(1).strip()
            current_text = []
        else:
            # Add line to current chapter
            current_text.append(line)

    # Save last chapter
    if current_chapter is not None:
        chapters.append({
            'title': current_chapter,
            'text': '\n'.join(current_text).strip()
        })

    # If no chapters were found, create a single chapter
    if not chapters and text.strip():
        chapters.append({
            'title': 'Content',
            'text': text.strip()
        })

    return chapters


def _create_container_xml() -> str:
    """Create META-INF/container.xml content."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>'''


def _create_simple_css() -> str:
    """Create simple, readable CSS."""
    return '''body {
    font-family: Georgia, serif;
    line-height: 1.6;
    margin: 2em;
    max-width: 40em;
}

h1 {
    font-size: 2em;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    text-align: center;
}

p {
    margin: 1em 0;
    text-align: justify;
    text-indent: 1.5em;
}

p:first-of-type {
    text-indent: 0;
}'''


def _create_chapter_xhtml(title: str, text: str) -> str:
    """
    Create XHTML content for a chapter.

    Args:
        title: Chapter title
        text: Chapter text content

    Returns:
        Complete XHTML string
    """
    # Escape HTML special characters
    import html
    title_escaped = html.escape(title) if title else "Chapter"

    # Split text into paragraphs (separated by blank lines)
    paragraphs = []
    for para in text.split('\n\n'):
        para_stripped = para.strip()
        if para_stripped:
            # Escape HTML and preserve line breaks within paragraphs
            para_escaped = html.escape(para_stripped)
            # Replace single newlines with spaces
            para_escaped = para_escaped.replace('\n', ' ')
            paragraphs.append(f'  <p>{para_escaped}</p>')

    paragraphs_html = '\n'.join(paragraphs)

    return f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>{title_escaped}</title>
  <link rel="stylesheet" type="text/css" href="styles.css"/>
</head>
<body>
  <h1>{title_escaped}</h1>
{paragraphs_html}
</body>
</html>'''


def _create_content_opf(metadata: dict, chapter_files: list) -> str:
    """
    Create content.opf file content.

    Args:
        metadata: Dictionary with title, author, language, identifier
        chapter_files: List of chapter filenames

    Returns:
        Complete OPF XML string
    """
    import html

    title = html.escape(metadata.get('title', 'Untitled'))
    author = html.escape(metadata.get('author', 'Unknown'))
    language = metadata.get('language', 'en')
    identifier = metadata.get('identifier', str(uuid.uuid4()))
    date = datetime.now().strftime('%Y-%m-%d')

    # Build manifest items
    manifest_items = ['    <item id="css" href="styles.css" media-type="text/css"/>']
    for i, filename in enumerate(chapter_files, 1):
        manifest_items.append(
            f'    <item id="chapter{i:02d}" href="{filename}" media-type="application/xhtml+xml"/>'
        )
    manifest_items.append('    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')

    manifest_xml = '\n'.join(manifest_items)

    # Build spine itemrefs
    spine_items = []
    for i in range(1, len(chapter_files) + 1):
        spine_items.append(f'    <itemref idref="chapter{i:02d}"/>')

    spine_xml = '\n'.join(spine_items)

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
    <dc:language>{language}</dc:language>
    <dc:identifier id="bookid">{identifier}</dc:identifier>
    <dc:date>{date}</dc:date>
    <meta property="dcterms:modified">{datetime.now().isoformat()}</meta>
  </metadata>
  <manifest>
{manifest_xml}
  </manifest>
  <spine toc="ncx">
{spine_xml}
  </spine>
</package>'''


def _create_toc_ncx(metadata: dict, chapters: list) -> str:
    """
    Create toc.ncx (Navigation Control file for EPUB 2 compatibility).

    Args:
        metadata: Dictionary with title, author, identifier
        chapters: List of chapter dictionaries

    Returns:
        Complete NCX XML string
    """
    import html

    title = html.escape(metadata.get('title', 'Untitled'))
    identifier = metadata.get('identifier', str(uuid.uuid4()))

    # Build nav points
    nav_points = []
    for i, chapter in enumerate(chapters, 1):
        chapter_title = html.escape(chapter['title']) if chapter['title'] else f'Chapter {i}'
        nav_points.append(f'''    <navPoint id="navpoint-{i}" playOrder="{i}">
      <navLabel>
        <text>{chapter_title}</text>
      </navLabel>
      <content src="chapter_{i:02d}.xhtml"/>
    </navPoint>''')

    nav_xml = '\n'.join(nav_points)

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="{identifier}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle>
    <text>{title}</text>
  </docTitle>
  <navMap>
{nav_xml}
  </navMap>
</ncx>'''


async def translate_text_as_string(
    text: str,
    source_language: str,
    target_language: str,
    model_name: str = DEFAULT_MODEL,
    cli_api_endpoint: str = API_ENDPOINT,
    chunk_target_lines: int = MAIN_LINES_PER_CHUNK,
    progress_callback=None,
    log_callback=None,
    stats_callback=None,
    check_interruption_callback=None,
    custom_instructions: str = "",
    llm_provider: str = "ollama",
    gemini_api_key=None,
    openai_api_key=None,
    enable_post_processing: bool = False,
    post_processing_instructions: str = "",
    context_window: int = 2048,
    auto_adjust_context: bool = True,
    min_chunk_size: int = 5
) -> str:
    """
    Translate a text string using the standard text translation workflow.

    This function is used by simple mode EPUB translation to translate
    the extracted pure text.

    Args:
        text: Text to translate
        source_language: Source language
        target_language: Target language
        model_name: LLM model name
        cli_api_endpoint: API endpoint
        chunk_target_lines: Target lines per chunk
        progress_callback: Progress callback
        log_callback: Logging callback
        stats_callback: Statistics callback
        check_interruption_callback: Interruption check callback
        custom_instructions: Additional translation instructions
        llm_provider: LLM provider (ollama/gemini/openai)
        gemini_api_key: Gemini API key
        openai_api_key: OpenAI API key
        enable_post_processing: Enable post-processing
        post_processing_instructions: Post-processing instructions
        context_window: Context window size
        auto_adjust_context: Auto-adjust context
        min_chunk_size: Minimum chunk size

    Returns:
        Translated text string
    """
    if log_callback:
        log_callback("simple_mode_text_translation_start",
                    f"Simple mode: Translating text from {source_language} to {target_language}")

    # Split text into chunks
    structured_chunks = split_text_into_chunks_with_context(text, chunk_target_lines)
    total_chunks = len(structured_chunks)

    if stats_callback and total_chunks > 0:
        stats_callback({'total_chunks': total_chunks, 'completed_chunks': 0, 'failed_chunks': 0})

    if total_chunks == 0 and text.strip():
        if log_callback:
            log_callback("simple_mode_no_chunks",
                        "Simple mode: No chunks generated, processing as single block")
        structured_chunks = [{"context_before": "", "main_content": text, "context_after": ""}]
        total_chunks = 1
        if stats_callback:
            stats_callback({'total_chunks': 1, 'completed_chunks': 0, 'failed_chunks': 0})
    elif total_chunks == 0:
        if log_callback:
            log_callback("simple_mode_empty_text", "Simple mode: Empty text, skipping translation")
        if progress_callback:
            progress_callback(100)
        return ""

    if log_callback:
        log_callback("simple_mode_chunks_info",
                    f"Simple mode: Translating {total_chunks} chunks")

    # Translate chunks using the standard text translation workflow
    translated_parts = await translate_chunks(
        structured_chunks,
        source_language,
        target_language,
        model_name,
        cli_api_endpoint,
        progress_callback=progress_callback,
        log_callback=log_callback,
        stats_callback=stats_callback,
        check_interruption_callback=check_interruption_callback,
        custom_instructions=custom_instructions,
        llm_provider=llm_provider,
        gemini_api_key=gemini_api_key,
        openai_api_key=openai_api_key,
        enable_post_processing=enable_post_processing,
        post_processing_instructions=post_processing_instructions,
        context_window=context_window,
        auto_adjust_context=auto_adjust_context,
        min_chunk_size=min_chunk_size
    )

    if progress_callback:
        progress_callback(100)

    # Join translated parts
    translated_text = "\n".join(translated_parts)

    if log_callback:
        log_callback("simple_mode_text_translation_complete",
                    f"Simple mode: Translation complete, {len(translated_text)} characters")

    return translated_text
