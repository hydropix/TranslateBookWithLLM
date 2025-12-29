"""
Output format examples for translation prompts.

These examples show expected output format in different target languages.
Uses the same sentence: "In this quiet night, the moonlight bathed the entire valley."
"""

from typing import Dict
from .constants import TAG0, TAG1

# Single sentence translated into all supported languages
# Format: "In this quiet night, the [TAG0]moonlight[TAG1] bathed the entire valley."
OUTPUT_FORMAT_EXAMPLES: Dict[str, Dict[str, str]] = {
    # ============================================================
    # GERMANIC LANGUAGES
    # ============================================================
    "english": {
        "fast_mode": "In this quiet night, the moonlight bathed the entire valley.",
        "standard": f"In this quiet night, the {TAG0}moonlight{TAG1} bathed the entire valley.",
    },
    "german": {
        "fast_mode": "In dieser ruhigen Nacht badete das Mondlicht das ganze Tal.",
        "standard": f"In dieser ruhigen Nacht badete {TAG0}das Mondlicht{TAG1} das ganze Tal.",
    },
    "dutch": {
        "fast_mode": "In deze rustige nacht baadde het maanlicht de hele vallei.",
        "standard": f"In deze rustige nacht baadde {TAG0}het maanlicht{TAG1} de hele vallei.",
    },
    "swedish": {
        "fast_mode": "I denna tysta natt badade månljuset hela dalen.",
        "standard": f"I denna tysta natt badade {TAG0}månljuset{TAG1} hela dalen.",
    },
    "norwegian": {
        "fast_mode": "I denne stille natten badet månelyset hele dalen.",
        "standard": f"I denne stille natten badet {TAG0}månelyset{TAG1} hele dalen.",
    },
    "danish": {
        "fast_mode": "I denne stille nat badede månelyset hele dalen.",
        "standard": f"I denne stille nat badede {TAG0}månelyset{TAG1} hele dalen.",
    },

    # ============================================================
    # ROMANCE LANGUAGES
    # ============================================================
    "spanish": {
        "fast_mode": "En esta noche tranquila, la luz de la luna bañaba todo el valle.",
        "standard": f"En esta noche tranquila, {TAG0}la luz de la luna{TAG1} bañaba todo el valle.",
    },
    "french": {
        "fast_mode": "Dans cette nuit paisible, le clair de lune baignait toute la vallée.",
        "standard": f"Dans cette nuit paisible, {TAG0}le clair de lune{TAG1} baignait toute la vallée.",
    },
    "portuguese": {
        "fast_mode": "Nesta noite tranquila, o luar banhava todo o vale.",
        "standard": f"Nesta noite tranquila, {TAG0}o luar{TAG1} banhava todo o vale.",
    },
    "italian": {
        "fast_mode": "In questa notte tranquilla, il chiaro di luna bagnava tutta la valle.",
        "standard": f"In questa notte tranquilla, {TAG0}il chiaro di luna{TAG1} bagnava tutta la valle.",
    },
    "romanian": {
        "fast_mode": "În această noapte liniștită, lumina lunii scălda întreaga vale.",
        "standard": f"În această noapte liniștită, {TAG0}lumina lunii{TAG1} scălda întreaga vale.",
    },
    "catalan": {
        "fast_mode": "En aquesta nit tranquil·la, la llum de la lluna banyava tota la vall.",
        "standard": f"En aquesta nit tranquil·la, {TAG0}la llum de la lluna{TAG1} banyava tota la vall.",
    },

    # ============================================================
    # SLAVIC LANGUAGES
    # ============================================================
    "russian": {
        "fast_mode": "В эту тихую ночь лунный свет заливал всю долину.",
        "standard": f"В эту тихую ночь {TAG0}лунный свет{TAG1} заливал всю долину.",
    },
    "ukrainian": {
        "fast_mode": "У цю тиху ніч місячне світло заливало всю долину.",
        "standard": f"У цю тиху ніч {TAG0}місячне світло{TAG1} заливало всю долину.",
    },
    "polish": {
        "fast_mode": "W tę cichą noc światło księżyca zalało całą dolinę.",
        "standard": f"W tę cichą noc {TAG0}światło księżyca{TAG1} zalało całą dolinę.",
    },
    "czech": {
        "fast_mode": "V tuto tichou noc měsíční světlo zalilo celé údolí.",
        "standard": f"V tuto tichou noc {TAG0}měsíční světlo{TAG1} zalilo celé údolí.",
    },
    "slovak": {
        "fast_mode": "V túto tichú noc mesačné svetlo zalievalo celé údolie.",
        "standard": f"V túto tichú noc {TAG0}mesačné svetlo{TAG1} zalievalo celé údolie.",
    },
    "serbian": {
        "fast_mode": "U ovoj tihoj noći mesečina je okupala celu dolinu.",
        "standard": f"U ovoj tihoj noći {TAG0}mesečina{TAG1} je okupala celu dolinu.",
    },
    "croatian": {
        "fast_mode": "U ovoj tihoj noći mjesečina je okupala cijelu dolinu.",
        "standard": f"U ovoj tihoj noći {TAG0}mjesečina{TAG1} je okupala cijelu dolinu.",
    },
    "bulgarian": {
        "fast_mode": "В тази тиха нощ лунната светлина обливаше цялата долина.",
        "standard": f"В тази тиха нощ {TAG0}лунната светлина{TAG1} обливаше цялата долина.",
    },

    # ============================================================
    # EAST ASIAN LANGUAGES
    # ============================================================
    "chinese": {
        "fast_mode": "在这个宁静的夜晚，月光洒满了整个山谷。",
        "standard": f"在这个宁静的夜晚，{TAG0}月光{TAG1}洒满了整个山谷。",
    },
    "japanese": {
        "fast_mode": "この静かな夜、月光が谷全体を照らしていました。",
        "standard": f"この静かな夜、{TAG0}月光{TAG1}が谷全体を照らしていました。",
    },
    "korean": {
        "fast_mode": "이 고요한 밤, 달빛이 온 계곡을 비추고 있었습니다.",
        "standard": f"이 고요한 밤, {TAG0}달빛{TAG1}이 온 계곡을 비추고 있었습니다.",
    },

    # ============================================================
    # SOUTH ASIAN LANGUAGES
    # ============================================================
    "hindi": {
        "fast_mode": "इस शांत रात में, चांदनी पूरी घाटी को नहला रही थी।",
        "standard": f"इस शांत रात में, {TAG0}चांदनी{TAG1} पूरी घाटी को नहला रही थी।",
    },
    "bengali": {
        "fast_mode": "এই শান্ত রাতে, চাঁদের আলো পুরো উপত্যকা জুড়ে ছড়িয়ে পড়েছিল।",
        "standard": f"এই শান্ত রাতে, {TAG0}চাঁদের আলো{TAG1} পুরো উপত্যকা জুড়ে ছড়িয়ে পড়েছিল।",
    },
    "urdu": {
        "fast_mode": "اس پرسکون رات میں، چاندنی نے پوری وادی کو نہلا دیا۔",
        "standard": f"اس پرسکون رات میں، {TAG0}چاندنی{TAG1} نے پوری وادی کو نہلا دیا۔",
    },
    "punjabi": {
        "fast_mode": "ਇਸ ਸ਼ਾਂਤ ਰਾਤ ਵਿੱਚ, ਚੰਦਰਮਾ ਦੀ ਰੌਸ਼ਨੀ ਨੇ ਸਾਰੀ ਵਾਦੀ ਨੂੰ ਨਹਾ ਦਿੱਤਾ।",
        "standard": f"ਇਸ ਸ਼ਾਂਤ ਰਾਤ ਵਿੱਚ, {TAG0}ਚੰਦਰਮਾ ਦੀ ਰੌਸ਼ਨੀ{TAG1} ਨੇ ਸਾਰੀ ਵਾਦੀ ਨੂੰ ਨਹਾ ਦਿੱਤਾ।",
    },
    "tamil": {
        "fast_mode": "இந்த அமைதியான இரவில், நிலவொளி முழு பள்ளத்தாக்கையும் குளிப்பாட்டியது.",
        "standard": f"இந்த அமைதியான இரவில், {TAG0}நிலவொளி{TAG1} முழு பள்ளத்தாக்கையும் குளிப்பாட்டியது.",
    },
    "telugu": {
        "fast_mode": "ఈ ప్రశాంతమైన రాత్రిలో, వెన్నెల మొత్తం లోయను స్నానం చేయించింది.",
        "standard": f"ఈ ప్రశాంతమైన రాత్రిలో, {TAG0}వెన్నెల{TAG1} మొత్తం లోయను స్నానం చేయించింది.",
    },
    "marathi": {
        "fast_mode": "या शांत रात्री, चंद्रप्रकाशाने संपूर्ण दरी न्हाऊन निघाली.",
        "standard": f"या शांत रात्री, {TAG0}चंद्रप्रकाशाने{TAG1} संपूर्ण दरी न्हाऊन निघाली.",
    },
    "gujarati": {
        "fast_mode": "આ શાંત રાત્રે, ચંદ્રપ્રકાશ આખી ખીણને નવડાવી રહ્યો હતો.",
        "standard": f"આ શાંત રાત્રે, {TAG0}ચંદ્રપ્રકાશ{TAG1} આખી ખીણને નવડાવી રહ્યો હતો.",
    },

    # ============================================================
    # SOUTHEAST ASIAN LANGUAGES
    # ============================================================
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
    "malay": {
        "fast_mode": "Pada malam yang tenang ini, cahaya bulan membasahi seluruh lembah.",
        "standard": f"Pada malam yang tenang ini, {TAG0}cahaya bulan{TAG1} membasahi seluruh lembah.",
    },
    "tagalog": {
        "fast_mode": "Sa tahimik na gabing ito, niligo ng liwanag ng buwan ang buong lambak.",
        "standard": f"Sa tahimik na gabing ito, niligo ng {TAG0}liwanag ng buwan{TAG1} ang buong lambak.",
    },
    "burmese": {
        "fast_mode": "ဤတိတ်ဆိတ်သောညတွင် လရောင်သည် တောင်ကြားတစ်ခုလုံးကို ရေချိုးပေးခဲ့သည်။",
        "standard": f"ဤတိတ်ဆိတ်သောညတွင် {TAG0}လရောင်{TAG1}သည် တောင်ကြားတစ်ခုလုံးကို ရေချိုးပေးခဲ့သည်။",
    },

    # ============================================================
    # MIDDLE EASTERN LANGUAGES
    # ============================================================
    "arabic": {
        "fast_mode": "في هذه الليلة الهادئة، كان ضوء القمر يغمر الوادي بأكمله.",
        "standard": f"في هذه الليلة الهادئة، كان {TAG0}ضوء القمر{TAG1} يغمر الوادي بأكمله.",
    },
    "persian": {
        "fast_mode": "در این شب آرام، نور ماه تمام دره را غرق کرده بود.",
        "standard": f"در این شب آرام، {TAG0}نور ماه{TAG1} تمام دره را غرق کرده بود.",
    },
    "turkish": {
        "fast_mode": "Bu sakin gecede, ay ışığı tüm vadiyi aydınlatıyordu.",
        "standard": f"Bu sakin gecede, {TAG0}ay ışığı{TAG1} tüm vadiyi aydınlatıyordu.",
    },
    "hebrew": {
        "fast_mode": "בלילה השקט הזה, אור הירח הציף את כל העמק.",
        "standard": f"בלילה השקט הזה, {TAG0}אור הירח{TAG1} הציף את כל העמק.",
    },

    # ============================================================
    # OTHER EUROPEAN LANGUAGES
    # ============================================================
    "greek": {
        "fast_mode": "Σε αυτή την ήσυχη νύχτα, το φως του φεγγαριού λούζε ολόκληρη την κοιλάδα.",
        "standard": f"Σε αυτή την ήσυχη νύχτα, {TAG0}το φως του φεγγαριού{TAG1} λούζε ολόκληρη την κοιλάδα.",
    },
    "hungarian": {
        "fast_mode": "Ezen a csendes éjszakán a holdfény fürdette az egész völgyet.",
        "standard": f"Ezen a csendes éjszakán {TAG0}a holdfény{TAG1} fürdette az egész völgyet.",
    },
    "finnish": {
        "fast_mode": "Tänä hiljaisena yönä kuunvalo kylpi koko laakson.",
        "standard": f"Tänä hiljaisena yönä {TAG0}kuunvalo{TAG1} kylpi koko laakson.",
    },

    # ============================================================
    # AFRICAN LANGUAGES
    # ============================================================
    "swahili": {
        "fast_mode": "Katika usiku huu wa utulivu, mwanga wa mwezi uliiosha bonde lote.",
        "standard": f"Katika usiku huu wa utulivu, {TAG0}mwanga wa mwezi{TAG1} uliiosha bonde lote.",
    },
    "amharic": {
        "fast_mode": "በዚህ ጸጥ ባለ ምሽት፣ የጨረቃ ብርሃን መላውን ሸለቆ አጠበ።",
        "standard": f"በዚህ ጸጥ ባለ ምሽት፣ {TAG0}የጨረቃ ብርሃን{TAG1} መላውን ሸለቆ አጠበ።",
    },
}
