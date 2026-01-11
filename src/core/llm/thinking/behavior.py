"""
Thinking behavior classification and detection for LLM models.

This module handles:
- ThinkingBehavior enum for model classification
- Pattern matching for model names
- Synchronous behavior detection (cache-based)
- Warning message generation for uncontrollable models
"""

import re
from enum import Enum
from typing import Optional

from src.config import (
    UNCONTROLLABLE_THINKING_MODELS,
    CONTROLLABLE_THINKING_MODELS
)


class ThinkingBehavior(Enum):
    """Classification of model thinking behavior"""
    STANDARD = "standard"              # No thinking capability
    CONTROLLABLE = "controllable"      # Thinks but respects think=false
    UNCONTROLLABLE = "uncontrollable"  # CANNOT stop thinking - needs WARNING


def _model_matches_pattern(model: str, pattern: str) -> bool:
    """
    Check if model name matches a pattern precisely.

    Matching rules:
    - "qwen3:30b" matches "qwen3:30b" exactly
    - "qwen3:30b" does NOT match "qwen3:30b-instruct"
    - "qwen3-vl" matches "qwen3-vl:4b", "qwen3-vl:8b" (prefix match with colon)
    - "phi4-reasoning" matches "phi4-reasoning:latest", "phi4-reasoning:14b"

    Args:
        model: Full model name (e.g., "qwen3:30b-instruct")
        pattern: Pattern from config (e.g., "qwen3:30b")

    Returns:
        True if model matches pattern
    """
    model_lower = model.lower()
    pattern_lower = pattern.lower()

    # Exact match
    if model_lower == pattern_lower:
        return True

    # Pattern with size (e.g., "qwen3:30b") - must match exactly or be a prefix followed by nothing valid
    # "qwen3:30b" should NOT match "qwen3:30b-instruct"
    if ":" in pattern_lower:
        # Check if model starts with pattern and next char (if any) is not alphanumeric or hyphen
        if model_lower.startswith(pattern_lower):
            remaining = model_lower[len(pattern_lower):]
            # If nothing remains, it's exact match (already handled above)
            # If something remains and starts with alphanumeric or hyphen, it's a different model
            if remaining and (remaining[0].isalnum() or remaining[0] == '-'):
                return False
            return True
        return False

    # Pattern without size (e.g., "qwen3-vl", "phi4-reasoning") - prefix match
    # "qwen3-vl" should match "qwen3-vl:4b", "qwen3-vl:8b"
    if model_lower.startswith(pattern_lower):
        remaining = model_lower[len(pattern_lower):]
        # Must be followed by nothing, ":", or end
        if not remaining or remaining[0] == ':':
            return True

    return False


def get_thinking_behavior_from_known_lists(model: str) -> Optional[ThinkingBehavior]:
    """
    Check if model matches known thinking behavior lists.

    This is an instant lookup that doesn't require cache loading.

    Args:
        model: Model name to check

    Returns:
        ThinkingBehavior if model is in known lists, None otherwise
    """
    # Check known lists - use precise matching
    for pattern in UNCONTROLLABLE_THINKING_MODELS:
        if _model_matches_pattern(model, pattern):
            return ThinkingBehavior.UNCONTROLLABLE
    for pattern in CONTROLLABLE_THINKING_MODELS:
        if _model_matches_pattern(model, pattern):
            return ThinkingBehavior.CONTROLLABLE

    return None


def get_thinking_behavior_sync(model: str, endpoint: str = "") -> Optional[ThinkingBehavior]:
    """
    Synchronous version for UI - returns cached or known list result instantly.

    This is safe to call from sync code (UI dropdowns, etc.) as it never
    makes network requests - only checks cache and known lists.

    Args:
        model: Model name
        endpoint: Optional endpoint to differentiate same model on different servers

    Returns:
        ThinkingBehavior if known, None if needs async testing
    """
    # Import here to avoid circular dependency
    from .cache import get_thinking_cache

    cache = get_thinking_cache()
    cached_behavior = cache.get(model, endpoint)

    if cached_behavior is not None:
        return cached_behavior

    # Check known lists as fallback
    return get_thinking_behavior_from_known_lists(model)


def get_model_warning_message(model: str, endpoint: str = "") -> Optional[str]:
    """
    Get warning message for a model if it's uncontrollable (for UI display).

    Args:
        model: Model name
        endpoint: Optional endpoint

    Returns:
        Warning message string if uncontrollable, None otherwise
    """
    behavior = get_thinking_behavior_sync(model, endpoint)

    if behavior == ThinkingBehavior.UNCONTROLLABLE:
        model_lower = model.lower()

        # Build recommendation based on model
        recommendation = ""
        if "qwen3" in model_lower and "instruct" not in model_lower:
            size_match = re.search(r':(\d+b)', model_lower)
            size = size_match.group(1) if size_match else ""
            if size:
                recommendation = f"Recommended: qwen3:{size}-instruct"
            else:
                recommendation = "Recommended: Use a Qwen3 instruct variant"
        elif "phi4-reasoning" in model_lower:
            recommendation = "Recommended: phi4:latest"
        elif "deepseek" in model_lower or "qwq" in model_lower:
            recommendation = "Recommended: Use a non-reasoning model"

        warning = "⚠️ This model cannot disable thinking mode (slower, uses more tokens)"
        if recommendation:
            warning += f"\n{recommendation}"

        return warning

    return None
