from typing import List, Tuple, NamedTuple
from src.config import (
    TRANSLATE_TAG_IN, TRANSLATE_TAG_OUT, INPUT_TAG_IN, INPUT_TAG_OUT,
    IMAGE_MARKER_PREFIX, IMAGE_MARKER_SUFFIX
)


class PromptPair(NamedTuple):
    """A pair of system and user prompts for LLM translation."""
    system: str
    user: str


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

**Examples with placeholders (multilingual):**

English → Chinese:
English: "This is ⟦TAG0⟧very important⟦TAG1⟧ information"
✅ CORRECT: "这是⟦TAG0⟧非常重要的⟦TAG1⟧信息"
❌ WRONG: "这是非常重要的信息" (placeholders removed)
❌ WRONG: "这是 ⟦ TAG0 ⟧非常重要的⟦ TAG1 ⟧ 信息" (spaces added)
"""

# Image marker example for fast mode prompt
_IMAGE_MARKER_EXAMPLE = f"{IMAGE_MARKER_PREFIX}001{IMAGE_MARKER_SUFFIX}"

IMAGE_PLACEHOLDER_PRESERVATION_SECTION = f"""# IMAGE PLACEHOLDER PRESERVATION (CRITICAL)

You will encounter image placeholders like: {_IMAGE_MARKER_EXAMPLE}, {IMAGE_MARKER_PREFIX}002{IMAGE_MARKER_SUFFIX}, etc.
These represent images that must stay at their EXACT position in the text.

**MANDATORY RULES:**
1. Keep ALL image placeholders EXACTLY as they appear
2. Do NOT translate, modify, remove, or explain them
3. Maintain their EXACT position relative to surrounding text
4. Image placeholders usually appear on their own line between paragraphs

**Examples:**

English → Chinese:
Source:
The beautiful landscape stretched before us.

{_IMAGE_MARKER_EXAMPLE}

We continued our journey through the valley.

✅ CORRECT:
美丽的风景在我们面前展开。

{_IMAGE_MARKER_EXAMPLE}

我们继续穿越山谷的旅程。

❌ WRONG: (placeholder removed or moved)
美丽的风景在我们面前展开。
我们继续穿越山谷的旅程。
{_IMAGE_MARKER_EXAMPLE}
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
    target_language: str = "Chinese",
    translate_tag_in: str = TRANSLATE_TAG_IN,
    translate_tag_out: str = TRANSLATE_TAG_OUT,
    fast_mode: bool = False,
    has_images: bool = False
) -> PromptPair:
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
        fast_mode: If True, excludes HTML/XML placeholder instructions (for pure text translation)
        has_images: If True (with fast_mode), includes image placeholder preservation instructions

    Returns:
        PromptPair: A named tuple with 'system' and 'user' prompts
    """
    # Get target-language-specific example text for output format
    example_texts = {
        "chinese": "您翻译的文本在这里" if fast_mode else "您翻译的文本在这里，所有⟦TAG0⟧标记都精确保留",
        "french": "Votre texte traduit ici" if fast_mode else "Votre texte traduit ici, tous les marqueurs ⟦TAG0⟧ sont préservés exactement",
        "spanish": "Su texto traducido aquí" if fast_mode else "Su texto traducido aquí, todos los marcadores ⟦TAG0⟧ se preservan exactamente",
        "german": "Ihr übersetzter Text hier" if fast_mode else "Ihr übersetzter Text hier, alle ⟦TAG0⟧-Markierungen werden genau beibehalten",
        "japanese": "翻訳されたテキストはこちら" if fast_mode else "翻訳されたテキストはこちら、すべての⟦TAG0⟧マーカーは正確に保持されます",
        "italian": "Il tuo testo tradotto qui" if fast_mode else "Il tuo testo tradotto qui, tutti i marcatori ⟦TAG0⟧ sono conservati esattamente",
        "portuguese": "Seu texto traduzido aqui" if fast_mode else "Seu texto traduzido aqui, todos os marcadores ⟦TAG0⟧ são preservados exatamente",
        "russian": "Ваш переведенный текст здесь" if fast_mode else "Ваш переведенный текст здесь, все маркеры ⟦TAG0⟧ сохранены точно",
        "korean": "번역된 텍스트는 여기에" if fast_mode else "번역된 텍스트는 여기에, 모든 ⟦TAG0⟧ 마커는 정확히 보존됩니다",
    }

    # Try to match target language to get appropriate example
    target_lang_lower = target_language.lower()
    example_format_text = example_texts.get(target_lang_lower, "Your translated text here")

    # Build the output format section outside the f-string to avoid backslash issues in Python 3.11
    additional_rules_text = "\n6. Do NOT repeat the input text or tags\n7. Preserve all spacing, indentation, and line breaks exactly as in source"
    output_format_section = _get_output_format_section(
        translate_tag_in,
        translate_tag_out,
        INPUT_TAG_IN,
        INPUT_TAG_OUT,
        additional_rules=additional_rules_text,
        example_format=example_format_text
    )

    # SYSTEM PROMPT - Role and instructions (stable across requests)
    system_prompt = f"""You are a professional {target_language} translator and writer.

