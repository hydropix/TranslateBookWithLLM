"""
Fast EPUB processor that extracts pure text, translates it, and rebuilds a minimal EPUB.

PRODUCTION-READY APPROACH:
1. Extract 100% pure text from EPUB (strip ALL HTML/XML/structure)
2. Split into equal-sized chunks (respecting sentence boundaries)
3. Translate chunk by chunk using standard text translation
4. Rebuild a valid, compliant EPUB 2.0 with translated text

Key features:
- Eliminates ALL placeholder/tag issues by working with pure text
- Creates EPUB 2.0 files compatible with strict readers (Aquile Reader, etc.)
- Flat directory structure for maximum compatibility
- Correct ZIP file ordering as per EPUB specification
- UTF-8 encoding throughout
- Handles ANY EPUB input regardless of complexity

Technical specifications:
- EPUB version: 2.0 (maximum compatibility)
- Structure: Flat (no OEBPS folder)
- File order: mimetype → META-INF/container.xml → content.opf → chapters
- Encoding: UTF-8 without BOM
- Compression: Stored (mimetype), Deflated (all others)
"""

import os
import zipfile
import tempfile
import re
import uuid
from lxml import etree
from datetime import datetime
import aiofiles

from src.config import NAMESPACES, DEFAULT_MODEL, MAIN_LINES_PER_CHUNK, API_ENDPOINT, SENTENCE_TERMINATORS, TRANSLATE_TAG_IN, TRANSLATE_TAG_OUT
from ..text_processor import split_text_into_chunks_with_context
from ..translator import translate_chunks


