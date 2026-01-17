"""
Centralized file type detection
"""
import os
from typing import Literal

FileType = Literal["txt", "epub", "srt", "docx"]


def detect_file_type(file_path: str) -> FileType:
    """
    Detect file type from extension
    
    Args:
        file_path: Path to the file
        
    Returns:
        File type as string
        
    Raises:
        ValueError: If file type is not supported
    """
    _, ext = os.path.splitext(file_path.lower())
    
    if ext == '.txt':
        return "txt"
    elif ext == '.epub':
        return "epub"
    elif ext == '.srt':
        return "srt"
    elif ext == '.docx':
        return "docx"
    else:
        raise ValueError(f"Unsupported file type: {ext}. Supported types: .txt, .epub, .srt, .docx")


def generate_output_filename(input_path: str, target_language: str) -> str:
    """
    Generate output filename based on input and target language
    
    Args:
        input_path: Input file path
        target_language: Target language
        
    Returns:
        Generated output filename
    """
    base, ext = os.path.splitext(input_path)
    lang_suffix = target_language.lower().replace(' ', '_')
    return f"{base}_{lang_suffix}{ext}"