# CRITICAL: TARGET LANGUAGE IS {target_language.upper()}

**YOUR TRANSLATION MUST BE WRITTEN ENTIRELY IN {target_language.upper()}.**

You are translating FROM {source_language} TO {target_language}.
Your output must be in {target_language} ONLY - do NOT use any other language.

# TRANSLATION PRINCIPLES

**Quality Standards:**
- Translate faithfully while preserving the author's style
- Maintain the original meaning
- Restructure sentences naturally in {target_language} (avoid word-by-word translation)
- Adapt cultural references, idioms, and expressions to {target_language} context
- Keep the exact text layout, spacing, line breaks, and indentation
- **WRITE YOUR TRANSLATION IN {target_language.upper()} - THIS IS MANDATORY**

**Technical Content (DO NOT TRANSLATE):**
- Code snippets and syntax: `function()`, `variable_name`, `class MyClass`
- Command lines: `npm install`, `git commit -m "message"`
- File paths: `/usr/bin/`, `C:/Users/Documents/`
- URLs: `https://example.com`, `www.site.org`
- Programming identifiers, API names, and technical terms

{IMAGE_PLACEHOLDER_PRESERVATION_SECTION if (fast_mode and has_images) else ('' if fast_mode else PLACEHOLDER_PRESERVATION_SECTION)}

# FINAL REMINDER: YOUR OUTPUT LANGUAGE

**YOU MUST TRANSLATE INTO {target_language.upper()}.**
Your entire translation output must be written in {target_language}.
Do NOT write in {source_language} or any other language - ONLY {target_language.upper()}.

{output_format_section}"""

    # USER PROMPT - Context and content to translate (varies per request)
    previous_translation_block_text = ""
    if previous_translation_context and previous_translation_context.strip():
        previous_translation_block_text = f"""# CONTEXT - Previous Paragraph

For consistency and natural flow, here's what came immediately before:

{previous_translation_context}

"""

    user_prompt = f"""{previous_translation_block_text}# TEXT TO TRANSLATE

{INPUT_TAG_IN}
{main_content}
{INPUT_TAG_OUT}

REMINDER: Output ONLY your translation in this exact format:
{translate_tag_in}
your translation here
{translate_tag_out}

Start with {translate_tag_in} and end with {translate_tag_out}. Nothing before or after.

