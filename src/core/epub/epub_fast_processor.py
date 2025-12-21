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

from src.config import (
    NAMESPACES, DEFAULT_MODEL, MAIN_LINES_PER_CHUNK, API_ENDPOINT,
    SENTENCE_TERMINATORS, TRANSLATE_TAG_IN, TRANSLATE_TAG_OUT,
    FAST_MODE_PRESERVE_IMAGES, IMAGE_MARKER_PREFIX, IMAGE_MARKER_SUFFIX,
    FAST_MODE_PRESERVE_FORMATTING, FORMAT_ITALIC_START, FORMAT_ITALIC_END,
    FORMAT_BOLD_START, FORMAT_BOLD_END, FORMAT_HR_MARKER
)
from ..text_processor import split_text_into_chunks
from ..translator import translate_chunks

# Supported image media types for EPUB
IMAGE_MEDIA_TYPES = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/svg+xml': '.svg',
    'image/webp': '.webp'
}


async def extract_pure_text_from_epub(
    epub_path: str,
    log_callback=None,
    preserve_images: bool = None
) -> tuple[str, dict, list]:
    """
    Extract 100% pure text from EPUB (production-ready).

    Strips ALL HTML/XML tags, structure, and formatting - returns only readable text.
    Optionally preserves images by inserting markers and collecting image data.
    Handles malformed EPUBs gracefully and extracts maximum content.

    Args:
        epub_path: Path to input EPUB file (must exist and be a valid ZIP)
        log_callback: Optional logging callback function(event_type, message)
        preserve_images: Whether to extract and preserve images (default: FAST_MODE_PRESERVE_IMAGES from config)

    Returns:
        tuple: (extracted_text, metadata_dict, images_list)
            - extracted_text: Pure text content with optional image markers
            - metadata_dict: Dict with keys: title, author, language, identifier
            - images_list: List of dicts with keys: id, filename, data (bytes), media_type, alt

    Raises:
        FileNotFoundError: If EPUB file doesn't exist
        zipfile.BadZipFile: If file is not a valid ZIP/EPUB
        ValueError: If EPUB structure is invalid (no OPF file found)
    """
    if preserve_images is None:
        preserve_images = FAST_MODE_PRESERVE_IMAGES

    if not os.path.exists(epub_path):
        raise FileNotFoundError(f"EPUB file not found: {epub_path}")

    if log_callback:
        msg = "Fast mode: Extracting pure text from EPUB"
        if preserve_images:
            msg += " (preserving images)"
        log_callback("fast_mode_extraction_start", msg)

    metadata = {
        'title': 'Untitled',
        'author': 'Unknown',
        'language': 'en',
        'identifier': str(uuid.uuid4())
    }

    all_text_parts = []
    all_images = []  # Collected images: {id, filename, data, media_type, alt}
    image_counter = [0]  # Use list for mutable counter in nested function

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

            # Build ID to href mapping for content files
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
                    content_dir = os.path.dirname(content_path)

                    if os.path.exists(content_path):
                        try:
                            # Extract pure text with optional image markers
                            pure_text = await _extract_pure_text_from_xhtml(
                                content_path,
                                preserve_images=preserve_images,
                                images_list=all_images,
                                image_counter=image_counter,
                                content_dir=content_dir
                            )
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
            msg = f"Fast mode: Extracted {len(full_text)} characters of pure text"
            if preserve_images and all_images:
                msg += f" and {len(all_images)} images"
            log_callback("fast_mode_extraction_complete", msg)

        return full_text, metadata, all_images

    except (FileNotFoundError, zipfile.BadZipFile, ValueError):
        # Re-raise known errors
        raise
    except Exception as e:
        # Catch-all for unexpected errors
        raise RuntimeError(f"Unexpected error during EPUB text extraction: {e}") from e


