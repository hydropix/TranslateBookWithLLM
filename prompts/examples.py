"""
Multilingual examples for translation prompts.

This module provides language-specific examples for:
- Placeholder preservation (HTML/XML tags)
- Image marker preservation (fast mode)
- Subtitle format examples
- Output format examples

All examples use the actual constants from src/config.py to ensure consistency.
"""

from typing import Dict, Tuple, Optional
from src.config import (
    create_placeholder,
    IMAGE_MARKER_PREFIX,
    IMAGE_MARKER_SUFFIX,
)

# ============================================================================
# DYNAMIC PLACEHOLDER GENERATION
# ============================================================================

# Generate placeholders using the actual config constants
TAG0 = create_placeholder(0)  # e.g., [TAG0]
TAG1 = create_placeholder(1)  # e.g., [TAG1]
TAG2 = create_placeholder(2)  # e.g., [TAG2]

# Image marker example
IMG_MARKER = f"{IMAGE_MARKER_PREFIX}001{IMAGE_MARKER_SUFFIX}"  # e.g., [IMG001]
IMG_MARKER_2 = f"{IMAGE_MARKER_PREFIX}002{IMAGE_MARKER_SUFFIX}"


# ============================================================================
# PLACEHOLDER PRESERVATION EXAMPLES
# ============================================================================

