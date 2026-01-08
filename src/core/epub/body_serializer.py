"""
Body serialization for simplified EPUB processing

This module handles extracting and replacing the content of <body> elements
in XHTML documents, enabling full-document translation instead of per-element processing.
"""
from lxml import etree
from typing import Tuple, Optional
import re


def normalize_whitespace(html: str) -> str:
    """
    Normalize excessive whitespace in HTML content while preserving structural breaks.

    This handles the common case where EPUB source files have arbitrary line breaks
    and indentation that are just formatting artifacts, not meaningful content.

    For example, transforms:
        "La technologie est en constante évolution.
            Au fur et à mesure que les ordinateurs"
    Into:
        "La technologie est en constante évolution. Au fur et à mesure que les ordinateurs"

    But preserves structural breaks by injecting newlines after block-level closing tags.

    Rules:
    - Normalize whitespace only WITHIN text content (inside paragraphs, etc.)
    - Inject newlines after closing block tags (</p>, </li>, </div>, etc.)
    - Preserve content inside <pre>, <code>, <script>, <style> tags unchanged
    - Preserve <br> and <br/> tags (they represent intentional line breaks)

    Args:
        html: Raw HTML string with potential excessive whitespace

    Returns:
        HTML with normalized whitespace
    """
    # Protect content in preformatted tags by replacing with placeholders
    preserved_blocks = []

    def preserve_block(match):
        preserved_blocks.append(match.group(0))
        return f"__PRESERVED_BLOCK_{len(preserved_blocks) - 1}__"

    # Preserve <pre>, <code>, <script>, <style> blocks (case insensitive)
    html = re.sub(
        r'<(pre|code|script|style)[^>]*>.*?</\1>',
        preserve_block,
        html,
        flags=re.DOTALL | re.IGNORECASE
    )

    # Preserve <br> tags (they represent intentional line breaks)
    html = re.sub(r'<br\s*/?\s*>', preserve_block, html, flags=re.IGNORECASE)

    # Step 1: Normalize line endings
    html = html.replace('\r\n', '\n').replace('\r', '\n')

    # Step 2: Inject newlines after block-level closing tags
    # This ensures structural separation is maintained even if source has no newlines
    block_tags = r'</(?:p|div|li|h[1-6]|blockquote|section|article|header|footer|nav|aside|ol|ul|table|tr|td|th|dt|dd)>'
    html = re.sub(f'({block_tags})[ \t]*', r'\1\n', html, flags=re.IGNORECASE)

    # Step 3: Replace remaining single newlines (within text content) with a single space
    # But preserve newlines that are right after a closing tag (just added in step 2)
    # Pattern: newline NOT preceded by > (closing tag)
    html = re.sub(r'(?<!>)[ \t]*\n(?!\n)[ \t]*', ' ', html)

    # Step 4: Collapse multiple spaces into one
    html = re.sub(r' {2,}', ' ', html)

    # Step 5: Clean up whitespace around newlines
    html = re.sub(r' \n', '\n', html)  # Remove space before newline
    html = re.sub(r'\n ', '\n', html)  # Remove space after newline

    # Restore preserved blocks
    for i, block in enumerate(preserved_blocks):
        html = html.replace(f"__PRESERVED_BLOCK_{i}__", block)

    return html


def extract_body_html(
    doc_root: etree._Element,
    normalize: bool = True
) -> Tuple[str, Optional[etree._Element]]:
    """
    Extract the HTML content of <body> as a string.

    Args:
        doc_root: Root of the parsed XHTML document
        normalize: If True, normalize excessive whitespace (default: True)

    Returns:
        Tuple (body_inner_html, body_element)
        Returns ("", None) if no body element found
    """
    # Try XHTML namespace first, then fallback to no namespace
    body = doc_root.find('.//{http://www.w3.org/1999/xhtml}body')
    if body is None:
        body = doc_root.find('.//body')

    if body is None:
        return "", None

    # Serialize the inner content of body (without the <body> tag itself)
    inner_html = etree.tostring(body, encoding='unicode', method='html')

    # Remove the outer <body> tags
    # <body class="x">content</body> → content
    inner_html = re.sub(r'^<body[^>]*>', '', inner_html)
    inner_html = re.sub(r'</body>$', '', inner_html)

    inner_html = inner_html.strip()

    # Normalize whitespace to remove arbitrary line breaks from source formatting
    if normalize:
        inner_html = normalize_whitespace(inner_html)

    return inner_html, body


def replace_body_content(body_element: etree._Element, new_html: str) -> None:
    """
    Replace the content of <body> with new translated HTML.

    Args:
        body_element: The <body> element to modify
        new_html: New translated HTML content
    """
    # Clear the body
    body_element.text = None
    for child in list(body_element):
        body_element.remove(child)

    # Parse the new content
    # Wrap in a temp element to handle multiple root elements
    wrapped = f"<temp xmlns='http://www.w3.org/1999/xhtml'>{new_html}</temp>"
    parser = etree.XMLParser(recover=True, encoding='utf-8')

    try:
        temp = etree.fromstring(wrapped.encode('utf-8'), parser)
    except etree.XMLSyntaxError:
        # Fallback: try without namespace
        wrapped = f"<temp>{new_html}</temp>"
        temp = etree.fromstring(wrapped.encode('utf-8'), parser)

    # Copy content into body
    body_element.text = temp.text
    for child in temp:
        body_element.append(child)
