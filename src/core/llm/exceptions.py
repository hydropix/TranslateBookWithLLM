"""
LLM-specific exceptions.

This module defines all custom exceptions used in the LLM provider system.
"""


class ContextOverflowError(Exception):
    """
    Raised when the input text exceeds the model's context window.

    This typically occurs when a chunk is too large for the model to process
    in a single request.
    """
    pass


class RepetitionLoopError(Exception):
    """
    Raised when the model enters a repetition loop.

    This can occur with "thinking" models that get stuck repeating the same
    phrase or pattern, indicating the model has likely exceeded its effective
    context window or encountered an issue.
    """
    pass