# Key: (source_language, target_language) - both lowercase
# Value: dict with "source", "correct", "wrong" examples
PLACEHOLDER_EXAMPLES: Dict[Tuple[str, str], Dict[str, str]] = {
    # English as source
    ("english", "chinese"): {
        "source": f"This is {TAG0}very important{TAG1} information",
        "correct": f"这是{TAG0}非常重要的{TAG1}信息",
        "wrong": "这是非常重要的信息",
    },
    ("english", "french"): {
        "source": f"This is {TAG0}very important{TAG1} information",
        "correct": f"C'est une information {TAG0}très importante{TAG1}",
        "wrong": "C'est une information très importante",
    },
    ("english", "spanish"): {
        "source": f"This is {TAG0}very important{TAG1} information",
        "correct": f"Esta es una información {TAG0}muy importante{TAG1}",
        "wrong": "Esta es una información muy importante",
    },
    ("english", "german"): {
        "source": f"This is {TAG0}very important{TAG1} information",
        "correct": f"Dies ist eine {TAG0}sehr wichtige{TAG1} Information",
        "wrong": "Dies ist eine sehr wichtige Information",
    },
    ("english", "italian"): {
        "source": f"This is {TAG0}very important{TAG1} information",
        "correct": f"Questa è un'informazione {TAG0}molto importante{TAG1}",
        "wrong": "Questa è un'informazione molto importante",
    },
    ("english", "portuguese"): {
        "source": f"This is {TAG0}very important{TAG1} information",
        "correct": f"Esta é uma informação {TAG0}muito importante{TAG1}",
        "wrong": "Esta é uma informação muito importante",
    },
    ("english", "russian"): {
        "source": f"This is {TAG0}very important{TAG1} information",
        "correct": f"Это {TAG0}очень важная{TAG1} информация",
        "wrong": "Это очень важная информация",
    },
    ("english", "japanese"): {
        "source": f"This is {TAG0}very important{TAG1} information",
        "correct": f"これは{TAG0}非常に重要な{TAG1}情報です",
        "wrong": "これは非常に重要な情報です",
    },
    ("english", "korean"): {
        "source": f"This is {TAG0}very important{TAG1} information",
        "correct": f"이것은 {TAG0}매우 중요한{TAG1} 정보입니다",
        "wrong": "이것은 매우 중요한 정보입니다",
    },
    ("english", "arabic"): {
        "source": f"This is {TAG0}very important{TAG1} information",
        "correct": f"هذه معلومات {TAG0}مهمة جداً{TAG1}",
        "wrong": "هذه معلومات مهمة جداً",
    },
    ("english", "dutch"): {
        "source": f"This is {TAG0}very important{TAG1} information",
        "correct": f"Dit is {TAG0}zeer belangrijke{TAG1} informatie",
        "wrong": "Dit is zeer belangrijke informatie",
    },
    ("english", "polish"): {
        "source": f"This is {TAG0}very important{TAG1} information",
        "correct": f"To jest {TAG0}bardzo ważna{TAG1} informacja",
        "wrong": "To jest bardzo ważna informacja",
    },
    ("english", "turkish"): {
        "source": f"This is {TAG0}very important{TAG1} information",
        "correct": f"Bu {TAG0}çok önemli{TAG1} bir bilgidir",
        "wrong": "Bu çok önemli bir bilgidir",
    },
    ("english", "vietnamese"): {
        "source": f"This is {TAG0}very important{TAG1} information",
        "correct": f"Đây là thông tin {TAG0}rất quan trọng{TAG1}",
        "wrong": "Đây là thông tin rất quan trọng",
    },
    ("english", "thai"): {
        "source": f"This is {TAG0}very important{TAG1} information",
        "correct": f"นี่คือข้อมูล{TAG0}ที่สำคัญมาก{TAG1}",
        "wrong": "นี่คือข้อมูลที่สำคัญมาก",
    },
    ("english", "indonesian"): {
        "source": f"This is {TAG0}very important{TAG1} information",
        "correct": f"Ini adalah informasi {TAG0}yang sangat penting{TAG1}",
        "wrong": "Ini adalah informasi yang sangat penting",
    },
    ("english", "hindi"): {
        "source": f"This is {TAG0}very important{TAG1} information",
        "correct": f"यह {TAG0}बहुत महत्वपूर्ण{TAG1} जानकारी है",
        "wrong": "यह बहुत महत्वपूर्ण जानकारी है",
    },

    # French as source
    ("french", "english"): {
        "source": f"C'est une information {TAG0}très importante{TAG1}",
        "correct": f"This is {TAG0}very important{TAG1} information",
        "wrong": "This is very important information",
    },
    ("french", "chinese"): {
        "source": f"C'est une information {TAG0}très importante{TAG1}",
        "correct": f"这是{TAG0}非常重要的{TAG1}信息",
        "wrong": "这是非常重要的信息",
    },
    ("french", "spanish"): {
        "source": f"C'est une information {TAG0}très importante{TAG1}",
        "correct": f"Esta es una información {TAG0}muy importante{TAG1}",
        "wrong": "Esta es una información muy importante",
    },
    ("french", "german"): {
        "source": f"C'est une information {TAG0}très importante{TAG1}",
        "correct": f"Dies ist eine {TAG0}sehr wichtige{TAG1} Information",
        "wrong": "Dies ist eine sehr wichtige Information",
    },

    # Spanish as source
    ("spanish", "english"): {
        "source": f"Esta es una información {TAG0}muy importante{TAG1}",
        "correct": f"This is {TAG0}very important{TAG1} information",
        "wrong": "This is very important information",
    },
    ("spanish", "french"): {
        "source": f"Esta es una información {TAG0}muy importante{TAG1}",
        "correct": f"C'est une information {TAG0}très importante{TAG1}",
        "wrong": "C'est une information très importante",
    },
    ("spanish", "chinese"): {
        "source": f"Esta es una información {TAG0}muy importante{TAG1}",
        "correct": f"这是{TAG0}非常重要的{TAG1}信息",
        "wrong": "这是非常重要的信息",
    },

    # German as source
    ("german", "english"): {
        "source": f"Dies ist eine {TAG0}sehr wichtige{TAG1} Information",
        "correct": f"This is {TAG0}very important{TAG1} information",
        "wrong": "This is very important information",
    },
    ("german", "french"): {
        "source": f"Dies ist eine {TAG0}sehr wichtige{TAG1} Information",
        "correct": f"C'est une information {TAG0}très importante{TAG1}",
        "wrong": "C'est une information très importante",
    },

    # Chinese as source
    ("chinese", "english"): {
        "source": f"这是{TAG0}非常重要的{TAG1}信息",
        "correct": f"This is {TAG0}very important{TAG1} information",
        "wrong": "This is very important information",
    },
    ("chinese", "french"): {
        "source": f"这是{TAG0}非常重要的{TAG1}信息",
        "correct": f"C'est une information {TAG0}très importante{TAG1}",
        "wrong": "C'est une information très importante",
    },
    ("chinese", "japanese"): {
        "source": f"这是{TAG0}非常重要的{TAG1}信息",
        "correct": f"これは{TAG0}非常に重要な{TAG1}情報です",
        "wrong": "これは非常に重要な情報です",
    },

    # Japanese as source
    ("japanese", "english"): {
        "source": f"これは{TAG0}非常に重要な{TAG1}情報です",
        "correct": f"This is {TAG0}very important{TAG1} information",
        "wrong": "This is very important information",
    },
    ("japanese", "chinese"): {
        "source": f"これは{TAG0}非常に重要な{TAG1}情報です",
        "correct": f"这是{TAG0}非常重要的{TAG1}信息",
        "wrong": "这是非常重要的信息",
    },

    # Russian as source
    ("russian", "english"): {
        "source": f"Это {TAG0}очень важная{TAG1} информация",
        "correct": f"This is {TAG0}very important{TAG1} information",
        "wrong": "This is very important information",
    },
    ("russian", "french"): {
        "source": f"Это {TAG0}очень важная{TAG1} информация",
        "correct": f"C'est une information {TAG0}très importante{TAG1}",
        "wrong": "C'est une information très importante",
    },
}


