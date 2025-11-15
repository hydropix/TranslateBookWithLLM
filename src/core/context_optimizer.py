"""
Context Optimization Module

Handles automatic estimation and adjustment of context size for LLM requests.
Ensures prompts fit within model's context window by estimating token counts
and adjusting parameters (num_ctx, chunk_size) as needed.
"""

import re
from typing import Optional, Tuple, Dict
from dataclasses import dataclass

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

# Safety margin for estimation (20% buffer)
SAFETY_MARGIN = 1.2

# Model family maximum context sizes (tokens)
MODEL_MAX_CONTEXT = {
    "llama": 32768,   # Llama 2 and 3 support up to 32K
    "mistral": 32768, # Mistral models support up to 32K
    "gemma": 8192,    # Gemma models typically 8K
    "phi": 4096,      # Phi models typically 4K
    "qwen": 32768,    # Qwen models support up to 32K
}


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
        apply_margin: Whether to apply 20% safety margin

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


def get_max_model_context(model_name: str) -> int:
    """
    Get maximum context size for a model based on its family.

    Args:
        model_name: Name of the model (e.g., "qwen3:14b")

    Returns:
        Maximum context size in tokens
    """
    model_lower = model_name.lower()

    for family, max_ctx in MODEL_MAX_CONTEXT.items():
        if family in model_lower:
            return max_ctx

    # Conservative default if family not recognized
    return 8192


def adjust_parameters_for_context(
    estimated_tokens: int,
    current_num_ctx: int,
    current_chunk_size: int,
    model_name: str,
    min_chunk_size: int = 5
) -> Tuple[int, int, list[str]]:
    """
    Adjust num_ctx and/or chunk_size to fit prompt within context.

    Strategy (Option B):
        1. Priority: Increase num_ctx up to model's maximum
        2. Last resort: Reduce chunk_size if num_ctx cannot be increased enough

    Args:
        estimated_tokens: Estimated prompt size in tokens
        current_num_ctx: Current context window setting
        current_chunk_size: Current chunk size (lines)
        model_name: Name of the model
        min_chunk_size: Minimum allowed chunk size

    Returns:
        Tuple of (adjusted_num_ctx, adjusted_chunk_size, warnings)
    """
    warnings = []
    adjusted_num_ctx = current_num_ctx
    adjusted_chunk_size = current_chunk_size

    # Get model's absolute maximum
    model_max = get_max_model_context(model_name)

    # Check if current context is sufficient
    # Need headroom for output (reserve 50% at minimum)
    required_ctx = estimated_tokens * 2  # 50% input, 50% output

    if required_ctx <= current_num_ctx:
        # All good, no adjustment needed
        return adjusted_num_ctx, adjusted_chunk_size, warnings

    # Step 1: Try to increase num_ctx
    if required_ctx <= model_max:
        adjusted_num_ctx = required_ctx
        warnings.append(
            f"Automatically increased context window from {current_num_ctx} to {adjusted_num_ctx} tokens "
            f"to accommodate prompt size (~{estimated_tokens} tokens)."
        )
        return adjusted_num_ctx, adjusted_chunk_size, warnings

    # Step 2: Last resort - reduce chunk_size
    # num_ctx is already at or above model max
    adjusted_num_ctx = model_max

    # Calculate what chunk_size would fit
    new_chunk_size = calculate_optimal_chunk_size(
        max_context_tokens=model_max,
        min_chunk_size=min_chunk_size
    )

    if new_chunk_size < current_chunk_size:
        adjusted_chunk_size = new_chunk_size
        warnings.append(
            f"Prompt too large even at maximum context ({model_max} tokens). "
            f"Automatically reduced chunk_size from {current_chunk_size} to {adjusted_chunk_size} lines."
        )
        warnings.append(
            f"Consider: 1) Using a model with larger context, or "
            f"2) Manually setting a smaller chunk_size in configuration."
        )
    else:
        # This shouldn't happen, but handle gracefully
        warnings.append(
            f"WARNING: Prompt size ({estimated_tokens} tokens) may exceed model capacity. "
            f"Translation may fail or produce incomplete results."
        )

    return adjusted_num_ctx, adjusted_chunk_size, warnings


def validate_configuration(
    chunk_size: int,
    num_ctx: int,
    model_name: str
) -> list[str]:
    """
    Validate translation configuration and return warnings/recommendations.

    Args:
        chunk_size: Configured chunk size
        num_ctx: Configured context window
        model_name: Model name

    Returns:
        List of warning/recommendation messages
    """
    warnings = []

    # Estimate typical prompt size for this configuration
    # Base overhead + (chunk_size * tokens_per_line) + context overhead
    estimated_prompt = 2000 + (chunk_size * 23) + 200

    # Need to reserve space for output (at least 50%)
    min_recommended_ctx = estimated_prompt * 2

    if num_ctx < min_recommended_ctx:
        warnings.append(
            f"⚠️  Configuration Warning:\n"
            f"   chunk_size={chunk_size} requires approximately {min_recommended_ctx} tokens of context\n"
            f"   Current num_ctx={num_ctx} may be insufficient\n"
            f"   Recommendation: Set OLLAMA_NUM_CTX={min_recommended_ctx} or higher in .env file"
        )

    # Check against model maximum
    model_max = get_max_model_context(model_name)
    if num_ctx > model_max:
        warnings.append(
            f"⚠️  num_ctx ({num_ctx}) exceeds model's likely maximum ({model_max}).\n"
            f"   This may be ignored by Ollama or cause errors.\n"
            f"   Recommendation: Set OLLAMA_NUM_CTX={model_max}"
        )

    # Check if chunk_size is reasonable
    if chunk_size < 5:
        warnings.append(
            f"ℹ️  chunk_size ({chunk_size}) is very small. Translation may be slow.\n"
            f"   Consider increasing chunk_size and num_ctx for better performance."
        )

    if chunk_size > 100:
        warnings.append(
            f"ℹ️  chunk_size ({chunk_size}) is very large. Ensure num_ctx is sufficient.\n"
            f"   Minimum recommended num_ctx: {min_recommended_ctx} tokens"
        )

    return warnings


# Convenience function for logging
def format_estimation_info(estimation: ContextEstimation) -> str:
    """Format estimation details for logging"""
    margin_text = " (with 20% safety margin)" if estimation.safety_margin_applied else ""
    return (
        f"Estimated {estimation.estimated_tokens} tokens{margin_text} "
        f"using {estimation.estimation_method} method "
        f"({estimation.prompt_length_chars} characters, {estimation.language})"
    )
