"""
EPUB processing module for specialized e-book translation
"""
import os
import zipfile
import tempfile
import html
import aiofiles
from lxml import etree
from tqdm.auto import tqdm

from src.config import (
    NAMESPACES, IGNORED_TAGS_EPUB, CONTENT_BLOCK_TAGS_EPUB,
    DEFAULT_MODEL, MAIN_LINES_PER_CHUNK, API_ENDPOINT
)
from .text_processor import split_text_into_chunks_with_context
from .translator import generate_translation_request, post_process_translation
from .post_processor import clean_residual_tag_placeholders
import re
import hashlib
import json


class EPUBProcessor:
    """Handles EPUB-specific processing for audio conversion"""
    
    def __init__(self):
        self.namespaces = NAMESPACES
    
    async def extract_chapters_for_audio(self, epub_path: str) -> dict:
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


def safe_iter_children(element):
    """
    Safely iterate over element children, handling different lxml/Cython versions
    
    Args:
        element: lxml element
        
    Yields:
        child elements
    """
    try:
        # Try normal iteration first
        for child in element:
            yield child
    except TypeError:
        # If that fails, try alternative methods
        try:
            # Try getchildren() (deprecated but might work)
            if hasattr(element, 'getchildren'):
                for child in element.getchildren():
                    yield child
            else:
                # Try converting to list
                children = list(element)
                for child in children:
                    yield child
        except:
            # If all else fails, use xpath
            try:
                for child in element.xpath('*'):
                    yield child
            except:
                # Give up - no children accessible
                pass


def safe_get_tag(element):
    """
    Safely get the tag of an element, handling cases where it might be a method
    
    Args:
        element: lxml element
        
    Returns:
        str: The tag name
    """
    try:
        # First try: direct access
        tag = element.tag
        if isinstance(tag, str):
            return tag
            
        # Second try: call if it's a method
        if callable(tag):
            tag_result = tag()
            if isinstance(tag_result, str):
                return tag_result
        
        # Third try: use etree.tostring to extract tag name
        try:
            # Get element as string
            elem_str = etree.tostring(element, encoding='unicode', method='xml')
            # Extract tag name from string (e.g., "<p class='bull'>..." -> "p")
            import re
            match = re.match(r'<([^>\s]+)', elem_str)
            if match:
                tag_with_ns = match.group(1)
                # Handle namespaced tags
                if '}' in tag_with_ns:
                    return tag_with_ns  # Return full namespaced tag
                else:
                    # Add namespace if element has one
                    if hasattr(element, 'nsmap') and None in element.nsmap:
                        return f"{{{element.nsmap[None]}}}{tag_with_ns}"
                    return tag_with_ns
        except:
            pass
            
        # Fourth try: Use QName if element has it
        try:
            if hasattr(element, 'qname'):
                return str(element.qname)
        except:
            pass
            
        return ""
    except:
        return ""


def safe_get_attrib(element):
    """
    Safely get the attributes of an element
    
    Args:
        element: lxml element
        
    Returns:
        dict: The attributes dictionary
    """
    try:
        attrib = element.attrib
        if callable(attrib):
            return attrib()
        return attrib
    except:
        return {}


