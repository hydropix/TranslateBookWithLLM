from typing import List, Tuple
from src.config import TRANSLATE_TAG_IN, TRANSLATE_TAG_OUT, INPUT_TAG_IN, INPUT_TAG_OUT


# ============================================================================
# SHARED PROMPT SECTIONS
# ============================================================================

PLACEHOLDER_PRESERVATION_SECTION = """# PLACEHOLDER PRESERVATION (CRITICAL)

You will encounter placeholders like: ⟦TAG0⟧, ⟦TAG1⟧, ⟦TAG2⟧
These represent HTML/XML tags that have been temporarily replaced.

**MANDATORY RULES:**
1. Keep ALL placeholders EXACTLY as they appear
2. Do NOT translate, modify, remove, or explain them
3. Maintain their EXACT position in the sentence structure
4. Do NOT add spaces around them unless present in the source

**Example with placeholders:**
English: "This is ⟦TAG0⟧very important⟦TAG1⟧ information"
✅ CORRECT: "Voici une information ⟦TAG0⟧très importante⟦TAG1⟧"
❌ WRONG: "Voici une information très importante" (placeholders removed)
❌ WRONG: "Voici une information ⟦ TAG0 ⟧très importante⟦ TAG1 ⟧" (spaces added)
❌ WRONG: "Voici une information ⟦TAG0_translated⟧très importante⟦TAG1⟧" (modified)
"""


def _get_output_format_section(
    translate_tag_in: str,
    translate_tag_out: str,
    input_tag_in: str,
    input_tag_out: str,
    additional_rules: str = "",
    example_format: str = "Your translated text here"
) -> str:
    """
    Generate standardized output format instructions.

    Args:
        translate_tag_in: Opening tag for translation output
        translate_tag_out: Closing tag for translation output
        input_tag_in: Opening tag for input text
        input_tag_out: Closing tag for input text
        additional_rules: Optional additional formatting rules
        example_format: Example text to show in correct format

    Returns:
        str: Formatted output format instructions
    """
    additional_rules_text = f"\n{additional_rules}" if additional_rules else ""

    return f"""# OUTPUT FORMAT

**CRITICAL OUTPUT RULES:**
1. Translate ONLY the text between "{input_tag_in}" and "{input_tag_out}" tags
2. Your response MUST start with {translate_tag_in} (first characters, no text before)
3. Your response MUST end with {translate_tag_out} (last characters, no text after)
4. Include NOTHING before {translate_tag_in} and NOTHING after {translate_tag_out}
5. Do NOT add explanations, comments, notes, or greetings{additional_rules_text}

**INCORRECT examples (DO NOT do this):**
❌ "Here is the translation: {translate_tag_in}Text...{translate_tag_out}"
❌ "{translate_tag_in}Text...{translate_tag_out} (Additional comment)"
❌ "Sure! {translate_tag_in}Text...{translate_tag_out}"
❌ "Text..." (missing tags entirely)
❌ "{translate_tag_in}Text..." (missing closing tag)

**CORRECT format (ONLY this):**
✅ {translate_tag_in}
{example_format}
{translate_tag_out}
"""


# ============================================================================
# TRANSLATION PROMPT FUNCTIONS
# ============================================================================

def generate_translation_prompt(
    main_content: str,
    context_before: str,
    context_after: str,
    previous_translation_context: str,
    source_language: str = "English",
    target_language: str = "French",
    translate_tag_in: str = TRANSLATE_TAG_IN,
    translate_tag_out: str = TRANSLATE_TAG_OUT,
    simple_mode: bool = False
) -> str:
    """
    Generate the translation prompt with all contextual elements.

    Args:
        main_content: The text to translate
        context_before: Text appearing before main_content for context
        context_after: Text appearing after main_content for context
        previous_translation_context: Previously translated text for consistency
        source_language: Source language name
        target_language: Target language name
        translate_tag_in: Opening tag for translation output
        translate_tag_out: Closing tag for translation output
        simple_mode: If True, excludes placeholder preservation instructions (for pure text translation)

    Returns:
        str: The complete prompt formatted for translation
    """
    source_lang = source_language.upper()

    # PROMPT - can be edited for custom usages
    role_and_instructions_block = f"""You are a professional {target_language} translator and writer.

# TRANSLATION PRINCIPLES

**Quality Standards:**
- Translate faithfully while preserving the author's voice, tone, and style
- Maintain the original meaning and literary quality
- Restructure sentences naturally in {target_language} (avoid word-by-word translation)
- Adapt cultural references, idioms, and expressions to {target_language} context
- Keep the exact text layout, spacing, line breaks, and indentation

**Technical Content (DO NOT TRANSLATE):**
- Code snippets and syntax: `function()`, `variable_name`, `class MyClass`
- Command lines: `npm install`, `git commit -m "message"`
- File paths: `/usr/bin/`, `C:\Users\Documents\`
- URLs: `https://example.com`, `www.site.org`
- Programming identifiers, API names, and technical terms

# TRANSLATION EXAMPLES (English → French)

**Example 1 - Sentence Restructuring:**
❌ WRONG (word-by-word): "Il a été donné le livre par son ami"
✅ CORRECT (natural): "Son ami lui a offert le livre"
English: "He was given the book by his friend"

**Example 2 - Idiomatic Adaptation:**
❌ WRONG (literal): "Il pleut des chats et des chiens"
✅ CORRECT (adapted): "Il pleut des cordes"
English: "It's raining cats and dogs"

**Example 3 - Cultural Context:**
❌ WRONG (direct): "Le repas de Thanksgiving sera jeudi"
✅ CORRECT (clarified): "Le repas de Thanksgiving (fête américaine) aura lieu jeudi"
English: "Thanksgiving dinner will be on Thursday"

**Example 4 - Verb Structure:**
❌ WRONG (awkward): "Elle a commencé à travailler sur ce projet il y a trois ans"
✅ CORRECT (natural): "Elle travaille sur ce projet depuis trois ans"
English: "She has been working on this project for three years"

**Example 5 - Passive to Active:**
❌ WRONG (passive kept): "Les résultats ont été obtenus après analyse"
✅ CORRECT (active voice): "L'analyse a permis d'obtenir les résultats"
English: "The results were obtained after analysis"

{'' if simple_mode else PLACEHOLDER_PRESERVATION_SECTION}

{_get_output_format_section(
    translate_tag_in,
    translate_tag_out,
    INPUT_TAG_IN,
    INPUT_TAG_OUT,
    additional_rules="\n6. Do NOT repeat the input text or tags\n7. Preserve all spacing, indentation, and line breaks exactly as in source",
    example_format="Votre texte traduit ici." if simple_mode else "Votre texte traduit ici avec tous les ⟦TAG0⟧ préservés exactement."
)}
"""

    previous_translation_block_text = ""
    if previous_translation_context and previous_translation_context.strip():
        previous_translation_block_text = f"""

# CONTEXT - Previous Paragraph

For consistency and natural flow, here's what came immediately before:

{previous_translation_context}

"""

    text_to_translate_block = f"""
# TEXT TO TRANSLATE

{INPUT_TAG_IN}
{main_content}
{INPUT_TAG_OUT}

REMINDER: Output ONLY your translation in this exact format:
{translate_tag_in}
your translation here
{translate_tag_out}

Start with {translate_tag_in} and end with {translate_tag_out}. Nothing before or after.

Provide your translation now:"""

    parts = [part.strip() for part in [
        role_and_instructions_block,
        previous_translation_block_text,
        text_to_translate_block
    ] if part]

    return "\n\n".join(parts).strip()