async def _extract_pure_text_from_xhtml(
    xhtml_path: str,
    preserve_images: bool = False,
    images_list: list = None,
    image_counter: list = None,
    content_dir: str = None
) -> str:
    """
    Extract 100% pure text from XHTML file - RADICAL APPROACH.
    Removes ALL tags, ALL structure, ALL formatting.
    Optionally preserves images by inserting markers and collecting image data.

    Args:
        xhtml_path: Path to XHTML/HTML file
        preserve_images: Whether to extract images and insert markers
        images_list: List to append image data to (modified in place)
        image_counter: Mutable counter [n] for unique image IDs
        content_dir: Directory containing the XHTML file (for resolving relative image paths)

    Returns:
        str: Pure text content with optional image markers
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

    # Remove non-content elements completely (script, style, head, link, meta)
    # Using local-name() to match elements regardless of namespace
    # This is critical for Fast Mode: we only want actual readable text content
    non_content_tags = ('script', 'style', 'head', 'link', 'meta', 'title')
    xpath_conditions = ' or '.join(f'local-name()="{tag}"' for tag in non_content_tags)
    for element in tree.xpath(f'.//*[{xpath_conditions}]'):
        parent = element.getparent()
        if parent is not None:
            parent.remove(element)

    # Extract text from body (or whole tree if no body)
    # Using local-name() to match regardless of namespace
    body = tree.xpath('.//*[local-name()="body"]')
    if body:
        text_root = body[0]
    else:
        text_root = tree

    # Recursively extract ALL text (with optional image handling)
    text_parts = []
    _extract_text_recursive(
        text_root,
        text_parts,
        preserve_images=preserve_images,
        images_list=images_list,
        image_counter=image_counter,
        content_dir=content_dir
    )

    # Join and clean up text
    plain_text = "\n".join(text_parts)

    # Clean up excessive newlines (max 2 in a row for paragraph breaks)
    plain_text = re.sub(r'\n{3,}', '\n\n', plain_text)

    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in plain_text.split('\n')]
    plain_text = '\n'.join(lines)

    # Remove empty lines at start/end
    return plain_text.strip()


def _extract_text_recursive(
    element,
    text_parts: list,
    preserve_images: bool = False,
    images_list: list = None,
    image_counter: list = None,
    content_dir: str = None
):
    """
    Recursively extract text from element and its children.

    Block-level elements accumulate their inline content with spaces,
    then add the complete block as a single text part.
    Images are optionally extracted and replaced with markers.

    Args:
        element: lxml element
        text_parts: List to append text to
        preserve_images: Whether to extract images and insert markers
        images_list: List to append image data to
        image_counter: Mutable counter [n] for unique image IDs
        content_dir: Directory for resolving relative image paths
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

    # Handle image elements
    if tag_lower == 'img' and preserve_images and images_list is not None and image_counter is not None:
        image_marker = _extract_image(element, images_list, image_counter, content_dir)
        if image_marker:
            text_parts.append('')  # Paragraph break before image
            text_parts.append(image_marker)
            text_parts.append('')  # Paragraph break after image
        return

    # Handle SVG elements (sometimes used for images)
    if tag_lower == 'svg' and preserve_images:
        # Skip SVG content entirely (too complex to preserve)
        return

    # Handle horizontal rules - preserve as marker
    if tag_lower == 'hr' and FAST_MODE_PRESERVE_FORMATTING:
        text_parts.append('')  # Paragraph break before
        text_parts.append(FORMAT_HR_MARKER)
        text_parts.append('')  # Paragraph break after
        return

    # If this is a block element, accumulate all inline content with spaces
    if tag_lower in block_tags:
        inline_parts = []
        _extract_inline_text(
            element,
            inline_parts,
            preserve_images=preserve_images,
            images_list=images_list,
            image_counter=image_counter,
            content_dir=content_dir
        )
        # Join parts, preserving newlines from <br/> tags
        # First join with spaces, then clean up spaces around newlines
        block_text = ' '.join(inline_parts)
        # Clean up multiple spaces (but preserve newlines)
        block_text = re.sub(r'[^\S\n]+', ' ', block_text)  # Replace non-newline whitespace with single space
        block_text = re.sub(r' *\n *', '\n', block_text)   # Remove spaces around newlines
        block_text = block_text.strip()
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
            _extract_text_recursive(
                child,
                text_parts,
                preserve_images=preserve_images,
                images_list=images_list,
                image_counter=image_counter,
                content_dir=content_dir
            )

            # Handle tail text (text after child element)
            if hasattr(child, 'tail') and child.tail:
                tail = child.tail.strip()
                if tail:
                    text_parts.append(tail)


