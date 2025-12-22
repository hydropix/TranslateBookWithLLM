"""
Placeholder preservation examples for translation prompts.

ARCHITECTURE:
- Technical examples (simple sentences demonstrating placeholder preservation)
  are now generated dynamically via technical_generator.py
- This file provides minimal fallback examples for when generation is not possible

The old static PLACEHOLDER_EXAMPLES dictionary with hundreds of pre-calculated
pairs has been removed. For high-quality translation examples demonstrating
cultural adaptation (idioms, metaphors), see cultural_examples.py.
"""

from typing import Dict, Tuple
from .constants import TAG0, TAG1


# Minimal fallback examples - used only when dynamic generation unavailable
# These are intentionally simple: the focus is on placeholder preservation,
# not on translation difficulty.
PLACEHOLDER_EXAMPLES: Dict[Tuple[str, str], Dict[str, str]] = {
    # English as source - core fallback
    ("english", "chinese"): {
        "source": f"This is {TAG0}important{TAG1} text.",
        "correct": f"这是{TAG0}重要的{TAG1}文本。",
        "wrong": "这是重要的文本。",
    },
    ("english", "french"): {
        "source": f"This is {TAG0}important{TAG1} text.",
        "correct": f"C'est un texte {TAG0}important{TAG1}.",
        "wrong": "C'est un texte important.",
    },
    ("english", "spanish"): {
        "source": f"This is {TAG0}important{TAG1} text.",
        "correct": f"Este es un texto {TAG0}importante{TAG1}.",
        "wrong": "Este es un texto importante.",
    },
    ("english", "german"): {
        "source": f"This is {TAG0}important{TAG1} text.",
        "correct": f"Dies ist ein {TAG0}wichtiger{TAG1} Text.",
        "wrong": "Dies ist ein wichtiger Text.",
    },
    ("english", "japanese"): {
        "source": f"This is {TAG0}important{TAG1} text.",
        "correct": f"これは{TAG0}重要な{TAG1}テキストです。",
        "wrong": "これは重要なテキストです。",
    },
    ("english", "korean"): {
        "source": f"This is {TAG0}important{TAG1} text.",
        "correct": f"이것은 {TAG0}중요한{TAG1} 텍스트입니다.",
        "wrong": "이것은 중요한 텍스트입니다.",
    },
    ("english", "russian"): {
        "source": f"This is {TAG0}important{TAG1} text.",
        "correct": f"Это {TAG0}важный{TAG1} текст.",
        "wrong": "Это важный текст.",
    },
    ("english", "arabic"): {
        "source": f"This is {TAG0}important{TAG1} text.",
        "correct": f"هذا نص {TAG0}مهم{TAG1}.",
        "wrong": "هذا نص مهم.",
    },
    ("english", "portuguese"): {
        "source": f"This is {TAG0}important{TAG1} text.",
        "correct": f"Este é um texto {TAG0}importante{TAG1}.",
        "wrong": "Este é um texto importante.",
    },
    ("english", "italian"): {
        "source": f"This is {TAG0}important{TAG1} text.",
        "correct": f"Questo è un testo {TAG0}importante{TAG1}.",
        "wrong": "Questo è un testo importante.",
    },

    # Reverse pairs for major languages
    ("chinese", "english"): {
        "source": f"这是{TAG0}重要的{TAG1}文本。",
        "correct": f"This is {TAG0}important{TAG1} text.",
        "wrong": "This is important text.",
    },
    ("french", "english"): {
        "source": f"C'est un texte {TAG0}important{TAG1}.",
        "correct": f"This is {TAG0}important{TAG1} text.",
        "wrong": "This is important text.",
    },
    ("spanish", "english"): {
        "source": f"Este es un texto {TAG0}importante{TAG1}.",
        "correct": f"This is {TAG0}important{TAG1} text.",
        "wrong": "This is important text.",
    },
    ("german", "english"): {
        "source": f"Dies ist ein {TAG0}wichtiger{TAG1} Text.",
        "correct": f"This is {TAG0}important{TAG1} text.",
        "wrong": "This is important text.",
    },
    ("japanese", "english"): {
        "source": f"これは{TAG0}重要な{TAG1}テキストです。",
        "correct": f"This is {TAG0}important{TAG1} text.",
        "wrong": "This is important text.",
    },
    ("korean", "english"): {
        "source": f"이것은 {TAG0}중요한{TAG1} 텍스트입니다.",
        "correct": f"This is {TAG0}important{TAG1} text.",
        "wrong": "This is important text.",
    },
    ("russian", "english"): {
        "source": f"Это {TAG0}важный{TAG1} текст.",
        "correct": f"This is {TAG0}important{TAG1} text.",
        "wrong": "This is important text.",
    },
}