class TagPreserver:
    """
    Preserves HTML/XML tags during translation by replacing them with simple placeholders
    """
    def __init__(self):
        self.tag_map = {}
        self.counter = 0
        self.placeholder_prefix = "⟦TAG"
        self.placeholder_suffix = "⟧"
    
    def preserve_tags(self, text):
        """
        Replace HTML/XML tags with simple placeholders
        
        Args:
            text: Text containing HTML/XML tags
            
        Returns:
            tuple: (processed_text, tag_map)
        """
        # Reset for new text
        self.tag_map = {}
        self.counter = 0
        
        # Pattern to match any HTML/XML tag (opening, closing, or self-closing)
        tag_pattern = r'<[^>]+>'
        
        def replace_tag(match):
            tag = match.group(0)
            # Create a simple placeholder
            placeholder = f"{self.placeholder_prefix}{self.counter}{self.placeholder_suffix}"
            self.tag_map[placeholder] = tag
            self.counter += 1
            return placeholder
        
        # Replace all tags with placeholders
        processed_text = re.sub(tag_pattern, replace_tag, text)
        
        return processed_text, self.tag_map.copy()
    
    def restore_tags(self, text, tag_map):
        """
        Restore HTML/XML tags from placeholders
        
        Args:
            text: Text with placeholders
            tag_map: Dictionary mapping placeholders to original tags
            
        Returns:
            str: Text with restored tags
        """
        restored_text = text
        
        # Sort placeholders by reverse order to avoid partial replacements
        placeholders = sorted(tag_map.keys(), key=lambda x: int(x[len(self.placeholder_prefix):-len(self.placeholder_suffix)]), reverse=True)
        
        for placeholder in placeholders:
            if placeholder in restored_text:
                restored_text = restored_text.replace(placeholder, tag_map[placeholder])
        
        return restored_text
    
    def validate_placeholders(self, text, tag_map):
        """
        Validate that all expected placeholders are present in the text
        
        Args:
            text: Text to validate
            tag_map: Dictionary mapping placeholders to original tags
            
        Returns:
            tuple: (is_valid, missing_placeholders, mutated_placeholders)
        """
        missing_placeholders = []
        mutated_placeholders = []
        
        for placeholder in tag_map.keys():
            if placeholder not in text:
                missing_placeholders.append(placeholder)
                
                # Check for common mutations
                # Extract tag number
                tag_num = placeholder[len(self.placeholder_prefix):-len(self.placeholder_suffix)]
                
                # Check various mutation patterns
                mutations = [
                    f"[[TAG{tag_num}]]",  # Double brackets
                    f"[TAG{tag_num}]",    # Single brackets
                    f"{{TAG{tag_num}}}",  # Curly braces
                    f"<TAG{tag_num}>",    # Angle brackets
                    f"TAG{tag_num}",      # No brackets (check last to avoid false positives)
                    f"⟦TAG{tag_num}⟧",    # Unicode brackets (in case of encoding issues)
                ]
                
                for mutation in mutations:
                    if mutation in text:
                        mutated_placeholders.append((placeholder, mutation))
                        break
        
        is_valid = len(missing_placeholders) == 0 and len(mutated_placeholders) == 0
        return is_valid, missing_placeholders, mutated_placeholders
    
    def fix_mutated_placeholders(self, text, mutated_placeholders):
        """
        Attempt to fix common placeholder mutations
        
        Args:
            text: Text with mutated placeholders
            mutated_placeholders: List of (original, mutated) placeholder pairs
            
        Returns:
            str: Text with fixed placeholders
        """
        fixed_text = text
        for original, mutated in mutated_placeholders:
            fixed_text = fixed_text.replace(mutated, original)
        return fixed_text


def _get_node_text_content_with_br_as_newline(node):
    """
    Extract text content from XML/HTML node with <br> handling
    
    Args:
        node: lxml element node
        
    Returns:
        str: Extracted text with <br> tags converted to newlines
    """
    parts = []
    if node.text:
        parts.append(node.text)

    for child in safe_iter_children(node):
        child_qname_str = safe_get_tag(child)
        
        # Skip if we couldn't get a valid tag
        if not child_qname_str or ' at 0x' in str(child_qname_str):
            # Try to get text content anyway
            try:
                if hasattr(child, 'text') and child.text:
                    parts.append(child.text)
                if hasattr(child, 'tail') and child.tail:
                    parts.append(child.tail)
            except:
                pass
            continue
            
        br_xhtml_tag = etree.QName(NAMESPACES['xhtml'], 'br').text

        if child_qname_str == br_xhtml_tag:
            if not (parts and (parts[-1].endswith('\n') or parts[-1] == '\n')):
                parts.append('\n')
        elif child_qname_str in CONTENT_BLOCK_TAGS_EPUB:
            if parts and parts[-1] and not parts[-1].endswith('\n'):
                parts.append('\n')
        else:
            parts.append(_get_node_text_content_with_br_as_newline(child))

        if child.tail:
            parts.append(child.tail)

    return "".join(parts)


