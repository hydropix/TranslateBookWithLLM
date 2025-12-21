"""
Translation job collection for EPUB files

This module analyzes EPUB content and creates translation jobs for each
translatable text segment, handling block elements, inline tags, and text nodes.
"""
from typing import List, Dict, Any, Optional, Callable
from lxml import etree

from .xml_helpers import safe_get_tag, safe_iter_children, serialize_inline_tags
from .tag_preservation import TagPreserver
from ..text_processor import split_text_into_chunks


def collect_translation_jobs(
    element: etree._Element,
    file_path_abs: str,
    jobs_list: List[Dict[str, Any]],
    chunk_size: int,
    ignored_tags: set,
    content_block_tags: set,
    log_callback: Optional[Callable] = None
) -> None:
    """
    Recursively collect translation jobs from EPUB elements

    This function walks the XML tree and identifies translatable text segments.
    It handles three types of content:
    - Block content (paragraphs, divs): translated as complete units
    - Direct text: text nodes within elements
    - Tail text: text following inline elements

    Args:
        element: lxml element to process
        file_path_abs: Absolute file path for reference
        jobs_list: List to append jobs to (modified in place)
        chunk_size: Target chunk size for splitting large texts
        ignored_tags: Set of tag names to skip
        content_block_tags: Set of block-level tags
        log_callback: Optional logging callback
    """
    element_tag = safe_get_tag(element)

    # Skip ignored tags (script, style, meta, etc.)
    if element_tag in ignored_tags:
        return

    if element_tag in content_block_tags:
        # Check if this block element contains other block elements
        has_block_children = any(
            safe_get_tag(child) in content_block_tags
            for child in safe_iter_children(element)
        )

        if has_block_children:
            # If it has block children, don't process as a single block
            # Instead, process only direct text if any
            if element.text and element.text.strip():
                _add_text_job(
                    jobs_list,
                    element,
                    element.text,
                    'text',
                    file_path_abs,
                    chunk_size
                )
        else:
            # No block children, process entire content as a block
            # Use the serialization function to preserve inline tags
            text_content_for_chunking = serialize_inline_tags(element, preserve_tags=True).strip()

            # Filter out any object representations that might have leaked through
            if ' at 0x' in text_content_for_chunking:
                import re
                text_content_for_chunking = re.sub(
                    r'<[^>]*at 0x[0-9A-Fa-f]+>',
                    '',
                    text_content_for_chunking
                ).strip()

            if text_content_for_chunking:
                _add_block_content_job(
                    jobs_list,
                    element,
                    text_content_for_chunking,
                    file_path_abs,
                    chunk_size
                )
            # For block elements without block children, don't process children
            return
    else:
        # Non-block element: process direct text if present
        if element.text:
            text_to_translate = element.text.strip()
            if text_to_translate:
                _add_text_job(
                    jobs_list,
                    element,
                    element.text,
                    'text',
                    file_path_abs,
                    chunk_size
                )

    # Recursive processing of children
    for child in safe_iter_children(element):
        collect_translation_jobs(
            child,
            file_path_abs,
            jobs_list,
            chunk_size,
            ignored_tags,
            content_block_tags,
            log_callback
        )

    # Handle tail text for non-block elements
    if element_tag not in content_block_tags and element.tail:
        tail_to_translate = element.tail.strip()
        if tail_to_translate:
            _add_text_job(
                jobs_list,
                element,
                element.tail,
                'tail',
                file_path_abs,
                chunk_size
            )


def _add_text_job(
    jobs_list: List[Dict[str, Any]],
    element: etree._Element,
    original_text: str,
    job_type: str,
    file_path: str,
    chunk_size: int
) -> None:
    """
    Add a text translation job to the jobs list

    Args:
        jobs_list: List to append job to
        element: Element reference
        original_text: Original text content (with whitespace)
        job_type: Either 'text' or 'tail'
        file_path: File path for reference
        chunk_size: Target chunk size
    """
    text_to_translate = original_text.strip()
    if not text_to_translate:
        return

    # Preserve leading/trailing whitespace
    leading_space = original_text[:len(original_text) - len(original_text.lstrip())]
    trailing_space = original_text[len(original_text.rstrip()):]

    # Split into chunks (uses token-based or line-based based on config)
    sub_chunks = split_text_into_chunks(text_to_translate)
    if not sub_chunks and text_to_translate:
        sub_chunks = [{"context_before": "", "main_content": text_to_translate, "context_after": ""}]

    if sub_chunks:
        jobs_list.append({
            'element_ref': element,
            'type': job_type,
            'original_text_stripped': text_to_translate,
            'sub_chunks': sub_chunks,
            'leading_space': leading_space,
            'trailing_space': trailing_space,
            'file_path': file_path,
            'translated_text': None
        })


def _add_block_content_job(
    jobs_list: List[Dict[str, Any]],
    element: etree._Element,
    text_content: str,
    file_path: str,
    chunk_size: int
) -> None:
    """
    Add a block content translation job with tag preservation

    Block content may contain inline tags like <em>, <strong>, etc.
    These are preserved using placeholders during translation.

    Args:
        jobs_list: List to append job to
        element: Element reference
        text_content: Text content with inline tags
        file_path: File path for reference
        chunk_size: Target chunk size
    """
    # Create tag preserver instance
    tag_preserver = TagPreserver()

    # Replace tags with placeholders
    text_with_placeholders, tag_map = tag_preserver.preserve_tags(text_content)

    # Split into chunks (uses token-based or line-based based on config)
    sub_chunks = split_text_into_chunks(text_with_placeholders)
    if not sub_chunks and text_with_placeholders:
        sub_chunks = [{"context_before": "", "main_content": text_with_placeholders, "context_after": ""}]

    if sub_chunks:
        jobs_list.append({
            'element_ref': element,
            'type': 'block_content',
            'original_text_stripped': text_content,
            'text_with_placeholders': text_with_placeholders,
            'tag_map': tag_map,
            'sub_chunks': sub_chunks,
            'file_path': file_path,
            'translated_text': None,
            'has_inline_tags': True  # Flag to indicate this content has inline tags
        })