# ============================================================================
# IMAGE PLACEHOLDER EXAMPLES (FAST MODE)
# ============================================================================

IMAGE_EXAMPLES: Dict[Tuple[str, str], Dict[str, str]] = {
    ("english", "chinese"): {
        "source": f"The sun rose.\n\n{IMG_MARKER}\n\nBirds sang.",
        "correct": f"太阳升起。\n\n{IMG_MARKER}\n\n鸟儿歌唱。",
        "wrong": f"太阳升起。\n鸟儿歌唱。\n{IMG_MARKER}",
    },
    ("english", "french"): {
        "source": f"The sun rose.\n\n{IMG_MARKER}\n\nBirds sang.",
        "correct": f"Le soleil se leva.\n\n{IMG_MARKER}\n\nLes oiseaux chantaient.",
        "wrong": f"Le soleil se leva.\nLes oiseaux chantaient.\n{IMG_MARKER}",
    },
    ("english", "spanish"): {
        "source": f"The sun rose.\n\n{IMG_MARKER}\n\nBirds sang.",
        "correct": f"El sol salió.\n\n{IMG_MARKER}\n\nLos pájaros cantaban.",
        "wrong": f"El sol salió.\nLos pájaros cantaban.\n{IMG_MARKER}",
    },
    ("english", "german"): {
        "source": f"The sun rose.\n\n{IMG_MARKER}\n\nBirds sang.",
        "correct": f"Die Sonne ging auf.\n\n{IMG_MARKER}\n\nVögel sangen.",
        "wrong": f"Die Sonne ging auf.\nVögel sangen.\n{IMG_MARKER}",
    },
    ("english", "japanese"): {
        "source": f"The sun rose.\n\n{IMG_MARKER}\n\nBirds sang.",
        "correct": f"太陽が昇った。\n\n{IMG_MARKER}\n\n鳥が歌った。",
        "wrong": f"太陽が昇った。\n鳥が歌った。\n{IMG_MARKER}",
    },
}


# ============================================================================
# SUBTITLE FORMAT EXAMPLES
# ============================================================================

SUBTITLE_EXAMPLES: Dict[str, str] = {
    "chinese": "[1]第一行翻译文本\n[2]第二行翻译文本",
    "french": "[1]Première ligne traduite\n[2]Deuxième ligne traduite",
    "spanish": "[1]Primera línea traducida\n[2]Segunda línea traducida",
    "german": "[1]Erste übersetzte Zeile\n[2]Zweite übersetzte Zeile",
    "italian": "[1]Prima riga tradotta\n[2]Seconda riga tradotta",
    "portuguese": "[1]Primeira linha traduzida\n[2]Segunda linha traduzida",
    "russian": "[1]Первая переведенная строка\n[2]Вторая переведенная строка",
    "japanese": "[1]最初の翻訳行\n[2]2番目の翻訳行",
    "korean": "[1]첫 번째 번역 줄\n[2]두 번째 번역 줄",
    "arabic": "[1]السطر الأول المترجم\n[2]السطر الثاني المترجم",
    "dutch": "[1]Eerste vertaalde regel\n[2]Tweede vertaalde regel",
    "polish": "[1]Pierwsza przetłumaczona linia\n[2]Druga przetłumaczona linia",
    "turkish": "[1]İlk çevrilmiş satır\n[2]İkinci çevrilmiş satır",
    "vietnamese": "[1]Dòng dịch đầu tiên\n[2]Dòng dịch thứ hai",
    "thai": "[1]บรรทัดแปลแรก\n[2]บรรทัดแปลที่สอง",
    "indonesian": "[1]Baris terjemahan pertama\n[2]Baris terjemahan kedua",
    "hindi": "[1]पहली अनुवादित पंक्ति\n[2]दूसरी अनुवादित पंक्ति",
}


