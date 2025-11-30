"""
Prompts module for TranslateBookWithLLM
"""
from prompts.prompts import (
    PromptPair,
    generate_translation_prompt,
    generate_subtitle_block_prompt,
)

__all__ = [
    "PromptPair",
    "generate_translation_prompt",
    "generate_subtitle_block_prompt",
]