def _extract_inline_text(
    element,
    inline_parts: list,
    preserve_images: bool = False,
    images_list: list = None,
    image_counter: list = None,
    content_dir: str = None,
    preserve_formatting: bool = None
):
    """
    Extract all text from an element and its children as inline content.

    This accumulates text without adding paragraph breaks, suitable for
    gathering all content within a block-level element.
    Images within inline content are extracted and marked.
    Line breaks (<br/>) are preserved as newline characters.
    Formatting tags (em, i, strong, b) are preserved as markers.

    Args:
        element: lxml element
        inline_parts: List to append text parts to
        preserve_images: Whether to extract images and insert markers
        images_list: List to append image data to
        image_counter: Mutable counter [n] for unique image IDs
        content_dir: Directory for resolving relative image paths
        preserve_formatting: Whether to preserve italic/bold formatting (default from config)
    """
    if preserve_formatting is None:
        preserve_formatting = FAST_MODE_PRESERVE_FORMATTING

    # Get tag name without namespace
    tag = element.tag
    if isinstance(tag, str) and '}' in tag:
        tag = tag.split('}', 1)[1]
    tag_lower = tag.lower() if isinstance(tag, str) else ''

    # Handle line breaks - preserve them as newlines
    if tag_lower == 'br':
        inline_parts.append('\n')
        # Also handle tail text after <br/>
        if hasattr(element, 'tail') and element.tail:
            tail = element.tail.strip()
            if tail:
                inline_parts.append(tail)
        return

    # Handle inline images
    if tag_lower == 'img' and preserve_images and images_list is not None and image_counter is not None:
        image_marker = _extract_image(element, images_list, image_counter, content_dir)
        if image_marker:
            inline_parts.append(image_marker)
        return

    # Handle formatting tags (italic and bold) - wrap content with markers
    if preserve_formatting and tag_lower in ('em', 'i'):
        inline_parts.append(FORMAT_ITALIC_START)
        # Process content inside the formatting tag
        if hasattr(element, 'text') and element.text:
            text = element.text.strip()
            if text:
                inline_parts.append(text)
        for child in element:
            _extract_inline_text(
                child, inline_parts,
                preserve_images=preserve_images,
                images_list=images_list,
                image_counter=image_counter,
                content_dir=content_dir,
                preserve_formatting=preserve_formatting
            )
            if hasattr(child, 'tail') and child.tail:
                tail = child.tail.strip()
                if tail:
                    inline_parts.append(tail)
        inline_parts.append(FORMAT_ITALIC_END)
        return

    if preserve_formatting and tag_lower in ('strong', 'b'):
        inline_parts.append(FORMAT_BOLD_START)
        # Process content inside the formatting tag
        if hasattr(element, 'text') and element.text:
            text = element.text.strip()
            if text:
                inline_parts.append(text)
        for child in element:
            _extract_inline_text(
                child, inline_parts,
                preserve_images=preserve_images,
                images_list=images_list,
                image_counter=image_counter,
                content_dir=content_dir,
                preserve_formatting=preserve_formatting
            )
            if hasattr(child, 'tail') and child.tail:
                tail = child.tail.strip()
                if tail:
                    inline_parts.append(tail)
        inline_parts.append(FORMAT_BOLD_END)
        return

    # Handle element text
    if hasattr(element, 'text') and element.text:
        text = element.text.strip()
        if text:
            inline_parts.append(text)

    # Process children recursively
    for child in element:
        _extract_inline_text(
            child,
            inline_parts,
            preserve_images=preserve_images,
            images_list=images_list,
            image_counter=image_counter,
            content_dir=content_dir,
            preserve_formatting=preserve_formatting
        )

        # Handle tail text (text after child element)
        if hasattr(child, 'tail') and child.tail:
            tail = child.tail.strip()
            if tail:
                inline_parts.append(tail)