async def extract_pure_text_from_epub(epub_path: str, log_callback=None) -> tuple[str, dict]:
    """
    Extract 100% pure text from EPUB (production-ready).

    Strips ALL HTML/XML tags, structure, and formatting - returns only readable text.
    Handles malformed EPUBs gracefully and extracts maximum content.

    Args:
        epub_path: Path to input EPUB file (must exist and be a valid ZIP)
        log_callback: Optional logging callback function(event_type, message)

    Returns:
        tuple: (extracted_text, metadata_dict)
            - extracted_text: Pure text content (no markup, no tags, no structure)
            - metadata_dict: Dict with keys: title, author, language, identifier

    Raises:
        FileNotFoundError: If EPUB file doesn't exist
        zipfile.BadZipFile: If file is not a valid ZIP/EPUB
        ValueError: If EPUB structure is invalid (no OPF file found)
    """
    if not os.path.exists(epub_path):
        raise FileNotFoundError(f"EPUB file not found: {epub_path}")

    if log_callback:
        log_callback("fast_mode_extraction_start", "Fast mode: Extracting pure text from EPUB")

    metadata = {
        'title': 'Untitled',
        'author': 'Unknown',
        'language': 'en',
        'identifier': str(uuid.uuid4())
    }

    all_text_parts = []

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract EPUB (with validation)
            try:
                with zipfile.ZipFile(epub_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
            except zipfile.BadZipFile as e:
                raise zipfile.BadZipFile(f"Invalid EPUB file (not a valid ZIP): {epub_path}") from e

            # Find OPF file (package document)
            opf_path = None
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith('.opf'):
                        opf_path = os.path.join(root, file)
                        break
                if opf_path:
                    break

            if not opf_path:
                raise ValueError(f"Invalid EPUB structure: No OPF file found in {epub_path}")

            # Parse OPF to extract metadata
            try:
                opf_tree = etree.parse(opf_path)
                opf_root = opf_tree.getroot()
            except Exception as e:
                raise ValueError(f"Failed to parse OPF file: {e}") from e

            # Extract metadata (with defaults if not found)
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
                raise ValueError("Invalid EPUB structure: No manifest or spine found in OPF")

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
                        try:
                            # Extract pure text (no titles, no structure markers)
                            pure_text = await _extract_pure_text_from_xhtml(content_path)
                            if pure_text.strip():
                                all_text_parts.append(pure_text.strip())
                        except Exception as e:
                            # Log but continue with other chapters if one fails
                            if log_callback:
                                log_callback("fast_mode_chapter_extraction_error",
                                           f"Warning: Failed to extract text from {href}: {e}")
                            continue

        # Join all text with paragraph breaks
        full_text = "\n\n".join(all_text_parts)

        if not full_text.strip():
            raise ValueError("No text content could be extracted from EPUB")

        if log_callback:
            log_callback("fast_mode_extraction_complete",
                        f"Fast mode: Extracted {len(full_text)} characters of pure text")

        return full_text, metadata

    except (FileNotFoundError, zipfile.BadZipFile, ValueError):
        # Re-raise known errors
        raise
    except Exception as e:
        # Catch-all for unexpected errors
        raise RuntimeError(f"Unexpected error during EPUB text extraction: {e}") from e


async def _extract_pure_text_from_xhtml(xhtml_path: str) -> str:
    """
    Extract 100% pure text from XHTML file - RADICAL APPROACH.
    Removes ALL tags, ALL structure, ALL formatting.

    Args:
        xhtml_path: Path to XHTML/HTML file

    Returns:
        str: Pure text content only
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

    # Remove script and style elements completely
    for element in tree.xpath('.//script | .//style', namespaces=NAMESPACES):
        parent = element.getparent()
        if parent is not None:
            parent.remove(element)

    # Extract text from body (or whole tree if no body)
    body = tree.xpath('.//body', namespaces=NAMESPACES)
    if body:
        text_root = body[0]
    else:
        text_root = tree

    # Recursively extract ALL text
    text_parts = []
    _extract_text_recursive(text_root, text_parts)

    # Join and clean up text
    plain_text = "\n".join(text_parts)

    # Clean up excessive newlines (max 2 in a row for paragraph breaks)
    plain_text = re.sub(r'\n{3,}', '\n\n', plain_text)

    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in plain_text.split('\n')]
    plain_text = '\n'.join(lines)

    # Remove empty lines at start/end
    return plain_text.strip()


def _extract_text_recursive(element, text_parts: list):
    """
    Recursively extract text from element and its children.

    Block-level elements accumulate their inline content with spaces,
    then add the complete block as a single text part.

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

    tag_lower = tag.lower()

    # If this is a block element, accumulate all inline content with spaces
    if tag_lower in block_tags:
        inline_parts = []
        _extract_inline_text(element, inline_parts)
        block_text = ' '.join(inline_parts)
        # Clean up multiple spaces
        block_text = ' '.join(block_text.split())
        if block_text:
            text_parts.append(block_text)
            text_parts.append('')  # Empty string creates paragraph break
    else:
        # For non-block elements, process normally (handles nested structures)
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


def _extract_inline_text(element, inline_parts: list):
    """
    Extract all text from an element and its children as inline content.

    This accumulates text without adding paragraph breaks, suitable for
    gathering all content within a block-level element.

    Args:
        element: lxml element
        inline_parts: List to append text parts to
    """
    # Handle element text
    if hasattr(element, 'text') and element.text:
        text = element.text.strip()
        if text:
            inline_parts.append(text)

    # Process children recursively
    for child in element:
        _extract_inline_text(child, inline_parts)

        # Handle tail text (text after child element)
        if hasattr(child, 'tail') and child.tail:
            tail = child.tail.strip()
            if tail:
                inline_parts.append(tail)


def _clean_translation_tags(text: str) -> str:
    """
    Clean up residual translation tags from the text.

    Removes <TRANSLATION> and </TRANSLATION> tags that may appear in the output.
    These tags are used internally by the LLM provider to mark translated content,
    but should not appear in the final EPUB.

    Args:
        text: Text potentially containing translation tags

    Returns:
        Cleaned text with all translation tags removed
    """
    # Remove opening tags (with optional spaces and angle brackets)
    text = re.sub(r'<\s*TRANSLATION\s*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'&lt;\s*TRANSLATION\s*&gt;', '', text, flags=re.IGNORECASE)

    # Remove closing tags (with optional spaces and angle brackets)
    text = re.sub(r'</\s*TRANSLATION\s*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'&lt;/\s*TRANSLATION\s*&gt;', '', text, flags=re.IGNORECASE)

    # Remove configured translation tags from config
    text = text.replace(TRANSLATE_TAG_IN, '')
    text = text.replace(TRANSLATE_TAG_OUT, '')

    # Clean up any excessive whitespace that might result from tag removal
    text = re.sub(r' {2,}', ' ', text)  # Multiple spaces to single space
    text = re.sub(r'\n{3,}', '\n\n', text)  # Max 2 newlines in a row

    return text.strip()


async def create_simple_epub(translated_text: str, output_path: str, metadata: dict,
                            target_language: str, log_callback=None) -> None:
    """
    Create a standard, generic EPUB 3.0 from translated pure text - RADICAL APPROACH.

    Splits text into readable chapters (auto-pagination by size).
    Creates a clean, valid EPUB structure.

    Args:
        translated_text: Pure translated text (no markup)
        output_path: Path for output EPUB file
        metadata: Dictionary with title, author, language, identifier
        target_language: Target language code
        log_callback: Optional logging callback
    """
    if log_callback:
        log_callback("fast_mode_rebuild_start", "Fast mode: Building generic EPUB from translated text")

    # Split text into chapters (auto-pagination by word count)
    chapters = _auto_split_into_chapters(translated_text, words_per_chapter=5000)

    if log_callback:
        log_callback("fast_mode_chapters_created", f"Fast mode: Created {len(chapters)} chapters")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create EPUB directory structure - FLAT (EPUB 2.0 style, like working EPUBs)
        # Files at root level for maximum compatibility with strict readers
        meta_inf_dir = os.path.join(temp_dir, 'META-INF')
        os.makedirs(meta_inf_dir, exist_ok=True)

        # Create mimetype file (MUST be first and uncompressed)
        mimetype_path = os.path.join(temp_dir, 'mimetype')
        async with aiofiles.open(mimetype_path, 'w', encoding='utf-8') as f:
            await f.write('application/epub+zip')

        # Create container.xml (points to content.opf at root)
        container_xml = _create_container_xml()
        container_path = os.path.join(meta_inf_dir, 'container.xml')
        async with aiofiles.open(container_path, 'w', encoding='utf-8') as f:
            await f.write(container_xml)

        # Create CSS file (clean, readable style)
        css_content = _create_simple_css()
        css_path = os.path.join(temp_dir, 'stylesheet.css')
        async with aiofiles.open(css_path, 'w', encoding='utf-8') as f:
            await f.write(css_content)

        # Update metadata with target language BEFORE creating chapters
        metadata['language'] = target_language.lower()[:2] if target_language else metadata.get('language', 'en')

        # Create chapter XHTML files
        chapter_files = []
        for i, chapter_text in enumerate(chapters, 1):
            filename = f'chapter_{i:03d}.xhtml'
            chapter_files.append(filename)

            # Clean translation tags BEFORE creating XHTML
            chapter_text_cleaned = _clean_translation_tags(chapter_text)

            chapter_title = f'Chapter {i}'
            xhtml_content = _create_chapter_xhtml(chapter_title, chapter_text_cleaned, metadata['language'])
            xhtml_path = os.path.join(temp_dir, filename)
            # Write with proper UTF-8 encoding (no newline parameter for Windows compatibility)
            async with aiofiles.open(xhtml_path, 'w', encoding='utf-8') as f:
                await f.write(xhtml_content)

        # Create content.opf (package document) - EPUB 2.0 format
        opf_content = _create_content_opf(metadata, chapter_files)
        opf_path = os.path.join(temp_dir, 'content.opf')
        async with aiofiles.open(opf_path, 'w', encoding='utf-8') as f:
            await f.write(opf_content)

        # Create toc.ncx (navigation for EPUB 2.0)
        ncx_content = _create_toc_ncx(metadata, len(chapters))
        ncx_path = os.path.join(temp_dir, 'toc.ncx')
        async with aiofiles.open(ncx_path, 'w', encoding='utf-8') as f:
            await f.write(ncx_content)

        # Create EPUB zip file with CORRECT ORDER (critical for strict readers!)
        # EPUB spec requires: 1. mimetype, 2. META-INF/container.xml, 3. other files
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as epub_zip:
            # 1. Add mimetype FIRST and UNCOMPRESSED (EPUB spec requirement)
            epub_zip.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)

            # 2. Add META-INF/container.xml SECOND (required by strict readers)
            epub_zip.write(container_path, 'META-INF/container.xml')

            # 3. Add all other files in a specific order for compatibility
            # Add OPF and NCX first (navigation files)
            epub_zip.write(opf_path, 'content.opf')
            epub_zip.write(ncx_path, 'toc.ncx')

            # Add CSS
            epub_zip.write(css_path, 'stylesheet.css')

            # Add chapter files in order
            for i, chapter_text in enumerate(chapters, 1):
                filename = f'chapter_{i:03d}.xhtml'
                xhtml_path = os.path.join(temp_dir, filename)
                if os.path.exists(xhtml_path):
                    epub_zip.write(xhtml_path, filename)

    if log_callback:
        log_callback("fast_mode_epub_created",
                    f"Fast mode: EPUB created successfully with {len(chapters)} chapters at {output_path}")


def _auto_split_into_chapters(text: str, words_per_chapter: int = 5000) -> list[str]:
    """
    Automatically split text into chapters based on word count.
    Respects paragraph and sentence boundaries - RADICAL APPROACH.

    Args:
        text: Pure text to split
        words_per_chapter: Target words per chapter (default 5000 ≈ 15-20 pages)

    Returns:
        List of chapter texts (always at least one chapter)
    """
    # Ensure we have text
    text = text.strip()
    if not text:
        return ["No content available."]

    # Split into paragraphs (separated by blank lines)
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]

    # If no paragraphs found, treat entire text as one paragraph
    if not paragraphs:
        paragraphs = [text]

    chapters = []
    current_chapter = []
    current_word_count = 0

    for paragraph in paragraphs:
        para_word_count = len(paragraph.split())

        # If adding this paragraph exceeds target AND we already have content
        if current_word_count > 0 and current_word_count + para_word_count > words_per_chapter:
            # Save current chapter
            chapters.append('\n\n'.join(current_chapter))
            current_chapter = [paragraph]
            current_word_count = para_word_count
        else:
            # Add to current chapter
            current_chapter.append(paragraph)
            current_word_count += para_word_count

    # Save last chapter
    if current_chapter:
        chapters.append('\n\n'.join(current_chapter))

    # Ensure we have at least one chapter with content
    if not chapters:
        chapters = [text if text else "No content available."]

    return chapters


def _create_container_xml() -> str:
    """Create META-INF/container.xml content - points to root level content.opf."""
    return '''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
   <rootfiles>
      <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>

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


def _create_chapter_xhtml(title: str, text: str, language: str = 'en') -> str:
    """
    Create XHTML content for a chapter - EPUB 2.0 format (like working EPUBs).

    Args:
        title: Chapter title
        text: Chapter text content
        language: Language code (e.g., 'en', 'fr')

    Returns:
        Complete XHTML string
    """
    # Escape HTML special characters
    import html
    title_escaped = html.escape(title) if title else "Chapter"

    # Ensure we have text
    text = text.strip() if text else "No content."

    # Split text into paragraphs (separated by blank lines)
    paragraphs = []
    for para in text.split('\n\n'):
        para_stripped = para.strip()
        if para_stripped:
            # Escape HTML and preserve line breaks within paragraphs
            para_escaped = html.escape(para_stripped)
            # Replace single newlines with spaces
            para_escaped = para_escaped.replace('\n', ' ')
            paragraphs.append(f'    <p>{para_escaped}</p>')

    # If no paragraphs were created, create at least one
    if not paragraphs:
        paragraphs.append(f'    <p>{html.escape(text)}</p>')

    paragraphs_html = '\n'.join(paragraphs)

    # EPUB 2.0 format - NO DOCTYPE, simple structure like working EPUBs
    return f'''<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml" lang="{language}" xml:lang="{language}">
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
    <title>{title_escaped}</title>
    <link rel="stylesheet" type="text/css" href="stylesheet.css"/>
  </head>
  <body>
    <h1>{title_escaped}</h1>
{paragraphs_html}
  </body>
</html>'''


def _create_content_opf(metadata: dict, chapter_files: list) -> str:
    """
    Create content.opf file content with translation signature.

    Args:
        metadata: Dictionary with title, author, language, identifier
        chapter_files: List of chapter filenames

    Returns:
        Complete OPF XML string
    """
    import html
    from src.config import SIGNATURE_ENABLED, PROJECT_NAME, PROJECT_GITHUB

    title = html.escape(metadata.get('title', 'Untitled'))
    author = html.escape(metadata.get('author', 'Unknown'))
    language = metadata.get('language', 'en')
    identifier = metadata.get('identifier', str(uuid.uuid4()))
    date = datetime.now().strftime('%Y-%m-%d')

    # Build manifest items - EPUB 2.0 style (no nav.xhtml)
    manifest_items = []
    for i, filename in enumerate(chapter_files, 1):
        manifest_items.append(
            f'    <item id="html{i}" href="{filename}" media-type="application/xhtml+xml"/>'
        )
    manifest_items.append('    <item id="css" href="stylesheet.css" media-type="text/css"/>')
    manifest_items.append('    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')

    manifest_xml = '\n'.join(manifest_items)

    # Build spine itemrefs
    spine_items = []
    for i in range(1, len(chapter_files) + 1):
        spine_items.append(f'    <itemref idref="html{i}"/>')

    spine_xml = '\n'.join(spine_items)

    # Add signature to metadata if enabled
    signature_metadata = ""
    if SIGNATURE_ENABLED:
        contributor_escaped = html.escape(PROJECT_NAME)
        description_escaped = html.escape(f"Translated using {PROJECT_NAME}\n{PROJECT_GITHUB}")
        signature_metadata = f'''
    <dc:contributor opf:role="trl">{contributor_escaped}</dc:contributor>
    <dc:description>{description_escaped}</dc:description>'''

    # EPUB 2.0 format - like working EPUBs
    return f'''<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="uuid_id">
  <metadata xmlns:opf="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <dc:title>{title}</dc:title>
    <dc:creator opf:role="aut">{author}</dc:creator>
    <dc:language>{language}</dc:language>
    <dc:identifier id="uuid_id" opf:scheme="uuid">{identifier}</dc:identifier>
    <dc:date>{date}</dc:date>{signature_metadata}
  </metadata>
  <manifest>
{manifest_xml}
  </manifest>
  <spine toc="ncx">
{spine_xml}
  </spine>
</package>'''


def _create_toc_ncx(metadata: dict, num_chapters: int) -> str:
    """
    Create toc.ncx (Navigation Control file for EPUB 2 compatibility).

    Args:
        metadata: Dictionary with title, author, identifier
        num_chapters: Number of chapters in the book

    Returns:
        Complete NCX XML string
    """
    import html

    title = html.escape(metadata.get('title', 'Untitled'))
    identifier = metadata.get('identifier', str(uuid.uuid4()))

    # Build nav points
    nav_points = []
    for i in range(1, num_chapters + 1):
        nav_points.append(f'''    <navPoint id="navpoint-{i}" playOrder="{i}">
      <navLabel>
        <text>Chapter {i}</text>
      </navLabel>
      <content src="chapter_{i:03d}.xhtml"/>
    </navPoint>''')

    nav_xml = '\n'.join(nav_points)

    # EPUB 2.0 NCX format - like working EPUBs
    return f'''<?xml version='1.0' encoding='utf-8'?>
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
    llm_provider: str = "ollama",
    gemini_api_key=None,
    openai_api_key=None,
    openrouter_api_key=None,
    context_window: int = 2048,
    auto_adjust_context: bool = True,
    min_chunk_size: int = 5,
    checkpoint_manager=None,
    translation_id: str = None,
    resume_from_index: int = 0
) -> str:
    """
    Translate a text string using the standard text translation workflow.

    This function is used by fast mode EPUB translation to translate
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
        llm_provider: LLM provider (ollama/gemini/openai)
        gemini_api_key: Gemini API key
        openai_api_key: OpenAI API key
        context_window: Context window size
        auto_adjust_context: Auto-adjust context
        min_chunk_size: Minimum chunk size
        checkpoint_manager: Checkpoint manager for resume functionality
        translation_id: ID of the translation job
        resume_from_index: Index to resume from

    Returns:
        Translated text string
    """
    if log_callback:
        log_callback("fast_mode_text_translation_start",
                    f"Fast mode: Translating text from {source_language} to {target_language}")

    # Split text into chunks
    structured_chunks = split_text_into_chunks_with_context(text, chunk_target_lines)
    total_chunks = len(structured_chunks)

    if stats_callback and total_chunks > 0:
        stats_callback({'total_chunks': total_chunks, 'completed_chunks': 0, 'failed_chunks': 0})

    if total_chunks == 0 and text.strip():
        if log_callback:
            log_callback("fast_mode_no_chunks",
                        "Fast mode: No chunks generated, processing as single block")
        structured_chunks = [{"context_before": "", "main_content": text, "context_after": ""}]
        total_chunks = 1
        if stats_callback:
            stats_callback({'total_chunks': 1, 'completed_chunks': 0, 'failed_chunks': 0})
    elif total_chunks == 0:
        if log_callback:
            log_callback("fast_mode_empty_text", "Fast mode: Empty text, skipping translation")
        if progress_callback:
            progress_callback(100)
        return ""

    if log_callback:
        log_callback("fast_mode_chunks_info",
                    f"Fast mode: Translating {total_chunks} chunks")

    # Translate chunks using the standard text translation workflow
    # IMPORTANT: Pass fast_mode=True to use simplified prompts without placeholder instructions
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
        llm_provider=llm_provider,
        gemini_api_key=gemini_api_key,
        openai_api_key=openai_api_key,
        openrouter_api_key=openrouter_api_key,
        context_window=context_window,
        auto_adjust_context=auto_adjust_context,
        min_chunk_size=min_chunk_size,
        fast_mode=True,  # Fast mode uses pure text - no HTML/XML placeholders
        checkpoint_manager=checkpoint_manager,
        translation_id=translation_id,
        resume_from_index=resume_from_index
    )

    if progress_callback:
        progress_callback(100)

    # Join translated parts
    translated_text = "\n".join(translated_parts)

    # Clean up any residual translation tags
    translated_text = _clean_translation_tags(translated_text)

    if log_callback:
        log_callback("fast_mode_text_translation_complete",
                    f"Fast mode: Translation complete, {len(translated_text)} characters")

    return translated_text