def _serialize_inline_tags(node, preserve_tags=True):
    """
    Serialize XML/HTML node content while preserving or removing inline tags
    
    Args:
        node: lxml element node
        preserve_tags: If True, preserve inline tags as XML strings
        
    Returns:
        str: Serialized content with tags preserved or removed
    """
    # Use lxml's built-in method first, then clean up
    try:
        if preserve_tags:
            # Get the full XML content
            content = etree.tostring(node, encoding='unicode', method='xml', pretty_print=False)
            # Remove the outer tag
            import re
            # Match opening tag
            match = re.match(r'^<[^>]+>', content)
            if match:
                opening_tag_len = len(match.group(0))
                # Find closing tag from the end
                closing_match = re.search(r'</[^>]+>$', content)
                if closing_match:
                    closing_tag_start = closing_match.start()
                    # Extract inner content
                    inner_content = content[opening_tag_len:closing_tag_start]
                    return inner_content
            return content
        else:
            # Get text content only
            return etree.tostring(node, encoding='unicode', method='text')
    except Exception as e:
        # Fallback to manual serialization
        parts = []
        
        if hasattr(node, 'text') and node.text:
            parts.append(node.text)
        
        try:
            for child in node:
                # Get child content
                child_content = etree.tostring(child, encoding='unicode', method='xml')
                if child_content and ' at 0x' not in child_content:
                    parts.append(child_content)
        except:
            pass
        
        return "".join(parts)


def _rebuild_element_from_translated_content(element, translated_content):
    """
    Rebuild element structure from translated content containing inline tags
    
    Args:
        element: lxml element to rebuild
        translated_content: Translated text with preserved XML tags
    """
    # Clear existing content
    element.text = None
    element.tail = None
    for child in list(element):
        element.remove(child)
    
    # Parse the translated content as XML fragment
    try:
        # Wrap content in a temporary root to handle mixed content
        wrapped_content = f"<temp_root>{translated_content}</temp_root>"
        
        # Parse with recovery mode to handle potential issues
        parser = etree.XMLParser(recover=True, encoding='utf-8')
        temp_root = etree.fromstring(wrapped_content.encode('utf-8'), parser)
        
        # Copy content from temp root to element
        element.text = temp_root.text
        
        # Add all children from temp root
        for child in safe_iter_children(temp_root):
            # Create new element with the same tag and attributes
            new_child = etree.SubElement(element, safe_get_tag(child), attrib=dict(safe_get_attrib(child)))
            new_child.text = child.text
            new_child.tail = child.tail
            
            # Recursively copy any nested children
            _copy_element_children(child, new_child)
            
    except Exception as e:
        # Fallback: if parsing fails, just set as text
        element.text = translated_content


def _copy_element_children(source, target):
    """
    Recursively copy children from source element to target element
    
    Args:
        source: Source lxml element
        target: Target lxml element
    """
    for child in safe_iter_children(source):
        new_child = etree.SubElement(target, safe_get_tag(child), attrib=dict(safe_get_attrib(child)))
        new_child.text = child.text
        new_child.tail = child.tail
        _copy_element_children(child, new_child)