def _extract_image(
    element,
    images_list: list,
    image_counter: list,
    content_dir: str
) -> str:
    """
    Extract image data from an img element and return a marker.

    Captures all display attributes (width, height, style, class) to restore
    them in the output EPUB without passing them through the LLM.

    Args:
        element: lxml img element
        images_list: List to append image data to (modified in place)
        image_counter: Mutable counter [n] for unique image IDs
        content_dir: Directory for resolving relative image paths

    Returns:
        str: Image marker string (e.g., "⟦IMG:001⟧") or empty string if extraction failed
    """
    # Get image source
    src = element.get('src')
    if not src:
        # Try xlink:href (used in some EPUBs)
        src = element.get('{http://www.w3.org/1999/xlink}href')
    if not src:
        return ''

    # Skip data URIs (too large to handle efficiently)
    if src.startswith('data:'):
        return ''

    # Resolve relative path
    if content_dir and not os.path.isabs(src):
        # Handle URL-encoded paths
        from urllib.parse import unquote
        src_decoded = unquote(src)
        image_path = os.path.normpath(os.path.join(content_dir, src_decoded))
    else:
        image_path = src

    # Check if file exists
    if not os.path.exists(image_path):
        return ''

    # Determine media type from extension
    ext = os.path.splitext(image_path)[1].lower()
    media_type = None
    for mt, extension in IMAGE_MEDIA_TYPES.items():
        if extension == ext:
            media_type = mt
            break

    if not media_type:
        # Try to guess from common extensions
        ext_to_media = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.webp': 'image/webp'
        }
        media_type = ext_to_media.get(ext)

    if not media_type:
        return ''

    # Read image data
    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()
    except Exception:
        return ''

    # Generate unique ID
    image_id = f"{image_counter[0]:03d}"
    image_counter[0] += 1

    # Get alt text
    alt = element.get('alt', '')

    # Generate filename for output
    original_filename = os.path.basename(image_path)
    filename = f"image_{image_id}{ext}"

    # Extract display attributes (width, height, style, class)
    # These are preserved and restored without passing through the LLM
    width = element.get('width', '')
    height = element.get('height', '')
    style = element.get('style', '')
    css_class = element.get('class', '')

    # Add to images list with display attributes
    images_list.append({
        'id': image_id,
        'filename': filename,
        'original_filename': original_filename,
        'data': image_data,
        'media_type': media_type,
        'alt': alt,
        # Display attributes (preserved for output)
        'width': width,
        'height': height,
        'style': style,
        'class': css_class
    })

    # Return marker
    return f"{IMAGE_MARKER_PREFIX}{image_id}{IMAGE_MARKER_SUFFIX}"


def has_image_markers(text: str) -> bool:
    """
    Check if text contains any image markers.

    Args:
        text: Text that may contain image markers (e.g., "[IMG001]")

    Returns:
        bool: True if text contains at least one image marker
    """
    marker_pattern = re.compile(
        re.escape(IMAGE_MARKER_PREFIX) + r'\s*\d+\s*' + re.escape(IMAGE_MARKER_SUFFIX)
    )
    return bool(marker_pattern.search(text))


def _build_img_attributes(image_info: dict, is_inline: bool = False) -> str:
    """
    Build HTML attributes string for an image tag, including preserved display attributes.

    Args:
        image_info: Dict with image data including width, height, style, class
        is_inline: Whether this is an inline image (affects default class)

    Returns:
        String of HTML attributes (e.g., 'width="100" height="50" style="..."')
    """
    import html as html_module

    attrs = []

    # Add preserved width/height attributes
    width = image_info.get('width', '')
    height = image_info.get('height', '')
    if width:
        attrs.append(f'width="{html_module.escape(width)}"')
    if height:
        attrs.append(f'height="{html_module.escape(height)}"')

    # Add preserved style attribute
    style = image_info.get('style', '')
    if style:
        attrs.append(f'style="{html_module.escape(style)}"')

    # Handle class: combine preserved class with our class if needed
    css_class = image_info.get('class', '')
    if is_inline:
        # For inline images, add our inline-image class
        if css_class:
            combined_class = f"{css_class} inline-image"
        else:
            combined_class = "inline-image"
        attrs.append(f'class="{html_module.escape(combined_class)}"')
    elif css_class:
        # For block images, only use original class if present
        attrs.append(f'class="{html_module.escape(css_class)}"')

    return ' '.join(attrs)


