"""
Thinking System Module

Handles detection and management of "thinking" models that output reasoning tokens.

Components:
    - behavior: ThinkingBehavior enum and detection functions
    - cache: Persistent cache for model behavior
    - detection: Repetition loop detection
"""

# Behavior
from .behavior import (
    ThinkingBehavior,
    get_thinking_behavior_from_known_lists,
    get_thinking_behavior_sync,
    get_model_warning_message
)

# Cache
from .cache import (
    ThinkingCache,
    get_thinking_cache
)

# Detection
from .detection import detect_repetition_loop

__all__ = [
    # Behavior
    "ThinkingBehavior",
    "get_thinking_behavior_from_known_lists",
    "get_thinking_behavior_sync",
    "get_model_warning_message",

    # Cache
    "ThinkingCache",
    "get_thinking_cache",

    # Detection
    "detect_repetition_loop",
]
