"""
High-quality cultural translation examples.

These examples demonstrate HOW to translate idiomatically:
- Avoid word-for-word translation
- Respect cultural context and expressions
- Adapt idioms and metaphors appropriately
- Maintain register and tone

Each example is carefully crafted to show the difference between
literal translation (wrong) and culturally-adapted translation (correct).

These are hand-curated examples, not generated, to ensure maximum quality.
"""

from typing import Dict, List, Tuple


# Example structure:
# {
#     "source": "Original text",
#     "literal": "Bad word-for-word translation (what to avoid)",
#     "correct": "Good culturally-adapted translation",
#     "explanation": "Why this adaptation is better"
# }

CULTURAL_EXAMPLES: Dict[Tuple[str, str], List[Dict[str, str]]] = {

    # =========================================================================
    # ENGLISH → FRENCH
    # =========================================================================
    ("english", "french"): [
        {
            "source": "It's raining cats and dogs outside.",
            "literal": "Il pleut des chats et des chiens dehors.",
            "correct": "Il pleut des cordes dehors.",
            "explanation": "French has its own idiom for heavy rain"
        },
        {
            "source": "He kicked the bucket last night.",
            "literal": "Il a donné un coup de pied dans le seau hier soir.",
            "correct": "Il a cassé sa pipe hier soir.",
            "explanation": "Euphemism for death requires cultural equivalent"
        },
        {
            "source": "That's a piece of cake!",
            "literal": "C'est un morceau de gâteau !",
            "correct": "C'est du gâteau !",
            "explanation": "The French idiom uses a slightly different form"
        },
        {
            "source": "She has butterflies in her stomach.",
            "literal": "Elle a des papillons dans l'estomac.",
            "correct": "Elle a le trac. / Elle a l'estomac noué.",
            "explanation": "French expresses nervousness differently"
        },
        {
            "source": "He's feeling under the weather today.",
            "literal": "Il se sent sous le temps aujourd'hui.",
            "correct": "Il n'est pas dans son assiette aujourd'hui.",
            "explanation": "French uses a plate metaphor for feeling unwell"
        },
        {
            "source": "Let's call it a day.",
            "literal": "Appelons ça une journée.",
            "correct": "On arrête là pour aujourd'hui.",
            "explanation": "Direct idiomatic equivalent doesn't exist"
        },
        {
            "source": "Break a leg!",
            "literal": "Casse-toi une jambe !",
            "correct": "Merde !",
            "explanation": "Theater superstition has different expression in French"
        },
    ],

    # =========================================================================
    # FRENCH → ENGLISH
    # =========================================================================
    ("french", "english"): [
        {
            "source": "Il pleut des cordes.",
            "literal": "It's raining ropes.",
            "correct": "It's raining cats and dogs.",
            "explanation": "English has its own idiom for heavy rain"
        },
        {
            "source": "Avoir le cafard.",
            "literal": "To have the cockroach.",
            "correct": "To feel down. / To have the blues.",
            "explanation": "French cockroach metaphor for sadness doesn't work in English"
        },
        {
            "source": "Ce n'est pas la mer à boire.",
            "literal": "It's not the sea to drink.",
            "correct": "It's not rocket science. / It's no big deal.",
            "explanation": "Different metaphor for 'not difficult'"
        },
        {
            "source": "Poser un lapin à quelqu'un.",
            "literal": "To put a rabbit on someone.",
            "correct": "To stand someone up.",
            "explanation": "French rabbit idiom for missing a date"
        },
        {
            "source": "Avoir d'autres chats à fouetter.",
            "literal": "To have other cats to whip.",
            "correct": "To have bigger fish to fry.",
            "explanation": "Both use animals but different ones"
        },
        {
            "source": "Tomber dans les pommes.",
            "literal": "To fall into the apples.",
            "correct": "To faint. / To pass out.",
            "explanation": "French apple idiom for fainting has no English equivalent"
        },
    ],

    # =========================================================================
    # ENGLISH → SPANISH
    # =========================================================================
    ("english", "spanish"): [
        {
            "source": "It cost me an arm and a leg.",
            "literal": "Me costó un brazo y una pierna.",
            "correct": "Me costó un ojo de la cara.",
            "explanation": "Spanish uses 'an eye from the face' for expensive things"
        },
        {
            "source": "When pigs fly!",
            "literal": "¡Cuando los cerdos vuelen!",
            "correct": "¡Cuando las ranas críen pelo!",
            "explanation": "Spanish: 'When frogs grow hair'"
        },
        {
            "source": "He's beating around the bush.",
            "literal": "Está golpeando alrededor del arbusto.",
            "correct": "Se anda con rodeos. / Se va por las ramas.",
            "explanation": "Spanish uses 'going around in circles' or 'going through branches'"
        },
        {
            "source": "Kill two birds with one stone.",
            "literal": "Matar dos pájaros de un tiro.",
            "correct": "Matar dos pájaros de un tiro.",
            "explanation": "This one translates directly - same idiom exists"
        },
        {
            "source": "It's not my cup of tea.",
            "literal": "No es mi taza de té.",
            "correct": "No es lo mío. / No es santo de mi devoción.",
            "explanation": "Tea culture reference doesn't resonate in Spanish"
        },
    ],

    # =========================================================================
    # ENGLISH → GERMAN
    # =========================================================================
    ("english", "german"): [
        {
            "source": "That's water under the bridge.",
            "literal": "Das ist Wasser unter der Brücke.",
            "correct": "Schnee von gestern.",
            "explanation": "German uses 'yesterday's snow' for past events"
        },
        {
            "source": "To hit the nail on the head.",
            "literal": "Den Nagel auf den Kopf treffen.",
            "correct": "Den Nagel auf den Kopf treffen.",
            "explanation": "Same idiom exists in German"
        },
        {
            "source": "He let the cat out of the bag.",
            "literal": "Er ließ die Katze aus dem Sack.",
            "correct": "Er hat die Katze aus dem Sack gelassen.",
            "explanation": "Similar idiom exists, slight grammatical adjustment"
        },
        {
            "source": "I'm feeling blue.",
            "literal": "Ich fühle mich blau.",
            "correct": "Mir ist traurig zumute. / Ich bin niedergeschlagen.",
            "explanation": "Blue=sad doesn't work in German (blau=drunk)"
        },
        {
            "source": "You're pulling my leg!",
            "literal": "Du ziehst an meinem Bein!",
            "correct": "Du nimmst mich auf den Arm!",
            "explanation": "German uses 'taking on the arm' for teasing"
        },
    ],

    # =========================================================================
    # ENGLISH → CHINESE
    # =========================================================================
    ("english", "chinese"): [
        {
            "source": "He's the black sheep of the family.",
            "literal": "他是家里的黑羊。",
            "correct": "他是家里的害群之马。",
            "explanation": "Chinese uses 'horse that harms the herd'"
        },
        {
            "source": "Kill two birds with one stone.",
            "literal": "一石杀两鸟。",
            "correct": "一箭双雕。 / 一举两得。",
            "explanation": "Chinese uses 'one arrow, two eagles' or 'one action, two gains'"
        },
        {
            "source": "It's raining cats and dogs.",
            "literal": "下着猫和狗。",
            "correct": "倾盆大雨。",
            "explanation": "Chinese uses 'rain pouring like from a basin'"
        },
        {
            "source": "Break a leg!",
            "literal": "摔断腿！",
            "correct": "祝你好运！ / 加油！",
            "explanation": "Western theater superstition doesn't exist in Chinese culture"
        },
        {
            "source": "He has a green thumb.",
            "literal": "他有一个绿色的拇指。",
            "correct": "他很会种花种草。 / 他有园艺天赋。",
            "explanation": "Green thumb idiom doesn't exist in Chinese"
        },
        {
            "source": "Let sleeping dogs lie.",
            "literal": "让睡着的狗躺着。",
            "correct": "别惹是生非。 / 多一事不如少一事。",
            "explanation": "Chinese uses 'don't stir up trouble' concept"
        },
    ],

    # =========================================================================
    # ENGLISH → JAPANESE
    # =========================================================================
    ("english", "japanese"): [
        {
            "source": "It's a piece of cake.",
            "literal": "ケーキの一切れです。",
            "correct": "朝飯前だ。",
            "explanation": "Japanese uses 'before breakfast' for easy tasks"
        },
        {
            "source": "Kill two birds with one stone.",
            "literal": "一石で二羽の鳥を殺す。",
            "correct": "一石二鳥。",
            "explanation": "Same concept exists as a four-character idiom"
        },
        {
            "source": "He kicked the bucket.",
            "literal": "彼はバケツを蹴った。",
            "correct": "彼は亡くなった。 / 彼は他界した。",
            "explanation": "Japanese prefers respectful euphemisms for death"
        },
        {
            "source": "Once in a blue moon.",
            "literal": "青い月に一度。",
            "correct": "滅多にない。 / ごくまれに。",
            "explanation": "Blue moon concept doesn't exist in Japanese"
        },
        {
            "source": "He's a couch potato.",
            "literal": "彼はソファのジャガイモだ。",
            "correct": "彼はゴロゴロしてばかりいる。",
            "explanation": "Japanese describes the lazy behavior directly"
        },
        {
            "source": "Let's touch base next week.",
            "literal": "来週ベースに触れましょう。",
            "correct": "来週また連絡しましょう。",
            "explanation": "Baseball idiom doesn't translate to Japanese business culture"
        },
    ],

    # =========================================================================
    # ENGLISH → KOREAN
    # =========================================================================
    ("english", "korean"): [
        {
            "source": "He spilled the beans.",
            "literal": "그는 콩을 쏟았다.",
            "correct": "그는 비밀을 누설했다.",
            "explanation": "Korean expresses 'revealed a secret' directly"
        },
        {
            "source": "It's raining cats and dogs.",
            "literal": "고양이와 개가 비처럼 내린다.",
            "correct": "비가 억수같이 쏟아진다.",
            "explanation": "Korean has its own expression for heavy rain"
        },
        {
            "source": "He's on cloud nine.",
            "literal": "그는 구름 아홉 위에 있다.",
            "correct": "그는 기분이 날아갈 것 같다.",
            "explanation": "Korean describes feeling like flying with happiness"
        },
        {
            "source": "You're barking up the wrong tree.",
            "literal": "당신은 잘못된 나무를 향해 짖고 있다.",
            "correct": "헛다리 짚고 있네.",
            "explanation": "Korean uses 'stepping on the wrong leg'"
        },
        {
            "source": "Break a leg!",
            "literal": "다리를 부러뜨려!",
            "correct": "파이팅! / 행운을 빌어!",
            "explanation": "Korean uses 'Fighting!' as encouragement"
        },
    ],

    # =========================================================================
    # ENGLISH → RUSSIAN
    # =========================================================================
    ("english", "russian"): [
        {
            "source": "When pigs fly!",
            "literal": "Когда свиньи полетят!",
            "correct": "Когда рак на горе свистнет!",
            "explanation": "Russian: 'When a crayfish whistles on the mountain'"
        },
        {
            "source": "It's not my cup of tea.",
            "literal": "Это не моя чашка чая.",
            "correct": "Это не по мне. / Это не моё.",
            "explanation": "Tea metaphor doesn't work in Russian"
        },
        {
            "source": "He's feeling under the weather.",
            "literal": "Он чувствует себя под погодой.",
            "correct": "Ему нездоровится. / Он неважно себя чувствует.",
            "explanation": "Russian describes feeling unwell directly"
        },
        {
            "source": "Kill two birds with one stone.",
            "literal": "Убить двух птиц одним камнем.",
            "correct": "Убить двух зайцев одним выстрелом.",
            "explanation": "Russian uses 'two rabbits with one shot'"
        },
        {
            "source": "He let the cat out of the bag.",
            "literal": "Он выпустил кошку из мешка.",
            "correct": "Он проболтался. / Он выдал секрет.",
            "explanation": "Russian describes revealing a secret directly"
        },
    ],

    # =========================================================================
    # ENGLISH → ARABIC
    # =========================================================================
    ("english", "arabic"): [
        {
            "source": "It's raining cats and dogs.",
            "literal": "تمطر قططاً وكلاباً.",
            "correct": "السماء تمطر بغزارة.",
            "explanation": "Arabic describes heavy rain directly"
        },
        {
            "source": "He kicked the bucket.",
            "literal": "ركل الدلو.",
            "correct": "لفظ أنفاسه الأخيرة. / انتقل إلى رحمة الله.",
            "explanation": "Arabic uses respectful phrases for death"
        },
        {
            "source": "Actions speak louder than words.",
            "literal": "الأفعال تتكلم أعلى من الكلمات.",
            "correct": "الفعل أبلغ من القول.",
            "explanation": "Arabic has equivalent proverb with different structure"
        },
        {
            "source": "Kill two birds with one stone.",
            "literal": "اقتل عصفورين بحجر واحد.",
            "correct": "ضرب عصفورين بحجر واحد.",
            "explanation": "Similar idiom exists with 'hit' instead of 'kill'"
        },
        {
            "source": "A penny for your thoughts.",
            "literal": "قرش مقابل أفكارك.",
            "correct": "بم تفكر؟ / ما الذي يشغل بالك؟",
            "explanation": "Arabic asks directly about someone's thoughts"
        },
    ],

    # =========================================================================
    # ENGLISH → ITALIAN
    # =========================================================================
    ("english", "italian"): [
        {
            "source": "It costs an arm and a leg.",
            "literal": "Costa un braccio e una gamba.",
            "correct": "Costa un occhio della testa.",
            "explanation": "Italian uses 'costs an eye from the head'"
        },
        {
            "source": "In a nutshell...",
            "literal": "In un guscio di noce...",
            "correct": "In poche parole... / In sintesi...",
            "explanation": "Italian expresses brevity differently"
        },
        {
            "source": "He's feeling blue.",
            "literal": "Si sente blu.",
            "correct": "È giù di morale. / Ha il morale a terra.",
            "explanation": "Blue=sad doesn't work in Italian"
        },
        {
            "source": "That's the last straw!",
            "literal": "Quella è l'ultima paglia!",
            "correct": "È la goccia che fa traboccare il vaso!",
            "explanation": "Italian uses 'the drop that overflows the vase'"
        },
        {
            "source": "Let sleeping dogs lie.",
            "literal": "Lascia dormire i cani che dormono.",
            "correct": "Non svegliare il can che dorme.",
            "explanation": "Italian has equivalent with slightly different structure"
        },
    ],

    # =========================================================================
    # ENGLISH → PORTUGUESE
    # =========================================================================
    ("english", "portuguese"): [
        {
            "source": "It's raining cats and dogs.",
            "literal": "Está chovendo gatos e cachorros.",
            "correct": "Está chovendo canivetes.",
            "explanation": "Brazilian Portuguese: 'raining penknives'"
        },
        {
            "source": "He kicked the bucket.",
            "literal": "Ele chutou o balde.",
            "correct": "Ele bateu as botas.",
            "explanation": "Portuguese uses 'knocked the boots'"
        },
        {
            "source": "Break a leg!",
            "literal": "Quebre uma perna!",
            "correct": "Merda! / Boa sorte!",
            "explanation": "Theater tradition similar to French in Portuguese"
        },
        {
            "source": "Once in a blue moon.",
            "literal": "Uma vez em uma lua azul.",
            "correct": "De vez em quando. / Muito raramente.",
            "explanation": "Blue moon concept needs direct translation in Portuguese"
        },
        {
            "source": "To beat around the bush.",
            "literal": "Bater ao redor do arbusto.",
            "correct": "Enrolar. / Fazer rodeios.",
            "explanation": "Portuguese uses 'to wrap around' or 'go in circles'"
        },
    ],
}


