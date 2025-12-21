"""
Text processing module for chunking and context management
"""
import re
from typing import List, Dict, Optional, TYPE_CHECKING

from src.config import SENTENCE_TERMINATORS

if TYPE_CHECKING:
    from src.config import TranslationConfig


def get_adjusted_start_index(all_lines, intended_start_idx, max_look_back_lines=20):
    """Adjust start index to align with sentence boundaries"""
    if intended_start_idx == 0:
        return 0
    for i in range(intended_start_idx - 1, max(-1, intended_start_idx - 1 - max_look_back_lines), -1):
        if i < 0:
            break
        line_content_stripped = all_lines[i].strip()
        if line_content_stripped and line_content_stripped.endswith(SENTENCE_TERMINATORS):
            return i + 1
    if intended_start_idx <= max_look_back_lines:
        return 0
    return intended_start_idx


def get_adjusted_end_index(all_lines, intended_end_idx, max_look_forward_lines=20):
    """Adjust end index to align with sentence boundaries"""
    if intended_end_idx >= len(all_lines):
        return len(all_lines)

    start_search_fwd = intended_end_idx - 1
    if start_search_fwd < 0: 
        start_search_fwd = 0

    for i in range(start_search_fwd, min(len(all_lines), start_search_fwd + max_look_forward_lines)):
        line_content_stripped = all_lines[i].strip()
        if line_content_stripped and line_content_stripped.endswith(SENTENCE_TERMINATORS):
            return i + 1

    if intended_end_idx + max_look_forward_lines >= len(all_lines):
        return len(all_lines)
    return intended_end_idx