def replace_image_markers_in_text(text: str, images_by_id: dict) -> str:
    """
    Replace ALL image markers in text with HTML img tags.

    This function finds and replaces image markers anywhere in the text,
    not just when they are isolated paragraphs. It handles:
    - Markers on their own line: [IMG001]
    - Markers with spaces: [IMG 001] or [ IMG001 ]
    - Markers inline with text: "Here is [IMG001] the image"
    - Markers with surrounding punctuation: ([IMG001]) or "[IMG001]"

    Preserves original display attributes (width, height, style, class).

    Args:
        text: Text containing image markers (e.g., "[IMG001]")
        images_by_id: Dict mapping image IDs to image info dicts

    Returns:
        Text with all image markers replaced by HTML img tags
    """
    if not images_by_id:
        return text

    # Pattern to match image markers with optional whitespace inside
    # Matches: [IMG001], [IMG 001], [ IMG001], [IMG001 ], etc.
    marker_pattern = re.compile(
        re.escape(IMAGE_MARKER_PREFIX) + r'\s*(\d+)\s*' + re.escape(IMAGE_MARKER_SUFFIX)
    )

    def replace_marker(match):
        """Replace a single marker with its HTML representation."""
        image_id = match.group(1)
        image_info = images_by_id.get(image_id)

        if not image_info:
            # Image not found - keep the marker visible for debugging
            return match.group(0)

        filename = image_info['filename']
        extra_attrs = _build_img_attributes(image_info, is_inline=True)
        if extra_attrs:
            return f'<img src="images/{filename}" alt="" {extra_attrs}/>'
        else:
            return f'<img src="images/{filename}" alt="" class="inline-image"/>'

    return marker_pattern.sub(replace_marker, text)


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


