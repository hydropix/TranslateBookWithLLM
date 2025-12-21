"""
Context Optimization Module

Handles automatic estimation and adjustment of context size for LLM requests.
Ensures prompts fit within model's context window by estimating token counts
and adjusting parameters (num_ctx, chunk_size) as needed.
"""

import re
from typing import Optional, Tuple, Dict
from dataclasses import dataclass

from src.config import MAX_TOKENS_PER_CHUNK

# Try to import tiktoken, fallback to character-based estimation
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


@dataclass
class ContextEstimation:
    """Result of context size estimation"""
    estimated_tokens: int
    prompt_length_chars: int
    estimation_method: str  # "tiktoken" or "character_based"
    language: str
    safety_margin_applied: bool


# Language-specific character-to-token ratios
CHAR_TO_TOKEN_RATIOS = {
    "english": 4.0,
    "french": 3.5,
    "spanish": 3.5,
    "german": 3.8,
    "italian": 3.6,
    "portuguese": 3.5,
    "russian": 3.2,
    "chinese": 1.5,
    "japanese": 2.0,
    "korean": 2.5,
    "arabic": 3.0,
}

# Safety margin for estimation (10% buffer)
SAFETY_MARGIN = 1.1

# Standard context sizes (powers of 2) for optimal Ollama performance
STANDARD_CONTEXT_SIZES = [2048, 4096, 8192, 16384, 32768, 65536, 131072]


def round_to_standard_context_size(required: int) -> int:
    """
    Round up to the nearest standard context size (power of 2).
    Ollama performs better with these standard sizes.

    Args:
        required: Minimum required context size

    Returns:
        Nearest standard context size >= required
    """
    for size in STANDARD_CONTEXT_SIZES:
        if size >= required:
            return size
    # If larger than all standard sizes, return as-is
    return required

# Default context size - most translations fit within 2048 tokens
DEFAULT_CONTEXT_SIZE = 2048

# Maximum context size limit (can be adjusted via OLLAMA_NUM_CTX in .env)
# Most modern models support at least 32K, so we use this as a safe upper bound
MAX_CONTEXT_SIZE = 131072


def estimate_tokens_with_margin(
    text: str,
    language: str = "english",
    apply_margin: bool = True
) -> ContextEstimation:
    """
    Estimate number of tokens in text with safety margin.

    Uses tiktoken if available (more accurate), otherwise falls back
    to character-based estimation with language-specific ratios.

    Args:
        text: The text to estimate
        language: Language of the text (affects character ratio)
        apply_margin: Whether to apply 10% safety margin

    Returns:
        ContextEstimation object with estimation details
    """
    prompt_length = len(text)

    # Method 1: tiktoken (preferred, ~90-95% accurate for Ollama models)
    if TIKTOKEN_AVAILABLE:
        try:
            # Use cl100k_base encoding (GPT-4 tokenizer)
            # Note: Not exact for Ollama models, but close enough
            encoder = tiktoken.get_encoding("cl100k_base")
            base_tokens = len(encoder.encode(text))

            estimated_tokens = int(base_tokens * SAFETY_MARGIN) if apply_margin else base_tokens

            return ContextEstimation(
                estimated_tokens=estimated_tokens,
                prompt_length_chars=prompt_length,
                estimation_method="tiktoken",
                language=language,
                safety_margin_applied=apply_margin
            )
        except Exception:
            # Fall through to character-based method
            pass

    # Method 2: Character-based estimation with language factors
    lang_lower = language.lower()
    ratio = CHAR_TO_TOKEN_RATIOS.get(lang_lower, 4.0)  # Default to English

    base_tokens = prompt_length / ratio
    estimated_tokens = int(base_tokens * SAFETY_MARGIN) if apply_margin else int(base_tokens)

    return ContextEstimation(
        estimated_tokens=estimated_tokens,
        prompt_length_chars=prompt_length,
        estimation_method="character_based",
        language=language,
        safety_margin_applied=apply_margin
    )


def calculate_optimal_chunk_size(
    max_context_tokens: int,
    base_overhead: int = 2000,
    tokens_per_line: int = 23,
    min_chunk_size: int = 5,
    max_chunk_size: int = 100
) -> int:
    """
    Calculate optimal chunk size given context window constraints.

    Formula:
        Reserve 50% of context for output tokens
        Input budget = (max_context * 0.5) - base_overhead
        chunk_size = input_budget / tokens_per_line

    Args:
        max_context_tokens: Maximum context window size
        base_overhead: Base prompt overhead (instructions, formatting)
        tokens_per_line: Estimated tokens per line of content
        min_chunk_size: Minimum allowed chunk size
        max_chunk_size: Maximum allowed chunk size

    Returns:
        Optimal chunk size (number of lines)
    """
    # Reserve half the context for output
    input_budget = (max_context_tokens * 0.5) - base_overhead

    if input_budget <= 0:
        return min_chunk_size

    optimal_size = int(input_budget / tokens_per_line)

    # Clamp to min/max bounds
    optimal_size = max(min_chunk_size, min(max_chunk_size, optimal_size))

    return optimal_size