def generate_subtitle_block_prompt(
    subtitle_blocks: List[Tuple[int, str]],
    previous_translation_block: str,
    source_language: str = "English",
    target_language: str = "French",
    translate_tag_in: str = TRANSLATE_TAG_IN,
    translate_tag_out: str = TRANSLATE_TAG_OUT
) -> str:
    """
    Generate translation prompt for multiple subtitle blocks with index markers.

    Args:
        subtitle_blocks: List of tuples (index, text) for subtitles to translate
        previous_translation_block: Previous translated block for context
        source_language: Source language
        target_language: Target language
        translate_tag_in: Opening tag for translation output
        translate_tag_out: Closing tag for translation output

    Returns:
        str: The complete prompt formatted for subtitle block translation
    """
    source_lang = source_language.upper()

    # Enhanced instructions for subtitle translation
    role_and_instructions_block = f"""You are a professional {target_language} subtitle translator and dialogue adaptation specialist.

# SUBTITLE TRANSLATION PRINCIPLES

**Quality Standards:**
- Translate dialogues naturally and conversationally for {target_language} viewers
- Adapt expressions, slang, and cultural references appropriately
- Keep subtitle length readable (typically 40-42 characters per line)
- Restructure sentences naturally (avoid word-by-word translation)
- Maintain speaker's tone, personality, and emotion

**Subtitle-Specific Rules:**
- Prioritize clarity and reading speed over literal accuracy
- Condense when necessary without losing meaning
- Use natural, spoken {target_language} (not formal written style)

# TRANSLATION EXAMPLES (Dialogue - English → French)

**Example 1 - Natural Dialogue:**
❌ WRONG: "Je ne peux pas croire que tu as fait cela"
✅ CORRECT: "J'en reviens pas que t'aies fait ça"
English: "I can't believe you did that"

**Example 2 - Slang Adaptation:**
❌ WRONG: "C'est très cool, mec"
✅ CORRECT: "C'est trop bien !"
English: "That's so cool, dude"

**Example 3 - Condensing for Readability:**
❌ WRONG: "Je pense qu'il serait préférable que nous partions maintenant"
✅ CORRECT: "On devrait partir maintenant"
English: "I think it would be better if we left now"

{_get_output_format_section(
    translate_tag_in,
    translate_tag_out,
    INPUT_TAG_IN,
    INPUT_TAG_OUT,
    additional_rules="\n6. Each subtitle has an index marker: [index]text - PRESERVE these markers exactly\n7. Maintain line breaks between indexed subtitles",
    example_format="[1]Première ligne traduite\n[2]Deuxième ligne traduite"
)}
"""

    # Previous translation context
    previous_translation_block_text = ""
    if previous_translation_block and previous_translation_block.strip():
        previous_translation_block_text = f"""

# CONTEXT - Previous Subtitle Block

For continuity and consistency, here's the previous subtitle block:

{previous_translation_block}

"""

    # Format subtitle blocks with indices
    formatted_subtitles = [f"[{idx}]{text}" for idx, text in subtitle_blocks]

    text_to_translate_block = f"""
# SUBTITLES TO TRANSLATE

{INPUT_TAG_IN}
{"\n".join(formatted_subtitles)}
{INPUT_TAG_OUT}

REMINDER: Output format must be:
{translate_tag_in}
[1]translated subtitle 1
[2]translated subtitle 2
{translate_tag_out}

Start with {translate_tag_in} and end with {translate_tag_out}. Nothing before or after.

Provide your translation now:"""

    parts = [part.strip() for part in [
        role_and_instructions_block,
        previous_translation_block_text,
        text_to_translate_block
    ] if part]

    return "\n".join(parts).strip()