async def create_simple_epub(
    translated_text: str,
    output_path: str,
    metadata: dict,
    target_language: str,
    log_callback=None,
    images: list = None
) -> None:
    """
    Create a standard, generic EPUB 2.0 from translated pure text - RADICAL APPROACH.

    Splits text into readable chapters (auto-pagination by size).
    Creates a clean, valid EPUB structure with optional images.

    Args:
        translated_text: Pure translated text (may contain image markers)
        output_path: Path for output EPUB file
        metadata: Dictionary with title, author, language, identifier
        target_language: Target language code
        log_callback: Optional logging callback
        images: Optional list of image dicts with keys: id, filename, data, media_type, alt
    """
    if images is None:
        images = []

    if log_callback:
        msg = "Fast mode: Building generic EPUB from translated text"
        if images:
            msg += f" with {len(images)} images"
        log_callback("fast_mode_rebuild_start", msg)

    # Build image lookup by ID for quick access
    images_by_id = {img['id']: img for img in images}

    # Split text into chapters (auto-pagination by word count)
    chapters = _auto_split_into_chapters(translated_text, words_per_chapter=5000)

    if log_callback:
        log_callback("fast_mode_chapters_created", f"Fast mode: Created {len(chapters)} chapters")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create EPUB directory structure - FLAT (EPUB 2.0 style, like working EPUBs)
        # Files at root level for maximum compatibility with strict readers
        meta_inf_dir = os.path.join(temp_dir, 'META-INF')
        os.makedirs(meta_inf_dir, exist_ok=True)

        # Create images directory if we have images
        if images:
            images_dir = os.path.join(temp_dir, 'images')
            os.makedirs(images_dir, exist_ok=True)

        # Create mimetype file (MUST be first and uncompressed)
        mimetype_path = os.path.join(temp_dir, 'mimetype')
        async with aiofiles.open(mimetype_path, 'w', encoding='utf-8') as f:
            await f.write('application/epub+zip')

        # Create container.xml (points to content.opf at root)
        container_xml = _create_container_xml()
        container_path = os.path.join(meta_inf_dir, 'container.xml')
        async with aiofiles.open(container_path, 'w', encoding='utf-8') as f:
            await f.write(container_xml)

        # Create CSS file (clean, readable style with image support)
        css_content = _create_simple_css(with_images=bool(images))
        css_path = os.path.join(temp_dir, 'stylesheet.css')
        async with aiofiles.open(css_path, 'w', encoding='utf-8') as f:
            await f.write(css_content)

        # Update metadata with target language BEFORE creating chapters
        metadata['language'] = target_language.lower()[:2] if target_language else metadata.get('language', 'en')

        # Write image files
        for img in images:
            img_path = os.path.join(temp_dir, 'images', img['filename'])
            async with aiofiles.open(img_path, 'wb') as f:
                await f.write(img['data'])

        # Create chapter XHTML files
        chapter_files = []
        for i, chapter_text in enumerate(chapters, 1):
            filename = f'chapter_{i:03d}.xhtml'
            chapter_files.append(filename)

            # Clean translation tags BEFORE creating XHTML
            chapter_text_cleaned = _clean_translation_tags(chapter_text)

            chapter_title = f'Chapter {i}'
            xhtml_content = _create_chapter_xhtml(
                chapter_title,
                chapter_text_cleaned,
                metadata['language'],
                images_by_id=images_by_id
            )
            xhtml_path = os.path.join(temp_dir, filename)
            # Write with proper UTF-8 encoding (no newline parameter for Windows compatibility)
            async with aiofiles.open(xhtml_path, 'w', encoding='utf-8') as f:
                await f.write(xhtml_content)

        # Create content.opf (package document) - EPUB 2.0 format
        opf_content = _create_content_opf(metadata, chapter_files, images=images)
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

            # Add images
            for img in images:
                img_path = os.path.join(temp_dir, 'images', img['filename'])
                epub_zip.write(img_path, f"images/{img['filename']}")

            # Add chapter files in order
            for i, chapter_text in enumerate(chapters, 1):
                filename = f'chapter_{i:03d}.xhtml'
                xhtml_path = os.path.join(temp_dir, filename)
                if os.path.exists(xhtml_path):
                    epub_zip.write(xhtml_path, filename)

    if log_callback:
        msg = f"Fast mode: EPUB created successfully with {len(chapters)} chapters"
        if images:
            msg += f" and {len(images)} images"
        msg += f" at {output_path}"
        log_callback("fast_mode_epub_created", msg)


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


def _create_simple_css(with_images: bool = False) -> str:
    """Create simple, readable CSS with optional image styling."""
    base_css = '''body {
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
}

hr {
    border: none;
    border-top: 1px solid #ccc;
    margin: 2em auto;
    width: 50%;
}

em, i {
    font-style: italic;
}

strong, b {
    font-weight: bold;
}'''

    if with_images:
        base_css += '''

.image-container {
    text-align: center;
    margin: 1.5em 0;
    page-break-inside: avoid;
}

.image-container img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 0 auto;
}

.image-caption {
    font-size: 0.9em;
    color: #666;
    font-style: italic;
    margin-top: 0.5em;
    text-align: center;
    text-indent: 0;
}

/* Inline images within paragraphs */
.inline-image {
    max-height: 1.5em;
    vertical-align: middle;
    display: inline;
    margin: 0 0.2em;
}

/* Larger inline images (standalone in paragraph) */
p > img.inline-image:only-child {
    max-width: 100%;
    max-height: none;
    display: block;
    margin: 0.5em auto;
}'''

    return base_css


def _convert_formatting_markers_to_html(text: str) -> str:
    """
    Convert formatting markers to HTML tags.

    Converts:
    - [I]text[/I] -> <em>text</em>
    - [B]text[/B] -> <strong>text</strong>
    - [HR] -> <hr/>

    This is done AFTER HTML escaping, so the markers are still plain text.

    Args:
        text: Text with formatting markers (already HTML-escaped)

    Returns:
        Text with markers converted to HTML tags
    """
    # Convert italic markers
    text = text.replace(FORMAT_ITALIC_START, '<em>')
    text = text.replace(FORMAT_ITALIC_END, '</em>')

    # Convert bold markers
    text = text.replace(FORMAT_BOLD_START, '<strong>')
    text = text.replace(FORMAT_BOLD_END, '</strong>')

    return text


