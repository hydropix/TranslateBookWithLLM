"""
Sentence and paragraph boundary detection for chunking.

Provides intelligent boundary detection that respects semantic structure.
"""

import re
from typing import Tuple, List, Optional
from .models import BoundaryType, ChunkBoundary


# Common abbreviations that shouldn't be treated as sentence endings
COMMON_ABBREVIATIONS = {
    'Dr.', 'Mr.', 'Mrs.', 'Ms.', 'Prof.', 'Sr.', 'Jr.', 'Inc.', 'Ltd.', 'Corp.',
    'etc.', 'vs.', 'i.e.', 'e.g.', 'cf.', 'Fig.', 'fig.', 'No.', 'Vol.', 'vol.',
    'p.', 'pp.', 'Ed.', 'ed.', 'Rev.', 'Gen.', 'Col.', 'Lt.', 'Capt.', 'Sgt.',
    'Ave.', 'Blvd.', 'St.', 'Rd.', 'Mt.', 'ft.', 'in.', 'oz.', 'lb.', 'kg.',
    'Jan.', 'Feb.', 'Mar.', 'Apr.', 'Jun.', 'Jul.', 'Aug.', 'Sep.', 'Oct.', 'Nov.', 'Dec.'
}

# Regex patterns
URL_PATTERN = re.compile(r'https?://[^\s]+|www\.[^\s]+')
DECIMAL_PATTERN = re.compile(r'\d+\.\d+')
ELLIPSIS_PATTERN = re.compile(r'\.{2,}')


def find_sentence_boundary(
    text: str,
    start_position: int,
    search_direction: str = "forward",
    max_search_distance: int = 500,
    terminators: Optional[List[str]] = None
) -> Tuple[int, str, float]:
    """
    Locate the nearest sentence-ending position in text.

    Args:
        text: Full text to search within
        start_position: Character position to start search
        search_direction: "forward" or "backward"
        max_search_distance: Maximum characters to search
        terminators: List of sentence-ending punctuation

    Returns:
        Tuple of (position, terminator_found, confidence_score)
    """
    if terminators is None:
        terminators = ['.', '!', '?', '."', '?"', '!"', ".'", "?'", "!'", '.)', ':]']

    if not text or start_position < 0 or start_position >= len(text):
        return (start_position, "", 0.0)

    if search_direction == "forward":
        return _search_forward(text, start_position, max_search_distance, terminators)
    else:
        return _search_backward(text, start_position, max_search_distance, terminators)


def _search_forward(
    text: str,
    start_position: int,
    max_distance: int,
    terminators: List[str]
) -> Tuple[int, str, float]:
    """Search forward for sentence boundary."""
    end_pos = min(start_position + max_distance, len(text))

    for i in range(start_position, end_pos):
        # Check for multi-character terminators first (longer matches first)
        for term in sorted(terminators, key=len, reverse=True):
            if text[i:i+len(term)] == term:
                # Check if this is a valid sentence ending
                if _is_valid_sentence_end(text, i, term):
                    # Return position after terminator
                    return (i + len(term), term, 1.0)

    # No boundary found within distance
    return (start_position, "", 0.3)


def _search_backward(
    text: str,
    start_position: int,
    max_distance: int,
    terminators: List[str]
) -> Tuple[int, str, float]:
    """Search backward for sentence boundary."""
    begin_pos = max(start_position - max_distance, 0)

    for i in range(start_position - 1, begin_pos - 1, -1):
        # Check for multi-character terminators first
        for term in sorted(terminators, key=len, reverse=True):
            if i >= len(term) - 1:
                check_start = i - len(term) + 1
                if text[check_start:i+1] == term:
                    # Check if this is a valid sentence ending
                    if _is_valid_sentence_end(text, check_start, term):
                        # Return position after terminator
                        return (i + 1, term, 1.0)

    # No boundary found within distance
    return (start_position, "", 0.3)


