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
    check_interruption_callback: Optional[Callable] = None,
    checkpoint_manager: Optional[Any] = None,
    translation_id: Optional[str] = None,
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
        log_callback: Logging callback function
        stats_callback: Statistics callback function (called after each chunk)
        prompt_options: Prompt options (refinement, etc.)
        max_retries: Max translation retries
        context_manager: Adaptive context manager (optional)
        check_interruption_callback: Callback to check for interruption (optional)
        checkpoint_manager: Checkpoint manager for partial state (optional)
        translation_id: Translation ID for checkpointing (optional)
        **kwargs: Additional arguments

    Returns:
        Dict with success, stats, output_path
    """
    import os

    # Create adapter and orchestrator
    adapter = DocxTranslationAdapter()
    orchestrator = GenericTranslationOrchestrator(adapter)

    # Use filename as file_href for checkpointing
    file_href = os.path.basename(input_filepath)

    # Check for resume state
    resume_state = None
    if checkpoint_manager and translation_id:
        resume_state = checkpoint_manager.load_xhtml_partial_state(translation_id, file_href)
        if resume_state and log_callback:
            log_callback("docx_resume_detected", f"Found checkpoint at chunk {resume_state.current_chunk_index}")

    # Translate using generic pipeline with checkpoint support
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
        stats_callback=stats_callback,
        check_interruption_callback=check_interruption_callback,
        checkpoint_manager=checkpoint_manager,
        translation_id=translation_id,
        file_href=file_href,
        resume_state=resume_state
    )

    # Check if translation was interrupted
    if not docx_bytes:
        if log_callback:
            log_callback("docx_incomplete", "DOCX translation interrupted - partial state saved")
        return {
            'success': False,
            'stats': stats.to_dict(),
            'output_path': None,
            'interrupted': True
        }

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