Provide your translation now:"""

    return PromptPair(system=system_prompt.strip(), user=user_prompt.strip())


def generate_subtitle_block_prompt(
    subtitle_blocks: List[Tuple[int, str]],
    previous_translation_block: str,
    source_language: str = "English",
    target_language: str = "Chinese",
    translate_tag_in: str = TRANSLATE_TAG_IN,
    translate_tag_out: str = TRANSLATE_TAG_OUT,
    custom_instructions: str = ""
) -> PromptPair:
    """
    Generate translation prompt for multiple subtitle blocks with index markers.

    Args:
        subtitle_blocks: List of tuples (index, text) for subtitles to translate
        previous_translation_block: Previous translated block for context
        source_language: Source language
        target_language: Target language
        translate_tag_in: Opening tag for translation output
        translate_tag_out: Closing tag for translation output
        custom_instructions: Additional custom translation instructions

    Returns:
        PromptPair: A named tuple with 'system' and 'user' prompts
    """
    # Build the output format section outside the f-string to avoid backslash issues in Python 3.11
    subtitle_additional_rules = "\n6. Each subtitle has an index marker: [index]text - PRESERVE these markers exactly\n7. Maintain line breaks between indexed subtitles"
    subtitle_example_format = "[1]第一行翻译文本\n[2]第二行翻译文本"
    subtitle_output_format_section = _get_output_format_section(
        translate_tag_in,
        translate_tag_out,
        INPUT_TAG_IN,
        INPUT_TAG_OUT,
        additional_rules=subtitle_additional_rules,
        example_format=subtitle_example_format
    )

    # Build custom instructions section if provided
    custom_instructions_section = ""
    if custom_instructions and custom_instructions.strip():
        custom_instructions_section = f"""

# ADDITIONAL CUSTOM INSTRUCTIONS

{custom_instructions.strip()}
"""

    # SYSTEM PROMPT - Role and instructions for subtitle translation
    system_prompt = f"""You are a professional {target_language} subtitle translator and dialogue adaptation specialist.

# CRITICAL: TARGET LANGUAGE IS {target_language.upper()}

**YOUR SUBTITLE TRANSLATION MUST BE WRITTEN ENTIRELY IN {target_language.upper()}.**

You are translating subtitles FROM {source_language} TO {target_language}.
Your output must be in {target_language} ONLY - do NOT use any other language.

# SUBTITLE TRANSLATION PRINCIPLES

**Quality Standards:**
- Translate dialogues naturally and conversationally for {target_language} viewers
- Adapt expressions, slang, and cultural references appropriately
- Keep subtitle length readable (typically 40-42 characters per line)
- Restructure sentences naturally (avoid word-by-word translation)
- Maintain speaker's tone, personality, and emotion
- **WRITE YOUR TRANSLATION IN {target_language.upper()} - THIS IS MANDATORY**

**Subtitle-Specific Rules:**
- Prioritize clarity and reading speed over literal accuracy
- Condense when necessary without losing meaning
- Use natural, spoken {target_language} (not formal written style){custom_instructions_section}

# FINAL REMINDER: YOUR OUTPUT LANGUAGE

**YOU MUST TRANSLATE INTO {target_language.upper()}.**
Your entire subtitle translation must be written in {target_language}.
Do NOT write in {source_language} or any other language - ONLY {target_language.upper()}.

{subtitle_output_format_section}"""

    # USER PROMPT - Context and subtitles to translate
    previous_translation_block_text = ""
    if previous_translation_block and previous_translation_block.strip():
        previous_translation_block_text = f"""# CONTEXT - Previous Subtitle Block

For continuity and consistency, here's the previous subtitle block:

{previous_translation_block}

"""

    # Format subtitle blocks with indices
    formatted_subtitles = [f"[{idx}]{text}" for idx, text in subtitle_blocks]

    # Join subtitles outside f-string to avoid Python 3.11 backslash issues
    formatted_subtitles_text = "\n".join(formatted_subtitles)

    user_prompt = f"""{previous_translation_block_text}# SUBTITLES TO TRANSLATE

{INPUT_TAG_IN}
{formatted_subtitles_text}
{INPUT_TAG_OUT}

REMINDER: Output format must be:
{translate_tag_in}
[1]translated subtitle 1
[2]translated subtitle 2
{translate_tag_out}

Start with {translate_tag_in} and end with {translate_tag_out}. Nothing before or after.

Provide your translation now:"""

    return PromptPair(system=system_prompt.strip(), user=user_prompt.strip())
