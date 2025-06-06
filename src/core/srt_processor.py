import re
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class SRTProcessor:
    """Handles SRT subtitle file processing, parsing, and reconstruction."""
    
    def __init__(self):
        # Updated regex pattern to properly capture SRT blocks
        self.subtitle_pattern = re.compile(
            r'(\d+)\s*\n'  # Subtitle number
            r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n'  # Timecode
            r'((?:(?!\n\n|\n\d+\s*\n).*\n?)*)',  # Text content (until empty line or next subtitle)
            re.MULTILINE
        )
    
    def parse_srt(self, content: str) -> List[Dict[str, str]]:
        """Parse SRT content into structured subtitle entries.
        
        Args:
            content: Raw SRT file content
            
        Returns:
            List of subtitle dictionaries with keys:
            - number: Subtitle sequence number
            - start_time: Start timecode
            - end_time: End timecode
            - text: Subtitle text (to be translated)
            - original_text: Original text (preserved for reference)
        """
        subtitles = []
        
        # Normalize line endings and ensure content ends with newline
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        if not content.endswith('\n'):
            content += '\n'
        
        # Split content into blocks by double newlines
        blocks = content.split('\n\n')
        
        for block in blocks:
            block = block.strip()
            if not block:
                continue
                
            lines = block.split('\n')
            if len(lines) < 3:  # Need at least: number, timecode, text
                continue
                
            # Extract subtitle number
            if not lines[0].isdigit():
                continue
            number = lines[0]
            
            # Extract timecode
            timecode_match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', lines[1])
            if not timecode_match:
                continue
            start_time, end_time = timecode_match.groups()
            
            # Extract text (everything after timecode line)
            text_lines = lines[2:]
            text = '\n'.join(text_lines)
            
            subtitle = {
                'number': number,
                'start_time': start_time,
                'end_time': end_time,
                'text': text,
                'original_text': text  # Keep original for reference
            }
            subtitles.append(subtitle)
            
        logger.info(f"Parsed {len(subtitles)} subtitles from SRT file")
        return subtitles
    
    def extract_translatable_text(self, subtitles: List[Dict[str, str]]) -> List[Tuple[int, str]]:
        """Extract only the text portions that need translation.
        
        Args:
            subtitles: List of parsed subtitle dictionaries
            
        Returns:
            List of tuples (index, text) for translation
        """
        translatable = []
        
        for idx, subtitle in enumerate(subtitles):
            if subtitle['text'].strip():  # Only non-empty text
                translatable.append((idx, subtitle['text']))
                
        return translatable
    
    def update_translated_subtitles(self, subtitles: List[Dict[str, str]], 
                                  translations: Dict[int, str]) -> List[Dict[str, str]]:
        """Update subtitle entries with translated text.
        
        Args:
            subtitles: Original parsed subtitles
            translations: Dictionary mapping subtitle index to translated text
            
        Returns:
            Updated subtitle list with translations
        """
        for idx, translation in translations.items():
            if idx < len(subtitles):
                subtitles[idx]['text'] = translation
                
        return subtitles
    
    def reconstruct_srt(self, subtitles: List[Dict[str, str]]) -> str:
        """Reconstruct SRT file content from subtitle entries.
        
        Args:
            subtitles: List of subtitle dictionaries
            
        Returns:
            Formatted SRT file content
        """
        srt_content = []
        
        for subtitle in subtitles:
            # Format each subtitle block
            block = f"{subtitle['number']}\n"
            block += f"{subtitle['start_time']} --> {subtitle['end_time']}\n"
            block += f"{subtitle['text']}\n"
            
            srt_content.append(block)
        
        # Join blocks with empty lines
        return '\n'.join(srt_content)
    
    def validate_srt(self, content: str) -> bool:
        """Validate that content appears to be valid SRT format.
        
        Args:
            content: File content to validate
            
        Returns:
            True if content appears to be valid SRT format
        """
        # Check for at least one valid subtitle pattern
        return bool(self.subtitle_pattern.search(content))
    
    def merge_multiline_subtitles(self, subtitles: List[Dict[str, str]], 
                                max_chars: int = 100) -> List[Dict[str, str]]:
        """Optionally merge short consecutive subtitles for better translation context.
        
        Args:
            subtitles: List of parsed subtitles
            max_chars: Maximum characters before avoiding merge
            
        Returns:
            List of subtitles with some entries potentially merged
        """
        if not subtitles:
            return subtitles
            
        merged = []
        current = None
        
        for subtitle in subtitles:
            if current is None:
                current = subtitle.copy()
            elif (len(current['text']) + len(subtitle['text']) + 1 <= max_chars and
                  self._is_continuation(current['text'], subtitle['text'])):
                # Merge subtitles
                current['text'] += ' ' + subtitle['text']
                current['end_time'] = subtitle['end_time']
                # Keep track of merged numbers
                if 'merged_numbers' not in current:
                    current['merged_numbers'] = [current['number']]
                current['merged_numbers'].append(subtitle['number'])
            else:
                merged.append(current)
                current = subtitle.copy()
                
        if current:
            merged.append(current)
            
        return merged
    
    def _is_continuation(self, text1: str, text2: str) -> bool:
        """Check if text2 appears to be a continuation of text1.
        
        Args:
            text1: First text segment
            text2: Second text segment
            
        Returns:
            True if text2 seems to continue text1
        """
        # Simple heuristic: text1 doesn't end with sentence terminator
        # and text2 doesn't start with capital letter (unless it's "I")
        terminators = '.!?'
        
        if not text1 or not text2:
            return False
            
        ends_with_terminator = text1.rstrip()[-1] in terminators if text1.rstrip() else False
        starts_with_capital = text2.strip()[0].isupper() if text2.strip() else False
        starts_with_i = text2.strip().startswith('I ') or text2.strip() == 'I'
        
        return not ends_with_terminator and (not starts_with_capital or starts_with_i)
    
    def group_subtitles_for_translation(self, subtitles: List[Dict[str, str]], 
                                      lines_per_block: int = 5,
                                      max_chars_per_block: int = 500) -> List[List[Dict[str, str]]]:
        """Group subtitles into blocks for batch translation with context.
        
        Args:
            subtitles: List of parsed subtitle dictionaries
            lines_per_block: Target number of subtitle lines per translation block
            max_chars_per_block: Maximum characters per block (soft limit)
            
        Returns:
            List of subtitle blocks, where each block is a list of subtitle dicts
        """
        if not subtitles:
            return []
        
        blocks = []
        current_block = []
        current_char_count = 0
        
        for i, subtitle in enumerate(subtitles):
            text = subtitle.get('text', '').strip()
            
            # Include empty subtitles but don't count them toward limits
            if not text:
                # If we have a current block, add empty subtitle to maintain sequence
                if current_block:
                    current_block.append(subtitle)
                continue
                
            text_length = len(text)
            
            # Check if adding this subtitle would exceed limits
            would_exceed_lines = len(current_block) >= lines_per_block
            would_exceed_chars = current_char_count + text_length > max_chars_per_block
            
            # Start new block if limits exceeded and current block has content
            if current_block and (would_exceed_lines or would_exceed_chars):
                blocks.append(current_block)
                current_block = []
                current_char_count = 0
            
            # Add subtitle to current block
            current_block.append(subtitle)
            current_char_count += text_length
            
        # Add final block if not empty
        if current_block:
            blocks.append(current_block)
            
        logger.info(f"Grouped {len(subtitles)} subtitles into {len(blocks)} blocks")
        return blocks
    
    def extract_block_translations(self, translated_text: str, block_indices: List[int]) -> Dict[int, str]:
        """Extract individual subtitle translations from a block translation.
        
        Args:
            translated_text: The translated block text with index markers
            block_indices: List of subtitle indices in this block
            
        Returns:
            Dictionary mapping subtitle index to translated text
        """
        translations = {}
        
        # Split by index markers
        lines = translated_text.strip().split('\n')
        current_index = None
        current_text_lines = []
        
        for line in lines:
            # Check if line starts with index marker
            index_match = re.match(r'^\[(\d+)\](.*)$', line)
            
            if index_match:
                # Save previous subtitle if exists
                if current_index is not None and current_text_lines:
                    translations[current_index] = '\n'.join(current_text_lines).strip()
                
                # Start new subtitle
                current_index = int(index_match.group(1))
                remaining_text = index_match.group(2).strip()
                
                if remaining_text:
                    current_text_lines = [remaining_text]
                else:
                    current_text_lines = []
            else:
                # Continue current subtitle
                if current_index is not None:
                    current_text_lines.append(line)
        
        # Save final subtitle
        if current_index is not None and current_text_lines:
            translations[current_index] = '\n'.join(current_text_lines).strip()
        
        # Validate we got all expected translations
        missing_indices = set(block_indices) - set(translations.keys())
        if missing_indices:
            logger.warning(f"Missing translations for indices: {missing_indices}")
        
        return translations