"""
Image placeholder examples for fast mode translation.

These examples show how to preserve image markers during translation.
"""

from typing import Dict, Tuple
from .constants import IMG_MARKER

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
    ("english", "korean"): {
        "source": f"The sun rose.\n\n{IMG_MARKER}\n\nBirds sang.",
        "correct": f"해가 떠올랐다.\n\n{IMG_MARKER}\n\n새들이 노래했다.",
        "wrong": f"해가 떠올랐다.\n새들이 노래했다.\n{IMG_MARKER}",
    },
    ("korean", "english"): {
        "source": f"해가 떠올랐다.\n\n{IMG_MARKER}\n\n새들이 노래했다.",
        "correct": f"The sun rose.\n\n{IMG_MARKER}\n\nBirds sang.",
        "wrong": f"The sun rose.\nBirds sang.\n{IMG_MARKER}",
    },
}