def _collect_epub_translation_jobs_recursive(element, file_path_abs, jobs_list, chunk_size, log_callback=None):
    """
    Recursively collect translation jobs from EPUB elements
    
    Args:
        element: lxml element to process
        file_path_abs (str): Absolute file path
        jobs_list (list): List to append jobs to
        chunk_size (int): Target chunk size
        log_callback (callable): Logging callback
    """
    element_tag = safe_get_tag(element)
    if element_tag in IGNORED_TAGS_EPUB:
        return
    

    if element_tag in CONTENT_BLOCK_TAGS_EPUB:
        # Check if this block element contains other block elements
        has_block_children = any(safe_get_tag(child) in CONTENT_BLOCK_TAGS_EPUB for child in safe_iter_children(element))
        
        if has_block_children:
            # If it has block children, don't process as a single block
            # Instead, process only direct text if any
            if element.text and element.text.strip():
                original_text_content = element.text
                text_to_translate = original_text_content.strip()
                leading_space = original_text_content[:len(original_text_content) - len(original_text_content.lstrip())]
                trailing_space = original_text_content[len(original_text_content.rstrip()):]
                sub_chunks = split_text_into_chunks_with_context(text_to_translate, chunk_size)
                if not sub_chunks and text_to_translate:
                    sub_chunks = [{"context_before": "", "main_content": text_to_translate, "context_after": ""}]

                if sub_chunks:
                    jobs_list.append({
                        'element_ref': element,
                        'type': 'text',
                        'original_text_stripped': text_to_translate,
                        'sub_chunks': sub_chunks,
                        'leading_space': leading_space,
                        'trailing_space': trailing_space,
                        'file_path': file_path_abs,
                        'translated_text': None
                    })
        else:
            # No block children, process entire content as a block
            # Use the new function to preserve inline tags
            text_content_for_chunking = _serialize_inline_tags(element, preserve_tags=True).strip()
            
            # Filter out any object representations that might have leaked through
            if ' at 0x' in text_content_for_chunking:
                # Remove object representations like "<...at 0x...>"
                import re
                text_content_for_chunking = re.sub(r'<[^>]*at 0x[0-9A-Fa-f]+>', '', text_content_for_chunking).strip()
            
            if text_content_for_chunking:
                # Create tag preserver instance
                tag_preserver = TagPreserver()
                # Replace tags with placeholders
                text_with_placeholders, tag_map = tag_preserver.preserve_tags(text_content_for_chunking)
                
                sub_chunks = split_text_into_chunks_with_context(text_with_placeholders, chunk_size)
                if not sub_chunks and text_with_placeholders:
                    sub_chunks = [{"context_before": "", "main_content": text_with_placeholders, "context_after": ""}]

                if sub_chunks:
                    jobs_list.append({
                        'element_ref': element,
                        'type': 'block_content',
                        'original_text_stripped': text_content_for_chunking,
                        'text_with_placeholders': text_with_placeholders,
                        'tag_map': tag_map,
                        'sub_chunks': sub_chunks,
                        'file_path': file_path_abs,
                        'translated_text': None,
                        'has_inline_tags': True  # Flag to indicate this content has inline tags
                    })
            # For block elements without block children, don't process children
            return
    else:
        if element.text:
            original_text_content = element.text
            text_to_translate = original_text_content.strip()
            if text_to_translate:
                leading_space = original_text_content[:len(original_text_content) - len(original_text_content.lstrip())]
                trailing_space = original_text_content[len(original_text_content.rstrip()):]
                sub_chunks = split_text_into_chunks_with_context(text_to_translate, chunk_size)
                if not sub_chunks and text_to_translate:
                    sub_chunks = [{"context_before": "", "main_content": text_to_translate, "context_after": ""}]

                if sub_chunks:
                    jobs_list.append({
                        'element_ref': element,
                        'type': 'text',
                        'original_text_stripped': text_to_translate,
                        'sub_chunks': sub_chunks,
                        'leading_space': leading_space,
                        'trailing_space': trailing_space,
                        'file_path': file_path_abs,
                        'translated_text': None
                    })

    # Recursive processing of children
    for child in safe_iter_children(element):
        _collect_epub_translation_jobs_recursive(child, file_path_abs, jobs_list, chunk_size, log_callback)

    # Handle tail text for non-block elements
    if element_tag not in CONTENT_BLOCK_TAGS_EPUB and element.tail:
        original_tail_content = element.tail
        tail_to_translate = original_tail_content.strip()
        if tail_to_translate:
            leading_space_tail = original_tail_content[:len(original_tail_content) - len(original_tail_content.lstrip())]
            trailing_space_tail = original_tail_content[len(original_tail_content.rstrip()):]
            sub_chunks = split_text_into_chunks_with_context(tail_to_translate, chunk_size)
            if not sub_chunks and tail_to_translate:
                sub_chunks = [{"context_before": "", "main_content": tail_to_translate, "context_after": ""}]

            if sub_chunks:
                jobs_list.append({
                    'element_ref': element,
                    'type': 'tail',
                    'original_text_stripped': tail_to_translate,
                    'sub_chunks': sub_chunks,
                    'leading_space': leading_space_tail,
                    'trailing_space': trailing_space_tail,
                    'file_path': file_path_abs,
                    'translated_text': None
                })