def _is_hr_marker(text: str) -> bool:
    """Check if text is only a horizontal rule marker."""
    return text.strip() == FORMAT_HR_MARKER


def _create_chapter_xhtml(
    title: str,
    text: str,
    language: str = 'en',
    images_by_id: dict = None
) -> str:
    """
    Create XHTML content for a chapter - EPUB 2.0 format (like working EPUBs).

    Handles image markers in three ways:
    1. Isolated markers (paragraph is only "[IMG001]") -> full image container div
    2. Inline markers (text contains "[IMG001]") -> inline img tag within paragraph
    3. Markers with spaces/variations -> normalized and replaced

    Args:
        title: Chapter title
        text: Chapter text content (may contain image markers)
        language: Language code (e.g., 'en', 'fr')
        images_by_id: Dict mapping image IDs to image info dicts

    Returns:
        Complete XHTML string
    """
    import html as html_module

    if images_by_id is None:
        images_by_id = {}

    title_escaped = html_module.escape(title) if title else "Chapter"

    # Ensure we have text
    text = text.strip() if text else "No content."

    # Split text into paragraphs (separated by blank lines)
    paragraphs = []
    for para in text.split('\n\n'):
        para_stripped = para.strip()
        if para_stripped:
            # Check if this paragraph is ONLY a horizontal rule marker
            if _is_hr_marker(para_stripped):
                paragraphs.append('    <hr/>')
                continue

            # Check if this paragraph is ONLY an image marker (isolated image)
            image_html = _convert_image_marker_to_html(para_stripped, images_by_id)
            if image_html:
                # Isolated image marker -> use full container div
                paragraphs.append(image_html)
            else:
                # Check if paragraph contains any image markers (inline images)
                if has_image_markers(para_stripped) and images_by_id:
                    # First escape HTML, then replace markers with img tags
                    # We need to be careful: escape first, but markers should not be escaped
                    # Solution: replace markers with placeholders, escape, then restore
                    para_with_images = _process_paragraph_with_inline_images(
                        para_stripped, images_by_id
                    )
                    # Convert formatting markers to HTML
                    para_with_images = _convert_formatting_markers_to_html(para_with_images)
                    paragraphs.append(f'    <p>{para_with_images}</p>')
                else:
                    # No image markers - standard text paragraph
                    para_escaped = html_module.escape(para_stripped)
                    # Replace single newlines with <br/> for line breaks (preserves text breathing)
                    para_escaped = para_escaped.replace('\n', '<br/>\n')
                    # Convert formatting markers to HTML
                    para_escaped = _convert_formatting_markers_to_html(para_escaped)
                    paragraphs.append(f'    <p>{para_escaped}</p>')

    # If no paragraphs were created, create at least one
    if not paragraphs:
        paragraphs.append(f'    <p>{html_module.escape(text)}</p>')

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


