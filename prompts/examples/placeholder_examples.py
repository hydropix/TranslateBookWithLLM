"""
Placeholder preservation examples for translation prompts.

Uses a single source sentence translated into each supported language.
Examples are generated dynamically for any language pair by combining
the source language text with the target language translation.

Covers 40+ languages based on global speaker populations.
"""

from typing import Dict, Tuple
from .constants import TAG0, TAG1


# Single sentence translated into 40+ languages
# Format: "This is [TAG0]important[TAG1] text." with and without placeholders
# Organized by language family / region for maintainability
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # ============================================================
    # GERMANIC LANGUAGES
    # ============================================================
    "english": {
        "with_tags": f"This is {TAG0}important{TAG1} text.",
        "without_tags": "This is important text.",
    },
    "german": {
        "with_tags": f"Dies ist ein {TAG0}wichtiger{TAG1} Text.",
        "without_tags": "Dies ist ein wichtiger Text.",
    },
    "dutch": {
        "with_tags": f"Dit is een {TAG0}belangrijke{TAG1} tekst.",
        "without_tags": "Dit is een belangrijke tekst.",
    },
    "swedish": {
        "with_tags": f"Detta är en {TAG0}viktig{TAG1} text.",
        "without_tags": "Detta är en viktig text.",
    },
    "norwegian": {
        "with_tags": f"Dette er en {TAG0}viktig{TAG1} tekst.",
        "without_tags": "Dette er en viktig tekst.",
    },
    "danish": {
        "with_tags": f"Dette er en {TAG0}vigtig{TAG1} tekst.",
        "without_tags": "Dette er en vigtig tekst.",
    },

    # ============================================================
    # ROMANCE LANGUAGES
    # ============================================================
    "spanish": {
        "with_tags": f"Este es un texto {TAG0}importante{TAG1}.",
        "without_tags": "Este es un texto importante.",
    },
    "french": {
        "with_tags": f"C'est un texte {TAG0}important{TAG1}.",
        "without_tags": "C'est un texte important.",
    },
    "portuguese": {
        "with_tags": f"Este é um texto {TAG0}importante{TAG1}.",
        "without_tags": "Este é um texto importante.",
    },
    "italian": {
        "with_tags": f"Questo è un testo {TAG0}importante{TAG1}.",
        "without_tags": "Questo è un testo importante.",
    },
    "romanian": {
        "with_tags": f"Acesta este un text {TAG0}important{TAG1}.",
        "without_tags": "Acesta este un text important.",
    },
    "catalan": {
        "with_tags": f"Aquest és un text {TAG0}important{TAG1}.",
        "without_tags": "Aquest és un text important.",
    },

    # ============================================================
    # SLAVIC LANGUAGES
    # ============================================================
    "russian": {
        "with_tags": f"Это {TAG0}важный{TAG1} текст.",
        "without_tags": "Это важный текст.",
    },
    "ukrainian": {
        "with_tags": f"Це {TAG0}важливий{TAG1} текст.",
        "without_tags": "Це важливий текст.",
    },
    "polish": {
        "with_tags": f"To jest {TAG0}ważny{TAG1} tekst.",
        "without_tags": "To jest ważny tekst.",
    },
    "czech": {
        "with_tags": f"Toto je {TAG0}důležitý{TAG1} text.",
        "without_tags": "Toto je důležitý text.",
    },
    "slovak": {
        "with_tags": f"Toto je {TAG0}dôležitý{TAG1} text.",
        "without_tags": "Toto je dôležitý text.",
    },
    "serbian": {
        "with_tags": f"Ovo je {TAG0}važan{TAG1} tekst.",
        "without_tags": "Ovo je važan tekst.",
    },
    "croatian": {
        "with_tags": f"Ovo je {TAG0}važan{TAG1} tekst.",
        "without_tags": "Ovo je važan tekst.",
    },
    "bulgarian": {
        "with_tags": f"Това е {TAG0}важен{TAG1} текст.",
        "without_tags": "Това е важен текст.",
    },

    # ============================================================
    # EAST ASIAN LANGUAGES
    # ============================================================
    "chinese": {
        "with_tags": f"这是{TAG0}重要的{TAG1}文本。",
        "without_tags": "这是重要的文本。",
    },
    "japanese": {
        "with_tags": f"これは{TAG0}重要な{TAG1}テキストです。",
        "without_tags": "これは重要なテキストです。",
    },
    "korean": {
        "with_tags": f"이것은 {TAG0}중요한{TAG1} 텍스트입니다.",
        "without_tags": "이것은 중요한 텍스트입니다.",
    },

    # ============================================================
    # SOUTH ASIAN LANGUAGES
    # ============================================================
    "hindi": {
        "with_tags": f"यह {TAG0}महत्वपूर्ण{TAG1} पाठ है।",
        "without_tags": "यह महत्वपूर्ण पाठ है।",
    },
    "bengali": {
        "with_tags": f"এটি {TAG0}গুরুত্বপূর্ণ{TAG1} পাঠ্য।",
        "without_tags": "এটি গুরুত্বপূর্ণ পাঠ্য।",
    },
    "urdu": {
        "with_tags": f"یہ {TAG0}اہم{TAG1} متن ہے۔",
        "without_tags": "یہ اہم متن ہے۔",
    },
    "punjabi": {
        "with_tags": f"ਇਹ {TAG0}ਮਹੱਤਵਪੂਰਨ{TAG1} ਟੈਕਸਟ ਹੈ।",
        "without_tags": "ਇਹ ਮਹੱਤਵਪੂਰਨ ਟੈਕਸਟ ਹੈ।",
    },
    "tamil": {
        "with_tags": f"இது {TAG0}முக்கியமான{TAG1} உரை.",
        "without_tags": "இது முக்கியமான உரை.",
    },
    "telugu": {
        "with_tags": f"ఇది {TAG0}ముఖ్యమైన{TAG1} వచనం.",
        "without_tags": "ఇది ముఖ్యమైన వచనం.",
    },
    "marathi": {
        "with_tags": f"हा {TAG0}महत्त्वाचा{TAG1} मजकूर आहे.",
        "without_tags": "हा महत्त्वाचा मजकूर आहे.",
    },
    "gujarati": {
        "with_tags": f"આ {TAG0}મહત્વપૂર્ણ{TAG1} ટેક્સ્ટ છે.",
        "without_tags": "આ મહત્વપૂર્ણ ટેક્સ્ટ છે.",
    },

    # ============================================================
    # SOUTHEAST ASIAN LANGUAGES
    # ============================================================
    "vietnamese": {
        "with_tags": f"Đây là văn bản {TAG0}quan trọng{TAG1}.",
        "without_tags": "Đây là văn bản quan trọng.",
    },
    "thai": {
        "with_tags": f"นี่คือข้อความ{TAG0}สำคัญ{TAG1}",
        "without_tags": "นี่คือข้อความสำคัญ",
    },
    "indonesian": {
        "with_tags": f"Ini adalah teks {TAG0}penting{TAG1}.",
        "without_tags": "Ini adalah teks penting.",
    },
    "malay": {
        "with_tags": f"Ini adalah teks {TAG0}penting{TAG1}.",
        "without_tags": "Ini adalah teks penting.",
    },
    "tagalog": {
        "with_tags": f"Ito ay {TAG0}mahalagang{TAG1} teksto.",
        "without_tags": "Ito ay mahalagang teksto.",
    },
    "burmese": {
        "with_tags": f"ဤသည် {TAG0}အရေးကြီးသော{TAG1} စာသားဖြစ်သည်။",
        "without_tags": "ဤသည် အရေးကြီးသော စာသားဖြစ်သည်။",
    },

    # ============================================================
    # MIDDLE EASTERN LANGUAGES
    # ============================================================
    "arabic": {
        "with_tags": f"هذا نص {TAG0}مهم{TAG1}.",
        "without_tags": "هذا نص مهم.",
    },
    "persian": {
        "with_tags": f"این یک متن {TAG0}مهم{TAG1} است.",
        "without_tags": "این یک متن مهم است.",
    },
    "turkish": {
        "with_tags": f"Bu {TAG0}önemli{TAG1} bir metindir.",
        "without_tags": "Bu önemli bir metindir.",
    },
    "hebrew": {
        "with_tags": f"זהו טקסט {TAG0}חשוב{TAG1}.",
        "without_tags": "זהו טקסט חשוב.",
    },

    # ============================================================
    # OTHER EUROPEAN LANGUAGES
    # ============================================================
    "greek": {
        "with_tags": f"Αυτό είναι ένα {TAG0}σημαντικό{TAG1} κείμενο.",
        "without_tags": "Αυτό είναι ένα σημαντικό κείμενο.",
    },
    "hungarian": {
        "with_tags": f"Ez egy {TAG0}fontos{TAG1} szöveg.",
        "without_tags": "Ez egy fontos szöveg.",
    },
    "finnish": {
        "with_tags": f"Tämä on {TAG0}tärkeä{TAG1} teksti.",
        "without_tags": "Tämä on tärkeä teksti.",
    },

    # ============================================================
    # AFRICAN LANGUAGES
    # ============================================================
    "swahili": {
        "with_tags": f"Hii ni maandishi {TAG0}muhimu{TAG1}.",
        "without_tags": "Hii ni maandishi muhimu.",
    },
    "amharic": {
        "with_tags": f"ይህ {TAG0}አስፈላጊ{TAG1} ጽሑፍ ነው።",
        "without_tags": "ይህ አስፈላጊ ጽሑፍ ነው።",
    },
}