async def translate_epub_chunks_with_context(chunks, source_language, target_language, model_name, 
                                           llm_client, previous_context, log_callback=None, 
                                           check_interruption_callback=None, custom_instructions="",
                                           enable_post_processing=False, post_processing_instructions=""):
    """
    Translate EPUB chunks with previous translation context for consistency
    
    Args:
        chunks (list): List of chunk dictionaries
        source_language (str): Source language
        target_language (str): Target language
        model_name (str): LLM model name
        api_endpoint (str): API endpoint
        previous_context (str): Previous translation for context
        log_callback (callable): Logging callback
        check_interruption_callback (callable): Interruption check callback
        custom_instructions (str): Additional translation instructions
        
    Returns:
        list: List of translated chunks
    """
    import asyncio
    
    total_chunks = len(chunks)
    translated_parts = []
    
    for i, chunk_data in enumerate(chunks):
        if check_interruption_callback and check_interruption_callback():
            if log_callback: 
                log_callback("epub_translation_interrupted", f"EPUB translation process for chunk {i+1}/{total_chunks} interrupted by user signal.")
            break

        main_content_to_translate = chunk_data["main_content"]
        context_before_text = chunk_data["context_before"]
        context_after_text = chunk_data["context_after"]

        if not main_content_to_translate.strip():
            translated_parts.append(main_content_to_translate)
            continue

        # Extract placeholders from the source text for validation
        import re
        placeholder_pattern = r'⟦TAG\d+⟧'
        source_placeholders = set(re.findall(placeholder_pattern, main_content_to_translate))
        
        translated_chunk_text = await generate_translation_request(
            main_content_to_translate, context_before_text, context_after_text,
            previous_context, source_language, target_language,
            model_name, llm_client=llm_client, log_callback=log_callback,
            custom_instructions=custom_instructions
        )

        if translated_chunk_text is not None:
            # Validate placeholders after translation if any exist
            if source_placeholders:
                translated_placeholders = set(re.findall(placeholder_pattern, translated_chunk_text))
                missing_after_translation = source_placeholders - translated_placeholders
                
                if missing_after_translation:
                    if log_callback:
                        log_callback("epub_translation_missing_placeholders", 
                                   f"Translation missing placeholders: {missing_after_translation}")
                    
                    # Retry translation with stronger instructions
                    retry_instructions = (f"{custom_instructions}\n\n"
                                        f"CRITICAL: You MUST preserve ALL placeholder tags exactly as they appear. "
                                        f"Tags like {', '.join(sorted(source_placeholders))} must remain UNCHANGED in your translation.")
                    
                    retry_text = await generate_translation_request(
                        main_content_to_translate, context_before_text, context_after_text,
                        previous_context, source_language, target_language,
                        model_name, llm_client=llm_client, log_callback=log_callback,
                        custom_instructions=retry_instructions
                    )
                    
                    if retry_text is not None:
                        retry_placeholders = set(re.findall(placeholder_pattern, retry_text))
                        if not (source_placeholders - retry_placeholders):  # All placeholders present
                            translated_chunk_text = retry_text
                            if log_callback:
                                log_callback("epub_translation_retry_successful", 
                                           "Translation retry successful - placeholders preserved")
            
            # Apply post-processing if enabled
            if enable_post_processing:
                if log_callback:
                    log_callback("post_processing_epub_chunk", f"Post-processing EPUB chunk {i+1}/{total_chunks}")
                
                # Create a temporary tag_map for validation
                temp_tag_map = {placeholder: f"<tag{i}>" for i, placeholder in enumerate(source_placeholders)}
                
                improved_text = await post_process_translation(
                    translated_chunk_text,
                    target_language,
                    model_name,
                    llm_client=llm_client,
                    log_callback=log_callback,
                    custom_instructions=post_processing_instructions,
                    tag_map=temp_tag_map if temp_tag_map else None
                )
                
                # The post_process_translation function already handles validation and retry internally
                # So we just use the result
                translated_chunk_text = improved_text
            
            translated_parts.append(translated_chunk_text)
        else:
            err_msg_chunk = f"ERROR translating EPUB chunk {i+1}. Original content preserved."
            if log_callback: 
                log_callback("epub_chunk_translation_error", err_msg_chunk)
            error_placeholder = f"[TRANSLATION_ERROR EPUB CHUNK {i+1}]\n{main_content_to_translate}\n[/TRANSLATION_ERROR EPUB CHUNK {i+1}]"
            translated_parts.append(error_placeholder)

    return translated_parts