def split_text_into_chunks_with_context(text, main_lines_per_chunk_target):
    """
    Split text into chunks with context preservation
    
    Args:
        text (str): Input text to split
        main_lines_per_chunk_target (int): Target lines per chunk
        
    Returns:
        list: List of chunk dictionaries with context_before, main_content, context_after
    """
    try:
        processed_text = re.sub(r'([a-zA-ZÀ-ÿ0-9])-(\n|\r\n|\r)\s*([a-zA-ZÀ-ÿ0-9])', r'\1\3', text)
    except Exception:
        processed_text = text

    original_raw_lines = processed_text.splitlines()
    refined_all_lines = []

    if original_raw_lines:
        sorted_terminators = sorted(list(SENTENCE_TERMINATORS), key=len, reverse=True)
        escaped_terminators = [re.escape(t) for t in sorted_terminators]
        sentence_splitting_pattern = '|'.join(escaped_terminators)

        for line_text in original_raw_lines:
            if not line_text.strip():
                refined_all_lines.append(line_text)
                continue

            current_segments = []
            last_split_end = 0
            for match in re.finditer(sentence_splitting_pattern, line_text):
                match_start, match_end = match.span()
                segment = line_text[last_split_end:match_end]
                if segment.strip():
                    current_segments.append(segment)
                last_split_end = match_end

            remaining_part = line_text[last_split_end:]
            if remaining_part.strip():
                current_segments.append(remaining_part)

            if not current_segments and line_text.strip():
                refined_all_lines.append(line_text)
            else:
                if current_segments:
                    refined_all_lines.extend(current_segments)
                elif not refined_all_lines or refined_all_lines[-1].strip() or line_text:
                    refined_all_lines.append(line_text)

    all_lines = refined_all_lines
    structured_chunks = []
    if not all_lines:
        return []

    look_back_main_limit = max(1, main_lines_per_chunk_target // 4)
    look_forward_main_limit = max(1, main_lines_per_chunk_target // 4)
    look_back_context_limit = max(1, main_lines_per_chunk_target // 8)
    look_forward_context_limit = max(1, main_lines_per_chunk_target // 8)

    current_position = 0
    while current_position < len(all_lines):
        initial_main_start_index = current_position
        initial_main_end_index = min(current_position + main_lines_per_chunk_target, len(all_lines))

        final_main_start_index = get_adjusted_start_index(all_lines, initial_main_start_index, look_back_main_limit)
        final_main_end_index = get_adjusted_end_index(all_lines, initial_main_end_index, look_forward_main_limit)

        if final_main_start_index > final_main_end_index:
            final_main_start_index = initial_main_start_index
            final_main_end_index = initial_main_end_index

        if final_main_end_index <= final_main_start_index:
            if initial_main_start_index < len(all_lines):
                if initial_main_end_index > initial_main_start_index:
                    final_main_start_index = initial_main_start_index
                    final_main_end_index = initial_main_end_index
                else:
                    final_main_start_index = initial_main_start_index
                    final_main_end_index = len(all_lines)
            else:
                break

        main_part_lines = all_lines[final_main_start_index:final_main_end_index]

        if not main_part_lines and final_main_start_index < len(all_lines):
            current_position = final_main_start_index + 1
            continue

        if not main_part_lines:
            break

        # Context before
        context_target_line_count_before = main_lines_per_chunk_target // 4
        intended_context_before_end_idx = final_main_start_index
        intended_context_before_start_idx = max(0, intended_context_before_end_idx - context_target_line_count_before)
        final_context_before_start_idx = get_adjusted_start_index(all_lines, intended_context_before_start_idx, look_back_context_limit)
        final_context_before_end_idx = min(intended_context_before_end_idx, final_main_start_index)
        
        if final_context_before_start_idx < final_context_before_end_idx:
            preceding_context_lines = all_lines[final_context_before_start_idx:final_context_before_end_idx]
        else:
            preceding_context_lines = []

        # Context after
        context_target_line_count_after = main_lines_per_chunk_target // 4
        intended_context_after_start_idx = final_main_end_index
        intended_context_after_end_idx = min(len(all_lines), intended_context_after_start_idx + context_target_line_count_after)
        final_context_after_start_idx = intended_context_after_start_idx
        final_context_after_end_idx = get_adjusted_end_index(all_lines, intended_context_after_end_idx, look_forward_context_limit)

        if final_context_after_start_idx < final_context_after_end_idx:
            succeeding_context_lines = all_lines[final_context_after_start_idx:final_context_after_end_idx]
        else:
            succeeding_context_lines = []

        if not "".join(main_part_lines).strip():
            current_position = final_main_end_index
            if current_position <= initial_main_start_index:
                current_position = initial_main_start_index + 1
            continue

        structured_chunks.append({
            "context_before": "\n".join(preceding_context_lines),
            "main_content": "\n".join(main_part_lines),
            "context_after": "\n".join(succeeding_context_lines)
        })

        current_position = final_main_end_index
        if current_position <= initial_main_start_index:
            current_position = initial_main_start_index + 1

    return structured_chunks


def split_text_into_chunks(
    text: str,
    config: Optional['TranslationConfig'] = None,
    use_token_chunking: Optional[bool] = None,
    max_tokens_per_chunk: Optional[int] = None,
    soft_limit_ratio: Optional[float] = None,
    chunk_size: Optional[int] = None
) -> List[Dict[str, str]]:
    """
    Split text into chunks with context preservation.

    Wrapper function that chooses between token-based and line-based chunking.

    Args:
        text: Input text to split
        config: TranslationConfig object (optional, for default values)
        use_token_chunking: Override for token chunking setting
        max_tokens_per_chunk: Override for max tokens per chunk
        soft_limit_ratio: Override for soft limit ratio
        chunk_size: Override for line-based chunk size

    Returns:
        List of chunk dictionaries with context_before, main_content, context_after
    """
    from src.config import (
        USE_TOKEN_CHUNKING,
        MAX_TOKENS_PER_CHUNK,
        SOFT_LIMIT_RATIO,
        MAIN_LINES_PER_CHUNK
    )

    # Determine settings from config or defaults
    if config is not None:
        _use_token = use_token_chunking if use_token_chunking is not None else config.use_token_chunking
        _max_tokens = max_tokens_per_chunk if max_tokens_per_chunk is not None else config.max_tokens_per_chunk
        _soft_limit = soft_limit_ratio if soft_limit_ratio is not None else config.soft_limit_ratio
        _chunk_size = chunk_size if chunk_size is not None else config.chunk_size
    else:
        _use_token = use_token_chunking if use_token_chunking is not None else USE_TOKEN_CHUNKING
        _max_tokens = max_tokens_per_chunk if max_tokens_per_chunk is not None else MAX_TOKENS_PER_CHUNK
        _soft_limit = soft_limit_ratio if soft_limit_ratio is not None else SOFT_LIMIT_RATIO
        _chunk_size = chunk_size if chunk_size is not None else MAIN_LINES_PER_CHUNK

    if _use_token:
        # Token-based chunking (new)
        from src.core.chunking.token_chunker import TokenChunker
        chunker = TokenChunker(
            max_tokens=_max_tokens,
            soft_limit_ratio=_soft_limit
        )
        return chunker.chunk_text(text)
    else:
        # Legacy line-based chunking
        return split_text_into_chunks_with_context(text, _chunk_size)