def get_cultural_examples(
    source_lang: str,
    target_lang: str,
    count: int = 3
) -> List[Dict[str, str]]:
    """
    Get cultural adaptation examples for a language pair.

    Args:
        source_lang: Source language name
        target_lang: Target language name
        count: Maximum number of examples to return

    Returns:
        List of example dicts with source, literal, correct, explanation.
        Returns empty list if no examples for this pair.
    """
    key = (source_lang.lower(), target_lang.lower())
    examples = CULTURAL_EXAMPLES.get(key, [])
    return examples[:count]


def has_cultural_examples(source_lang: str, target_lang: str) -> bool:
    """Check if cultural examples exist for a language pair."""
    key = (source_lang.lower(), target_lang.lower())
    return key in CULTURAL_EXAMPLES and len(CULTURAL_EXAMPLES[key]) > 0


def format_cultural_examples_for_prompt(
    source_lang: str,
    target_lang: str,
    count: int = 2
) -> str:
    """
    Format cultural examples for inclusion in a translation prompt.

    Args:
        source_lang: Source language name
        target_lang: Target language name
        count: Number of examples to include

    Returns:
        Formatted string for prompt, or empty string if no examples.
    """
    examples = get_cultural_examples(source_lang, target_lang, count)

    if not examples:
        return ""

    lines = [
        "# CULTURAL ADAPTATION (IMPORTANT)",
        "",
        "Translate idiomatically, NOT literally. Adapt expressions to the target culture.",
        ""
    ]

    for i, ex in enumerate(examples, 1):
        lines.append(f"**Example {i}:**")
        lines.append(f"Source: \"{ex['source']}\"")
        lines.append(f"❌ Literal: \"{ex['literal']}\"")
        lines.append(f"✅ Correct: \"{ex['correct']}\"")
        lines.append(f"Why: {ex['explanation']}")
        lines.append("")

    return "\n".join(lines)


# Reverse mappings for common pairs
def _add_reverse_pairs():
    """Add reverse pairs where appropriate."""
    pairs_to_add = {}
    # Some pairs work both ways with adjustment
    # This is handled in the main dictionary above
    pass


_add_reverse_pairs()