def _process_paragraph_with_inline_images(text: str, images_by_id: dict) -> str:
    """
    Process a paragraph that contains inline image markers.

    Escapes HTML in the text while preserving and converting image markers
    to proper img tags. Preserves original display attributes.

    Args:
        text: Paragraph text with image markers
        images_by_id: Dict mapping image IDs to image info dicts

    Returns:
        HTML-safe paragraph content with img tags
    """
    import html as html_module

    # Pattern to match image markers with optional whitespace inside
    marker_pattern = re.compile(
        re.escape(IMAGE_MARKER_PREFIX) + r'\s*(\d+)\s*' + re.escape(IMAGE_MARKER_SUFFIX)
    )

    # Split text by image markers, keeping the markers
    parts = marker_pattern.split(text)
    # parts will be: [text_before, id1, text_between, id2, text_after, ...]

    result_parts = []
    i = 0
    while i < len(parts):
        if i % 2 == 0:
            # This is text content - escape it
            text_part = parts[i]
            if text_part:
                escaped = html_module.escape(text_part)
                # Replace single newlines with <br/> for line breaks
                escaped = escaped.replace('\n', '<br/>\n')
                result_parts.append(escaped)
        else:
            # This is an image ID - convert to img tag
            image_id = parts[i]
            image_info = images_by_id.get(image_id)
            if image_info:
                filename = image_info['filename']
                extra_attrs = _build_img_attributes(image_info, is_inline=True)
                if extra_attrs:
                    result_parts.append(f'<img src="images/{filename}" alt="" {extra_attrs}/>')
                else:
                    result_parts.append(f'<img src="images/{filename}" alt="" class="inline-image"/>')
            else:
                # Image not found - keep the original marker (escaped)
                result_parts.append(html_module.escape(f"{IMAGE_MARKER_PREFIX}{image_id}{IMAGE_MARKER_SUFFIX}"))
        i += 1

    return ''.join(result_parts)


def _convert_image_marker_to_html(text: str, images_by_id: dict) -> str:
    """
    Convert an image marker to HTML img tag for block-level display.

    Preserves original display attributes (width, height, style, class).

    Args:
        text: Text that may be an image marker (e.g., "[IMG001]")
        images_by_id: Dict mapping image IDs to image info dicts

    Returns:
        HTML string for the image, or empty string if not an image marker
    """
    # Normalize text: remove all whitespace (LLM sometimes adds spaces inside markers)
    # e.g., "[IMG 005]" -> "[IMG005]"
    normalized_text = re.sub(r'\s+', '', text.strip())

    # Check if text is an image marker
    marker_pattern = re.compile(
        re.escape(IMAGE_MARKER_PREFIX) + r'(\d+)' + re.escape(IMAGE_MARKER_SUFFIX)
    )
    match = marker_pattern.fullmatch(normalized_text)

    if not match:
        return ''

    image_id = match.group(1)
    image_info = images_by_id.get(image_id)

    if not image_info:
        return ''

    filename = image_info['filename']

    # Build attributes from preserved display settings
    extra_attrs = _build_img_attributes(image_info, is_inline=False)
    if extra_attrs:
        img_tag = f'<img src="images/{filename}" alt="" {extra_attrs}/>'
    else:
        img_tag = f'<img src="images/{filename}" alt=""/>'

    # Create image HTML with container div for styling (no caption)
    return f'''    <div class="image-container">
      {img_tag}
    </div>'''


def _create_content_opf(metadata: dict, chapter_files: list, images: list = None) -> str:
    """
    Create content.opf file content with translation signature.

    Args:
        metadata: Dictionary with title, author, language, identifier
        chapter_files: List of chapter filenames
        images: Optional list of image dicts with keys: id, filename, media_type

    Returns:
        Complete OPF XML string
    """
    import html
    from src.config import SIGNATURE_ENABLED, PROJECT_NAME, PROJECT_GITHUB

    if images is None:
        images = []

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

    # Add images to manifest
    for img in images:
        img_id = f"img{img['id']}"
        img_href = f"images/{img['filename']}"
        media_type = img['media_type']
        manifest_items.append(f'    <item id="{img_id}" href="{img_href}" media-type="{media_type}"/>')

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
    resume_from_index: int = 0,
    has_images: bool = False
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
        has_images: If True, includes image placeholder preservation instructions in prompts

    Returns:
        Translated text string
    """
    if log_callback:
        log_callback("fast_mode_text_translation_start",
                    f"Fast mode: Translating text from {source_language} to {target_language}")

    # Split text into chunks (uses token-based or line-based based on config)
    structured_chunks = split_text_into_chunks(text)
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
    # IMPORTANT: Pass fast_mode=True to use simplified prompts without HTML/XML placeholder instructions
    # If has_images=True, the prompt will include image marker preservation instructions
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
        resume_from_index=resume_from_index,
        has_images=has_images  # Pass image flag to include image marker preservation in prompt
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