async def translate_epub_file(input_filepath, output_filepath,
                              source_language="English", target_language="French",
                              model_name=DEFAULT_MODEL, chunk_target_lines_arg=MAIN_LINES_PER_CHUNK,
                              cli_api_endpoint=API_ENDPOINT,
                              progress_callback=None, log_callback=None, stats_callback=None,
                              check_interruption_callback=None, custom_instructions="",
                              llm_provider="ollama", gemini_api_key=None,
                              enable_post_processing=False, post_processing_instructions=""):
    """
    Translate an EPUB file
    
    Args:
        input_filepath (str): Path to input EPUB
        output_filepath (str): Path to output EPUB
        source_language (str): Source language
        target_language (str): Target language
        model_name (str): LLM model name
        chunk_target_lines_arg (int): Target lines per chunk
        cli_api_endpoint (str): API endpoint
        progress_callback (callable): Progress callback
        log_callback (callable): Logging callback
        stats_callback (callable): Statistics callback
        check_interruption_callback (callable): Interruption check callback
    """
    if not os.path.exists(input_filepath):
        err_msg = f"ERROR: Input EPUB file '{input_filepath}' not found."
        if log_callback: 
            log_callback("epub_input_file_not_found", err_msg)
        else: 
            print(err_msg)
        return

    all_translation_jobs = []
    parsed_xhtml_docs = {}

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Extract EPUB
            with zipfile.ZipFile(input_filepath, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # Find OPF file
            opf_path = None
            for root_dir, _, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith('.opf'):
                        opf_path = os.path.join(root_dir, file)
                        break
                if opf_path: 
                    break
            if not opf_path: 
                raise FileNotFoundError("CRITICAL ERROR: content.opf not found in EPUB.")

            # Parse OPF
            opf_tree = etree.parse(opf_path)
            opf_root = opf_tree.getroot()

            manifest = opf_root.find('.//opf:manifest', namespaces=NAMESPACES)
            spine = opf_root.find('.//opf:spine', namespaces=NAMESPACES)
            if manifest is None or spine is None: 
                raise ValueError("CRITICAL ERROR: manifest or spine missing in EPUB.")

            # Get content files
            content_files_hrefs = []
            for itemref in spine.findall('.//opf:itemref', namespaces=NAMESPACES):
                idref = itemref.get('idref')
                item = manifest.find(f'.//opf:item[@id="{idref}"]', namespaces=NAMESPACES)
                if item is not None and item.get('media-type') in ['application/xhtml+xml', 'text/html'] and item.get('href'):
                    content_files_hrefs.append(item.get('href'))

            opf_dir = os.path.dirname(opf_path)

            # Phase 1: Collect translation jobs
            if log_callback: 
                log_callback("epub_phase1_start", "Phase 1: Collecting and splitting text from EPUB...")

            iterator_phase1 = tqdm(content_files_hrefs, desc="Analyzing EPUB files", unit="file") if not log_callback else content_files_hrefs
            for file_idx, content_href in enumerate(iterator_phase1):
                if progress_callback and len(content_files_hrefs) > 0:
                    progress_callback((file_idx / len(content_files_hrefs)) * 10)

                file_path_abs = os.path.normpath(os.path.join(opf_dir, content_href))
                if not os.path.exists(file_path_abs):
                    warn_msg = f"WARNING: EPUB file '{content_href}' not found at '{file_path_abs}', ignored."
                    if log_callback: 
                        log_callback("epub_content_file_not_found", warn_msg)
                    else: 
                        tqdm.write(warn_msg)
                    continue
                
                try:
                    async with aiofiles.open(file_path_abs, 'r', encoding='utf-8') as f_chap:
                        chap_str_content = await f_chap.read()

                    parser = etree.XMLParser(encoding='utf-8', recover=True, remove_blank_text=False)
                    doc_chap_root = etree.fromstring(chap_str_content.encode('utf-8'), parser)
                    parsed_xhtml_docs[file_path_abs] = doc_chap_root

                    body_el = doc_chap_root.find('.//{http://www.w3.org/1999/xhtml}body')
                    if body_el is not None:
                        _collect_epub_translation_jobs_recursive(body_el, file_path_abs, all_translation_jobs, chunk_target_lines_arg, log_callback)

                except etree.XMLSyntaxError as e_xml:
                    err_msg_xml = f"XML Syntax ERROR in '{content_href}': {e_xml}. Ignored."
                    if log_callback: 
                        log_callback("epub_xml_syntax_error", err_msg_xml)
                    else: 
                        tqdm.write(err_msg_xml)
                except Exception as e_chap:
                    err_msg_chap = f"ERROR Collecting chapter jobs '{content_href}': {e_chap}. Ignored."
                    if log_callback: 
                        log_callback("epub_collect_job_error", err_msg_chap)
                    else: 
                        tqdm.write(err_msg_chap)

            if not all_translation_jobs:
                info_msg_no_jobs = "No translatable text segments found in the EPUB."
                if log_callback: 
                    log_callback("epub_no_translatable_segments", info_msg_no_jobs)
                else: 
                    tqdm.write(info_msg_no_jobs)
                if progress_callback: 
                    progress_callback(100)
                return
            else:
                if log_callback: 
                    log_callback("epub_jobs_collected", f"{len(all_translation_jobs)} translatable segments collected.")

            if stats_callback and all_translation_jobs:
                stats_callback({'total_chunks': len(all_translation_jobs), 'completed_chunks': 0, 'failed_chunks': 0})

            # Phase 2: Translate
            if log_callback: 
                log_callback("epub_phase2_start", "\nPhase 2: Translating EPUB text segments...")

            # Create LLM client if custom endpoint is provided
            from .llm_client import LLMClient, default_client
            llm_client = None
            if llm_provider == "gemini" and gemini_api_key:
                llm_client = LLMClient(provider_type="gemini", api_key=gemini_api_key, model=model_name)
            elif cli_api_endpoint and cli_api_endpoint != default_client.api_endpoint:
                llm_client = LLMClient(provider_type="ollama", api_endpoint=cli_api_endpoint, model=model_name)

            last_successful_llm_context = ""
            completed_jobs_count = 0
            failed_jobs_count = 0
            context_accumulator = []  # Accumulate recent translations for richer context

            iterator_phase2 = tqdm(all_translation_jobs, desc="Translating EPUB segments", unit="seg") if not log_callback else all_translation_jobs
            for job_idx, job in enumerate(iterator_phase2):
                if check_interruption_callback and check_interruption_callback():
                    if log_callback: 
                        log_callback("epub_translation_interrupted", f"EPUB translation process (job {job_idx+1}/{len(all_translation_jobs)}) interrupted by user signal.")
                    else: 
                        tqdm.write(f"\nEPUB translation interrupted by user at job {job_idx+1}/{len(all_translation_jobs)}.")
                    break

                if progress_callback and len(all_translation_jobs) > 0:
                    base_progress_phase2 = ((job_idx + 1) / len(all_translation_jobs)) * 90
                    progress_callback(10 + base_progress_phase2)

                # Translate sub-chunks for this job with previous context
                translated_parts = await translate_epub_chunks_with_context(
                    job['sub_chunks'], source_language, target_language, 
                    model_name, llm_client or default_client, last_successful_llm_context, 
                    log_callback, check_interruption_callback, custom_instructions,
                    enable_post_processing, post_processing_instructions
                )
                
                # Join translated parts
                translated_text = "\n".join(translated_parts)
                
                # If this job has a tag map, validate and restore the tags
                if 'tag_map' in job and job['tag_map']:
                    tag_preserver = TagPreserver()
                    
                    # Final validation to check for any mutations that might have slipped through
                    is_valid, missing, mutated = tag_preserver.validate_placeholders(translated_text, job['tag_map'])
                    
                    if not is_valid:
                        # Try to fix mutated placeholders
                        if mutated:
                            translated_text = tag_preserver.fix_mutated_placeholders(translated_text, mutated)
                            if log_callback:
                                log_callback("epub_fixed_mutations_final", 
                                           f"Fixed placeholder mutations in final check: {mutated}")
                        
                        # Log if still missing placeholders after all retries
                        if missing:
                            if log_callback:
                                log_callback("epub_placeholders_still_missing", 
                                           f"WARNING: Some placeholders still missing after all retries: {missing}")
                    
                    # Restore the tags
                    translated_text = tag_preserver.restore_tags(translated_text, job['tag_map'])
                
                job['translated_text'] = translated_text
                
                has_translation_error = any("[TRANSLATION_ERROR" in part for part in translated_parts)
                if has_translation_error:
                    failed_jobs_count += 1
                else:
                    completed_jobs_count += 1
                    # Update context with last successful translation
                    if translated_parts:
                        last_translation = "\n".join(translated_parts)
                        # Add to context accumulator
                        context_accumulator.append(last_translation)
                        
                        # Build context from multiple recent blocks to reach minimum 10 lines
                        combined_context_lines = []
                        for recent_translation in reversed(context_accumulator):
                            # Split into lines and add to beginning of combined context
                            translation_lines = recent_translation.split('\n')
                            combined_context_lines = translation_lines + combined_context_lines
                            
                            # Stop if we have enough lines (minimum 3 lines or 25 words)
                            if len(combined_context_lines) >= 3 or len(' '.join(combined_context_lines).split()) >= 25:
                                break
                        
                        # Keep only the most recent context that provides sufficient content
                        if len(combined_context_lines) > 5:  # Limit to max 5 lines to avoid too much context
                            combined_context_lines = combined_context_lines[-5:]
                        
                        last_successful_llm_context = '\n'.join(combined_context_lines)
                        
                        # Keep only recent translations in accumulator (last 10 blocks max)
                        if len(context_accumulator) > 10:
                            context_accumulator = context_accumulator[-10:]

                if stats_callback:
                    stats_callback({'completed_chunks': completed_jobs_count, 'failed_chunks': failed_jobs_count})

            if progress_callback: 
                progress_callback(100)

            # Phase 3: Apply translations
            if log_callback: 
                log_callback("epub_phase3_start", "\nPhase 3: Applying translations to EPUB files...")

            iterator_phase3 = tqdm(all_translation_jobs, desc="Updating EPUB content", unit="seg") if not log_callback else all_translation_jobs
            for job in iterator_phase3:
                if job.get('translated_text') is None:
                    continue

                element = job['element_ref']
                translated_content = job['translated_text']

                # Unescape HTML entities that may have been translated
                # This converts &nbsp; and other entities to their actual characters
                translated_content_unescaped = html.unescape(translated_content)
                
                if job['type'] == 'block_content':
                    # Check if this content had inline tags
                    if job.get('has_inline_tags'):
                        # Parse the translated content to rebuild the XML structure
                        _rebuild_element_from_translated_content(element, translated_content_unescaped)
                    else:
                        element.text = translated_content_unescaped
                        for child_node in list(element):
                            element.remove(child_node)
                elif job['type'] == 'text':
                    element.text = job['leading_space'] + translated_content_unescaped + job['trailing_space']
                elif job['type'] == 'tail':
                    element.tail = job['leading_space'] + translated_content_unescaped + job['trailing_space']

            # Update metadata
            metadata = opf_root.find('.//opf:metadata', namespaces=NAMESPACES)
            if metadata is not None:
                lang_el = metadata.find('.//dc:language', namespaces=NAMESPACES)
                if lang_el is not None: 
                    lang_el.text = target_language.lower()[:2]

            # Save OPF
            opf_tree.write(opf_path, encoding='utf-8', xml_declaration=True, pretty_print=True)

            # Save XHTML files
            for file_path_abs, doc_root in parsed_xhtml_docs.items():
                try:
                    # Clean any residual TAG placeholders in the final document
                    # This is done as a final step to ensure all placeholders are removed
                    for element in doc_root.iter():
                        if element.text:
                            element.text = clean_residual_tag_placeholders(element.text)
                        if element.tail:
                            element.tail = clean_residual_tag_placeholders(element.tail)
                    
                    async with aiofiles.open(file_path_abs, 'wb') as f_out:
                        await f_out.write(etree.tostring(doc_root, encoding='utf-8', xml_declaration=True, pretty_print=True, method='xml'))
                except Exception as e_write:
                    err_msg_write = f"ERROR writing modified EPUB file '{file_path_abs}': {e_write}"
                    if log_callback: 
                        log_callback("epub_write_error", err_msg_write)
                    else: 
                        tqdm.write(err_msg_write)

            # Create output EPUB
            if log_callback: 
                log_callback("epub_zip_start", "\nCreating translated EPUB file...")

            with zipfile.ZipFile(output_filepath, 'w', zipfile.ZIP_DEFLATED) as epub_zip:
                mimetype_path_abs = os.path.join(temp_dir, 'mimetype')
                if os.path.exists(mimetype_path_abs):
                    epub_zip.write(mimetype_path_abs, 'mimetype', compress_type=zipfile.ZIP_STORED)

                for root_path, _, files_in_root in os.walk(temp_dir):
                    for file_item in files_in_root:
                        if file_item != 'mimetype':
                            file_path_abs_for_zip = os.path.join(root_path, file_item)
                            arcname = os.path.relpath(file_path_abs_for_zip, temp_dir)
                            epub_zip.write(file_path_abs_for_zip, arcname)

            success_save_msg = f"Translated (Full/Partial) EPUB saved: '{output_filepath}'"
            if log_callback: 
                log_callback("epub_save_success", success_save_msg)
            else: 
                tqdm.write(success_save_msg)

        except Exception as e_epub:
            major_err_msg = f"MAJOR ERROR processing EPUB '{input_filepath}': {e_epub}"
            if log_callback:
                log_callback("epub_major_error", major_err_msg)
                import traceback
                log_callback("epub_major_error_traceback", traceback.format_exc())
            else:
                print(major_err_msg)
                import traceback
                traceback.print_exc()