def adjust_parameters_for_context(
    estimated_tokens: int,
    current_num_ctx: int,
    current_chunk_size: int,
    model_name: str = "",
    min_chunk_size: int = 5
) -> Tuple[int, int, list[str]]:
    """
    Adjust num_ctx and/or chunk_size to fit prompt within context.

    Strategy:
        1. Priority: Increase num_ctx to next standard size (power of 2)
        2. Last resort: Reduce chunk_size if num_ctx would exceed MAX_CONTEXT_SIZE

    Args:
        estimated_tokens: Estimated prompt size in tokens
        current_num_ctx: Current context window setting (base from .env)
        current_chunk_size: Current chunk size (lines)
        model_name: Name of the model (unused, kept for compatibility)
        min_chunk_size: Minimum allowed chunk size

    Returns:
        Tuple of (adjusted_num_ctx, adjusted_chunk_size, warnings)
    """
    warnings = []
    adjusted_num_ctx = current_num_ctx
    adjusted_chunk_size = current_chunk_size

    # Check if current context is sufficient
    # Response can be up to 2x MAX_TOKENS_PER_CHUNK (for languages less efficient in tokenization)
    # + ~50 tokens for <Translated> tags
    response_buffer = (MAX_TOKENS_PER_CHUNK * 2) + 50
    required_ctx = estimated_tokens + response_buffer

    if required_ctx <= current_num_ctx:
        # All good, no adjustment needed
        return adjusted_num_ctx, adjusted_chunk_size, warnings

    # Step 1: Try to increase num_ctx to next standard size (power of 2)
    standard_ctx = round_to_standard_context_size(required_ctx)
    if standard_ctx <= MAX_CONTEXT_SIZE:
        adjusted_num_ctx = standard_ctx
        warnings.append(
            f"Automatically increased context window from {current_num_ctx} to {adjusted_num_ctx} tokens "
            f"to accommodate prompt size (~{estimated_tokens} tokens)."
        )
        return adjusted_num_ctx, adjusted_chunk_size, warnings

    # Step 2: Last resort - reduce chunk_size
    adjusted_num_ctx = MAX_CONTEXT_SIZE

    # Calculate what chunk_size would fit
    new_chunk_size = calculate_optimal_chunk_size(
        max_context_tokens=MAX_CONTEXT_SIZE,
        min_chunk_size=min_chunk_size
    )

    if new_chunk_size < current_chunk_size:
        adjusted_chunk_size = new_chunk_size
        warnings.append(
            f"Prompt too large even at maximum context ({MAX_CONTEXT_SIZE} tokens). "
            f"Automatically reduced chunk_size from {current_chunk_size} to {adjusted_chunk_size} lines."
        )
    else:
        warnings.append(
            f"WARNING: Prompt size ({estimated_tokens} tokens) may exceed maximum context. "
            f"Translation may fail or produce incomplete results."
        )

    return adjusted_num_ctx, adjusted_chunk_size, warnings


def validate_configuration(
    chunk_size: int,
    num_ctx: int,
    model_name: str = ""
) -> list[str]:
    """
    Validate translation configuration and return warnings/recommendations.

    Args:
        chunk_size: Configured chunk size
        num_ctx: Configured context window
        model_name: Model name (unused, kept for compatibility)

    Returns:
        List of warning/recommendation messages
    """
    warnings = []

    # Check if chunk_size is reasonable
    if chunk_size < 5:
        warnings.append(
            f"ℹ️  chunk_size ({chunk_size}) is very small. Translation may be slow.\n"
            f"   Consider increasing chunk_size for better performance."
        )

    if chunk_size > 100:
        # Estimate typical prompt size for this configuration
        estimated_prompt = 2000 + (chunk_size * 23) + 200
        min_recommended_ctx = estimated_prompt * 2
        warnings.append(
            f"ℹ️  chunk_size ({chunk_size}) is very large. Ensure num_ctx is sufficient.\n"
            f"   Minimum recommended num_ctx: {min_recommended_ctx} tokens"
        )

    return warnings


# Convenience function for logging
def format_estimation_info(estimation: ContextEstimation) -> str:
    """Format estimation details for logging"""
    margin_text = " (with 10% safety margin)" if estimation.safety_margin_applied else ""
    return (
        f"Estimated {estimation.estimated_tokens} tokens{margin_text} "
        f"using {estimation.estimation_method} method "
        f"({estimation.prompt_length_chars} characters, {estimation.language})"
    )