# ============================================================================
# OUTPUT FORMAT EXAMPLES (for example_texts in prompts.py)
# ============================================================================

# Simple output format example text by target language
OUTPUT_FORMAT_EXAMPLES: Dict[str, Dict[str, str]] = {
    "chinese": {
        "fast_mode": "在这个宁静的夜晚，月光洒满了整个山谷。",
        "standard": f"在这个宁静的夜晚，{TAG0}月光{TAG1}洒满了整个山谷。",
    },
    "french": {
        "fast_mode": "Dans cette nuit paisible, le clair de lune baignait toute la vallée.",
        "standard": f"Dans cette nuit paisible, {TAG0}le clair de lune{TAG1} baignait toute la vallée.",
    },
    "spanish": {
        "fast_mode": "En esta noche tranquila, la luz de la luna bañaba todo el valle.",
        "standard": f"En esta noche tranquila, {TAG0}la luz de la luna{TAG1} bañaba todo el valle.",
    },
    "german": {
        "fast_mode": "In dieser ruhigen Nacht badete das Mondlicht das ganze Tal.",
        "standard": f"In dieser ruhigen Nacht badete {TAG0}das Mondlicht{TAG1} das ganze Tal.",
    },
    "italian": {
        "fast_mode": "In questa notte tranquilla, il chiaro di luna bagnava tutta la valle.",
        "standard": f"In questa notte tranquilla, {TAG0}il chiaro di luna{TAG1} bagnava tutta la valle.",
    },
    "portuguese": {
        "fast_mode": "Nesta noite tranquila, o luar banhava todo o vale.",
        "standard": f"Nesta noite tranquila, {TAG0}o luar{TAG1} banhava todo o vale.",
    },
    "russian": {
        "fast_mode": "В эту тихую ночь лунный свет заливал всю долину.",
        "standard": f"В эту тихую ночь {TAG0}лунный свет{TAG1} заливал всю долину.",
    },
    "japanese": {
        "fast_mode": "この静かな夜、月光が谷全体を照らしていました。",
        "standard": f"この静かな夜、{TAG0}月光{TAG1}が谷全体を照らしていました。",
    },
    "korean": {
        "fast_mode": "이 고요한 밤, 달빛이 온 계곡을 비추고 있었습니다.",
        "standard": f"이 고요한 밤, {TAG0}달빛{TAG1}이 온 계곡을 비추고 있었습니다.",
    },
    "arabic": {
        "fast_mode": "في هذه الليلة الهادئة، كان ضوء القمر يغمر الوادي بأكمله.",
        "standard": f"في هذه الليلة الهادئة، كان {TAG0}ضوء القمر{TAG1} يغمر الوادي بأكمله.",
    },
    "dutch": {
        "fast_mode": "In deze rustige nacht baadde het maanlicht de hele vallei.",
        "standard": f"In deze rustige nacht baadde {TAG0}het maanlicht{TAG1} de hele vallei.",
    },
    "polish": {
        "fast_mode": "W tę cichą noc światło księżyca zalało całą dolinę.",
        "standard": f"W tę cichą noc {TAG0}światło księżyca{TAG1} zalało całą dolinę.",
    },
    "turkish": {
        "fast_mode": "Bu sakin gecede, ay ışığı tüm vadiyi aydınlatıyordu.",
        "standard": f"Bu sakin gecede, {TAG0}ay ışığı{TAG1} tüm vadiyi aydınlatıyordu.",
    },
    "vietnamese": {
        "fast_mode": "Trong đêm yên tĩnh này, ánh trăng tràn ngập khắp thung lũng.",
        "standard": f"Trong đêm yên tĩnh này, {TAG0}ánh trăng{TAG1} tràn ngập khắp thung lũng.",
    },
    "thai": {
        "fast_mode": "ในคืนที่เงียบสงบนี้ แสงจันทร์ส่องสว่างไปทั่วหุบเขา",
        "standard": f"ในคืนที่เงียบสงบนี้ {TAG0}แสงจันทร์{TAG1}ส่องสว่างไปทั่วหุบเขา",
    },
    "indonesian": {
        "fast_mode": "Di malam yang tenang ini, cahaya bulan membasahi seluruh lembah.",
        "standard": f"Di malam yang tenang ini, {TAG0}cahaya bulan{TAG1} membasahi seluruh lembah.",
    },
    "hindi": {
        "fast_mode": "इस शांत रात में, चांदनी पूरी घाटी को नहला रही थी।",
        "standard": f"इस शांत रात में, {TAG0}चांदनी{TAG1} पूरी घाटी को नहला रही थी।",
    },
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_placeholder_example(
    source_lang: str,
    target_lang: str
) -> Dict[str, str]:
    """
    Get placeholder preservation example for a language pair.

    Args:
        source_lang: Source language name
        target_lang: Target language name

    Returns:
        Dict with "source", "correct", "wrong" example strings.
        Falls back to English→target or generic example if pair not found.
    """
    key = (source_lang.lower(), target_lang.lower())

    # Direct match
    if key in PLACEHOLDER_EXAMPLES:
        return PLACEHOLDER_EXAMPLES[key]

    # Fallback: English as source
    fallback_key = ("english", target_lang.lower())
    if fallback_key in PLACEHOLDER_EXAMPLES:
        return PLACEHOLDER_EXAMPLES[fallback_key]

    # Ultimate fallback: English → Chinese (most common pair)
    return PLACEHOLDER_EXAMPLES[("english", "chinese")]


def get_image_example(
    source_lang: str,
    target_lang: str
) -> Dict[str, str]:
    """
    Get image placeholder example for a language pair.

    Args:
        source_lang: Source language name
        target_lang: Target language name

    Returns:
        Dict with "source", "correct", "wrong" example strings.
    """
    key = (source_lang.lower(), target_lang.lower())

    if key in IMAGE_EXAMPLES:
        return IMAGE_EXAMPLES[key]

    # Fallback: English as source
    fallback_key = ("english", target_lang.lower())
    if fallback_key in IMAGE_EXAMPLES:
        return IMAGE_EXAMPLES[fallback_key]

    # Ultimate fallback
    return IMAGE_EXAMPLES[("english", "chinese")]


def get_subtitle_example(target_lang: str) -> str:
    """
    Get subtitle format example for a target language.

    Args:
        target_lang: Target language name

    Returns:
        Formatted subtitle example string.
    """
    return SUBTITLE_EXAMPLES.get(
        target_lang.lower(),
        "[1]First translated line\n[2]Second translated line"
    )


def get_output_format_example(target_lang: str, fast_mode: bool = False) -> str:
    """
    Get output format example for a target language.

    Args:
        target_lang: Target language name
        fast_mode: If True, returns example without placeholders

    Returns:
        Example text in the target language.
    """
    lang_key = target_lang.lower()
    mode_key = "fast_mode" if fast_mode else "standard"

    if lang_key in OUTPUT_FORMAT_EXAMPLES:
        return OUTPUT_FORMAT_EXAMPLES[lang_key][mode_key]

    # Fallback to generic English text
    if fast_mode:
        return "Your translated text here"
    return f"Your translated text here, with all {TAG0} markers preserved exactly"


def build_placeholder_section(
    source_lang: str,
    target_lang: str
) -> str:
    """
    Build the complete placeholder preservation section with language-specific examples.

    Args:
        source_lang: Source language name
        target_lang: Target language name

    Returns:
        Formatted placeholder preservation instructions with examples.
    """
    example = get_placeholder_example(source_lang, target_lang)

    return f"""# PLACEHOLDER PRESERVATION (CRITICAL)

You will encounter placeholders like: {TAG0}, {TAG1}, {TAG2}
These represent HTML/XML tags that have been temporarily replaced.

**MANDATORY RULES:**
1. Keep ALL placeholders EXACTLY as they appear
2. Do NOT translate, modify, remove, or explain them
3. Maintain their EXACT position in the sentence structure
4. Do NOT add spaces around them unless present in the source

**Example ({source_lang.title()} -> {target_lang.title()}):**

{source_lang.title()}: "{example['source']}"
Correct: "{example['correct']}"
WRONG: "{example['wrong']}" (placeholders removed)
"""


def build_image_placeholder_section(
    source_lang: str,
    target_lang: str
) -> str:
    """
    Build the image placeholder preservation section with language-specific examples.

    Args:
        source_lang: Source language name
        target_lang: Target language name

    Returns:
        Formatted image placeholder preservation instructions.
    """
    example = get_image_example(source_lang, target_lang)

    return f"""# IMAGE MARKERS - PRESERVE EXACTLY

Markers like {IMG_MARKER} represent images. Keep them at their EXACT position.

**Example:**
Source: {example['source']}
✅ {example['correct']}
❌ {example['wrong']}
"""
