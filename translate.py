"""
Command-line interface for text translation
"""
import os
import argparse
import asyncio

from src.config import DEFAULT_MODEL, MAIN_LINES_PER_CHUNK, API_ENDPOINT, LLM_PROVIDER, GEMINI_API_KEY, OPENAI_API_KEY, DEFAULT_SOURCE_LANGUAGE, DEFAULT_TARGET_LANGUAGE
from src.utils.file_utils import translate_file
from src.utils.unified_logger import setup_cli_logger, LogType


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Translate a text, EPUB or SRT file using an LLM.")
    parser.add_argument("-i", "--input", required=True, help="Path to the input file (text, EPUB, or SRT).")
    parser.add_argument("-o", "--output", default=None, help="Path to the output file. If not specified, uses input filename with suffix.")
    parser.add_argument("-sl", "--source_lang", default=DEFAULT_SOURCE_LANGUAGE, help=f"Source language (default: {DEFAULT_SOURCE_LANGUAGE}).")
    parser.add_argument("-tl", "--target_lang", default=DEFAULT_TARGET_LANGUAGE, help=f"Target language (default: {DEFAULT_TARGET_LANGUAGE}).")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"LLM model (default: {DEFAULT_MODEL}).")
    parser.add_argument("-cs", "--chunksize", type=int, default=MAIN_LINES_PER_CHUNK, help=f"Target lines per chunk (default: {MAIN_LINES_PER_CHUNK}).")
    parser.add_argument("--api_endpoint", default=API_ENDPOINT, help=f"API endpoint for Ollama or OpenAI compatible provider (default: {API_ENDPOINT}).")
    parser.add_argument("--provider", default=LLM_PROVIDER, choices=["ollama", "gemini", "openai"], help=f"LLM provider to use (default: {LLM_PROVIDER}).")
    parser.add_argument("--gemini_api_key", default=GEMINI_API_KEY, help="Google Gemini API key (required if using gemini provider).")
    parser.add_argument("--openai_api_key", default=OPENAI_API_KEY, help="OpenAI API key (required if using openai provider).")
    parser.add_argument("--custom_instructions", default="", help="Additional custom instructions for translation.")
    parser.add_argument("--post-process", action="store_true", help="Enable post-processing to improve translation quality.")
    parser.add_argument("--post-process-instructions", default="", help="Additional instructions for post-processing.")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output.")

    args = parser.parse_args()

    if args.output is None:
        base, ext = os.path.splitext(args.input)
        output_ext = ext
        if args.input.lower().endswith('.epub'):
            output_ext = '.epub'
        elif args.input.lower().endswith('.srt'):
            output_ext = '.srt'
        args.output = f"{base}_translated_{args.target_lang.lower()}{output_ext}"

    # Determine file type
    if args.input.lower().endswith('.epub'):
        file_type = "EPUB"
    elif args.input.lower().endswith('.srt'):
        file_type = "SRT"
    else:
        file_type = "TEXT"
    
    # Setup unified logger
    logger = setup_cli_logger(enable_colors=not args.no_color)
    
    # Validate API keys for providers
    if args.provider == "gemini" and not args.gemini_api_key:
        parser.error("--gemini_api_key is required when using gemini provider")
    if args.provider == "openai" and not args.openai_api_key:
        parser.error("--openai_api_key is required when using openai provider")
    
    # PHASE 2: Validation of configuration at startup
    if args.provider == "ollama":
        from src.core.context_optimizer import validate_configuration
        from src.config import OLLAMA_NUM_CTX, AUTO_ADJUST_CONTEXT

        warnings = validate_configuration(
            chunk_size=args.chunksize,
            num_ctx=OLLAMA_NUM_CTX,
            model_name=args.model
        )

        for warning in warnings:
            logger.warning(warning)

        # Optional: Ask for confirmation if configuration is suboptimal
        if warnings and not AUTO_ADJUST_CONTEXT:
            print("\n⚠️  Configuration warnings detected (see above)")
            print("Consider enabling AUTO_ADJUST_CONTEXT=true in .env file")
            response = input("Continue anyway? (y/n): ")
            if response.lower() != 'y':
                print("Aborted. Please adjust configuration and try again.")
                exit(1)

    # Log translation start
    logger.info("Translation Started", LogType.TRANSLATION_START, {
        'source_lang': args.source_lang,
        'target_lang': args.target_lang,
        'file_type': file_type,
        'model': args.model,
        'input_file': args.input,
        'output_file': args.output,
        'chunk_size': args.chunksize,
        'api_endpoint': args.api_endpoint,
        'llm_provider': args.provider,
        'custom_instructions': args.custom_instructions,
        'post_processing': args.post_process
    })

    # Create legacy callback for backward compatibility
    log_callback = logger.create_legacy_callback()

    try:
        asyncio.run(translate_file(
            args.input,
            args.output,
            args.source_lang,
            args.target_lang,
            args.model,
            chunk_target_size_cli=args.chunksize,
            cli_api_endpoint=args.api_endpoint,
            progress_callback=None,
            log_callback=log_callback,
            stats_callback=None,
            check_interruption_callback=None,
            custom_instructions=args.custom_instructions,
            llm_provider=args.provider,
            gemini_api_key=args.gemini_api_key,
            openai_api_key=args.openai_api_key,
            enable_post_processing=args.post_process,
            post_processing_instructions=args.post_process_instructions
        ))
        
        # Log successful completion
        logger.info("Translation Completed Successfully", LogType.TRANSLATION_END, {
            'output_file': args.output
        })
        
    except Exception as e:
        logger.error(f"Translation failed: {str(e)}", LogType.ERROR_DETAIL, {
            'details': str(e),
            'input_file': args.input
        })