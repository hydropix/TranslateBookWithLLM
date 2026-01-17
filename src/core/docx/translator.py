"""
DOCX translation using generic orchestrator.

Phase 2 implementation: Uses the unified GenericTranslationOrchestrator
with DocxTranslationAdapter for clean, reusable architecture.
"""

from typing import Optional, Callable, Dict, Any
from ..common.translation_orchestrator import GenericTranslationOrchestrator
from .docx_translation_adapter import DocxTranslationAdapter


async def translate_docx_file(
    input_filepath: str,
    output_filepath: str,
    source_language: str,
    target_language: str,
    model_name: str,
    llm_client: Any,
    max_tokens_per_chunk: int = 450,
    log_callback: Optional[Callable] = None,
    stats_callback: Optional[Callable] = None,
    prompt_options: Optional[Dict] = None,
    max_retries: int = 1,
    context_manager: Optional[Any] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Translate a complete DOCX file using the generic orchestrator.

    This implementation uses the unified translation pipeline:
    1. Extract content (DOCX → HTML via mammoth)
    2. Preserve structure (HTML tags → placeholders)
    3. Chunk intelligently (HTML-aware chunking)
    4. Translate chunks (with 3-phase fallback)
    5. Optional: Refine translation
    6. Reconstruct content (restore HTML tags)
    7. Finalize output (HTML → DOCX via python-docx)

    Args:
        input_filepath: Input DOCX file path
        output_filepath: Output DOCX file path
        source_language: Source language name
        target_language: Target language name
        model_name: LLM model name
        llm_client: LLM client instance
        max_tokens_per_chunk: Max tokens per chunk
        log_callback: Logging callback function        stats_callback: Statistics callback function (called after each chunk)
        prompt_options: Prompt options (refinement, etc.)
        max_retries: Max translation retries
        context_manager: Adaptive context manager (optional)
        **kwargs: Additional arguments

    Returns:
        Dict with success, stats, output_path
    """
    # Create adapter and orchestrator
    adapter = DocxTranslationAdapter()
    orchestrator = GenericTranslationOrchestrator(adapter)

    # Translate using generic pipeline
    docx_bytes, stats = await orchestrator.translate(
        source=input_filepath,
        source_language=source_language,
        target_language=target_language,
        model_name=model_name,
        llm_client=llm_client,
        max_tokens_per_chunk=max_tokens_per_chunk,
        log_callback=log_callback,
        context_manager=context_manager,
        max_retries=max_retries,
        prompt_options=prompt_options,
        stats_callback=stats_callback
    )

    # Save to output file
    with open(output_filepath, 'wb') as f:
        f.write(docx_bytes)

    if log_callback:
        log_callback("file_saved", f"DOCX saved to {output_filepath}")

    return {
        'success': True,
        'stats': stats.to_dict(),
        'output_path': output_filepath
    }