# Default fallback language
DEFAULT_LANGUAGE = "english"


def get_example_for_pair(source_lang: str, target_lang: str) -> Dict[str, str]:
    """
    Generate a placeholder example for any language pair.

    Args:
        source_lang: Source language name
        target_lang: Target language name

    Returns:
        Dict with "source", "correct", "wrong" keys
    """
    source_key = source_lang.lower()
    target_key = target_lang.lower()

    # Get source language text (fallback to English)
    source_data = TRANSLATIONS.get(source_key, TRANSLATIONS[DEFAULT_LANGUAGE])

    # Get target language text (fallback to English)
    target_data = TRANSLATIONS.get(target_key, TRANSLATIONS[DEFAULT_LANGUAGE])

    return {
        "source": source_data["with_tags"],
        "correct": target_data["with_tags"],
        "wrong": target_data["without_tags"],
    }


# Legacy compatibility: PLACEHOLDER_EXAMPLES dictionary
# This is now generated dynamically but kept for backward compatibility
def _build_placeholder_examples() -> Dict[Tuple[str, str], Dict[str, str]]:
    """Build the legacy PLACEHOLDER_EXAMPLES dict for backward compatibility."""
    examples = {}
    languages = list(TRANSLATIONS.keys())

    for source in languages:
        for target in languages:
            if source != target:
                examples[(source, target)] = get_example_for_pair(source, target)

    return examples


PLACEHOLDER_EXAMPLES = _build_placeholder_examples()
