"""
Output format examples for translation prompts.

These examples show expected output format in different target languages.
"""

from typing import Dict
from .constants import TAG0, TAG1

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
