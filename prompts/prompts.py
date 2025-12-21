from typing import List, Tuple, NamedTuple
from src.config import (
    TRANSLATE_TAG_IN, TRANSLATE_TAG_OUT, INPUT_TAG_IN, INPUT_TAG_OUT,
)
from prompts.examples import (
    get_output_format_example,
    get_subtitle_example,
    build_placeholder_section,
    build_image_placeholder_section,
)


class PromptPair(NamedTuple):
    """A pair of system and user prompts for LLM translation."""
    system: str
    user: str


# ============================================================================
# SHARED PROMPT SECTIONS
# ============================================================================
# Note: Multilingual examples are now in prompts/examples.py
# Use build_placeholder_section() and build_image_placeholder_section()
# to generate language-specific examples dynamically.


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
2. Your response MUST start with {translate_tag_in}
3. Your response MUST end with {translate_tag_out}
4. Include NOTHING before {translate_tag_in} and NOTHING after {translate_tag_out}

**INCORRECT examples (DO NOT do this):**
❌ "Here is the translation: {translate_tag_in}Text...{translate_tag_out}"
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
    example_format_text = get_output_format_example(target_language, fast_mode=fast_mode)

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

    # Build placeholder preservation section dynamically based on languages
    if fast_mode and has_images:
        placeholder_section = build_image_placeholder_section(source_language, target_language)
    elif fast_mode:
        placeholder_section = ""
    else:
        placeholder_section = build_placeholder_section(source_language, target_language)

    # SYSTEM PROMPT - Role and instructions (stable across requests)
    system_prompt = f"""You are a professional {target_language} translator and writer.

You are translating FROM {source_language} TO {target_language}.

# TRANSLATION PRINCIPLES

**Quality Standards:**
- Translate faithfully while preserving the author's style
- Restructure sentences naturally in {target_language} (avoid word-by-word translation)
- Adapt cultural references and expressions to {target_language} context

**Technical Content (DO NOT TRANSLATE):**
- Programming identifiers, API names, and technical terms

{placeholder_section}

# FINAL REMINDER: **YOU MUST TRANSLATE INTO {target_language.upper()}.**
Do NOT write in {source_language}.

{output_format_section}"""

    # USER PROMPT - Context and content to translate (varies per request)
    previous_translation_block_text = ""
    if previous_translation_context and previous_translation_context.strip():
        previous_translation_block_text = f"""# CONTEXT - Previous Paragraph

Here's what came immediately before:

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
