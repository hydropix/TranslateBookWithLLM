"""
Path validation utilities for secure file operations
"""
import os
from typing import Tuple


class PathValidator:
    """Validates file paths and names for security"""

    MAX_FILENAME_LENGTH = 255

    @staticmethod
    def validate_filename(filename: str) -> Tuple[bool, str]:
        """
        Validate filename for security issues

        Args:
            filename: The filename to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not filename:
            return False, "Filename cannot be empty"

        # Prevent directory traversal - check for path separators with '..'
        # This allows '...' or '....' but blocks '../' or '..\' patterns
        if filename.startswith('/') or filename.startswith('\\'):
            return False, "Invalid filename: absolute path not allowed"

        # Check for directory traversal patterns
        # Block: ../ or ..\ (with separators)
        if '/../' in filename or '\\..\\' in filename or '/..' in filename or '\\..' in filename:
            return False, "Invalid filename: directory traversal not allowed"

        # Also check if the normalized filename contains path separators
        # This catches cases like "foo/../bar" or "foo/bar"
        if os.path.sep in filename or ('/' in filename or '\\' in filename):
            # Exception: allow if it's just the filename itself (no actual traversal)
            # Use os.path.basename to check if it's a pure filename
            if os.path.basename(filename) != filename:
                return False, "Invalid filename: path separators not allowed"

        # Check filename length
        if len(filename) > PathValidator.MAX_FILENAME_LENGTH:
            return False, f"Filename too long (max {PathValidator.MAX_FILENAME_LENGTH} characters)"

        # Prevent absolute paths
        if ':' in filename and len(filename) > 2 and filename[1] == ':':  # Windows absolute path
            return False, "Absolute paths not allowed"

        return True, ""

    @staticmethod
    def validate_filenames(filenames: list) -> Tuple[bool, str]:
        """
        Validate a list of filenames

        Args:
            filenames: List of filenames to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(filenames, list):
            return False, "Filenames must be a list"

        if len(filenames) == 0:
            return False, "No filenames provided"

        for filename in filenames:
            is_valid, error = PathValidator.validate_filename(filename)
            if not is_valid:
                return False, f"Invalid filename '{filename}': {error}"

        return True, ""