def _is_valid_sentence_end(text: str, position: int, terminator: str) -> bool:
    """
    Check if the terminator at position is a valid sentence ending.

    Avoids false positives from abbreviations, URLs, decimal numbers, etc.
    """
    # Must be followed by whitespace, end of text, or closing punctuation
    end_pos = position + len(terminator)
    if end_pos < len(text):
        next_char = text[end_pos]
        # Valid if followed by space, newline, or end of text
        if not (next_char.isspace() or next_char in '")]}>'):
            return False

    # Check if it's part of an abbreviation
    # Look for word before the period
    if terminator == '.' or terminator.startswith('.'):
        word_start = position - 1
        while word_start >= 0 and text[word_start].isalpha():
            word_start -= 1
        word_start += 1

        potential_abbrev = text[word_start:position + 1]
        if potential_abbrev in COMMON_ABBREVIATIONS:
            return False

        # Check for single letter abbreviations (e.g., "A.", "B.")
        if position > 0 and position - word_start == 1 and text[word_start].isupper():
            return False

    # Check if it's part of a URL
    # Look back for http:// or www.
    context_start = max(0, position - 100)
    context = text[context_start:end_pos]
    if URL_PATTERN.search(context):
        # Find the URL and check if our position is within it
        for match in URL_PATTERN.finditer(context):
            url_start_in_text = context_start + match.start()
            url_end_in_text = context_start + match.end()
            if url_start_in_text <= position < url_end_in_text:
                return False

    # Check if it's part of a decimal number (e.g., "3.14")
    if terminator == '.':
        # Check if surrounded by digits
        if position > 0 and end_pos < len(text):
            if text[position - 1].isdigit() and text[end_pos].isdigit():
                return False

    # Check for ellipsis (...)
    if terminator == '.' and end_pos < len(text) and text[end_pos] == '.':
        return False

    return True


def detect_paragraph_boundaries(text: str) -> List[int]:
    """
    Detect paragraph boundary positions in text.

    Args:
        text: Text to analyze

    Returns:
        List of character positions where paragraphs end
    """
    boundaries = []

    # Pattern 1: Double newlines (most common paragraph separator)
    double_newline = re.compile(r'\n\s*\n')
    for match in double_newline.finditer(text):
        boundaries.append(match.end())

    # Pattern 2: Consecutive <br/> tags (HTML)
    br_pattern = re.compile(r'(<br\s*/?>){2,}', re.IGNORECASE)
    for match in br_pattern.finditer(text):
        boundaries.append(match.end())

    # Sort and remove duplicates
    boundaries = sorted(set(boundaries))

    return boundaries


def is_header_line(line: str) -> bool:
    """
    Check if a line is a header/title.

    Args:
        line: Text line to check

    Returns:
        True if line appears to be a header
    """
    line = line.strip()

    if not line:
        return False

    # Markdown headers
    if line.startswith('#'):
        return True

    # All caps headers (common in EPUB)
    if len(line) > 3 and line.isupper() and not line.endswith('.'):
        return True

    # Chapter markers
    chapter_patterns = [
        r'^Chapter\s+\d+',
        r'^CHAPTER\s+\d+',
        r'^Part\s+\d+',
        r'^PART\s+\d+',
        r'^Section\s+\d+',
        r'^SECTION\s+\d+',
    ]
    for pattern in chapter_patterns:
        if re.match(pattern, line, re.IGNORECASE):
            return True

    # Short lines without ending punctuation (likely titles)
    if len(line) < 100 and not line[-1] in '.!?:;,':
        # Count words
        words = line.split()
        if 1 <= len(words) <= 10:
            # Check if title case or all caps
            if line.istitle() or line.isupper():
                return True

    return False


def create_chunk_boundary(
    text: str,
    target_position: int,
    boundary_type: BoundaryType,
    terminators: Optional[List[str]] = None
) -> ChunkBoundary:
    """
    Create a ChunkBoundary object at the specified position.

    Args:
        text: Full text
        target_position: Approximate position for boundary
        boundary_type: Type of boundary to create
        terminators: Sentence terminators

    Returns:
        ChunkBoundary object
    """
    if boundary_type == BoundaryType.SENTENCE_END:
        pos, term, confidence = find_sentence_boundary(
            text, target_position, "backward", 200, terminators
        )
        return ChunkBoundary(
            position=pos,
            type=boundary_type,
            confidence=confidence,
            original_punctuation=term if term else None,
            fallback_used=(confidence < 1.0)
        )

    elif boundary_type == BoundaryType.PARAGRAPH_END:
        # Find nearest paragraph boundary
        para_boundaries = detect_paragraph_boundaries(text)
        if para_boundaries:
            nearest = min(para_boundaries, key=lambda x: abs(x - target_position))
            if abs(nearest - target_position) < 500:
                return ChunkBoundary(
                    position=nearest,
                    type=boundary_type,
                    confidence=1.0,
                    original_punctuation="\n\n",
                    fallback_used=False
                )

        # Fallback to sentence boundary
        pos, term, confidence = find_sentence_boundary(
            text, target_position, "backward", 200, terminators
        )
        return ChunkBoundary(
            position=pos,
            type=BoundaryType.SENTENCE_END,
            confidence=confidence * 0.8,
            original_punctuation=term,
            fallback_used=True
        )

    else:
        # For other types, use the target position directly
        return ChunkBoundary(
            position=target_position,
            type=boundary_type,
            confidence=1.0,
            original_punctuation=None,
            fallback_used=False
        )
