"""
Translation job handlers and processing logic
"""
import os
import time
import asyncio
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from src.core.epub import translate_epub_file
from src.utils.unified_logger import setup_web_logger, LogType
from src.utils.file_utils import get_unique_output_path
from .websocket import emit_update


def run_translation_async_wrapper(translation_id, config, state_manager, output_dir, socketio):
    """
    Wrapper for running translation in async context
    
    Args:
        translation_id (str): Translation job ID
        config (dict): Translation configuration
        state_manager: State manager instance
        output_dir (str): Output directory path
        socketio: SocketIO instance
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(perform_actual_translation(translation_id, config, state_manager, output_dir, socketio))
    except Exception as e:
        error_msg = f"Uncaught major error in translation wrapper {translation_id}: {str(e)}"
        print(error_msg)
        if state_manager.exists(translation_id):
            state_manager.set_translation_field(translation_id, 'status', 'error')
            state_manager.set_translation_field(translation_id, 'error', error_msg)
            logs = state_manager.get_translation_field(translation_id, 'logs')
            if logs is None:
                logs = []
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] CRITICAL WRAPPER ERROR: {error_msg}")
            state_manager.set_translation_field(translation_id, 'logs', logs)
            emit_update(socketio, translation_id, {'error': error_msg, 'status': 'error', 'log': f"CRITICAL WRAPPER ERROR: {error_msg}"}, state_manager)
    finally:
        loop.close()


async def perform_actual_translation(translation_id, config, state_manager, output_dir, socketio):
    """
    Perform the actual translation job
    
    Args:
        translation_id (str): Translation job ID
        config (dict): Translation configuration
        state_manager: State manager instance
        output_dir (str): Output directory path
        socketio: SocketIO instance
    """
    if not state_manager.exists(translation_id):
        print(f"Critical error: {translation_id} not found in state_manager.")
        return

    state_manager.set_translation_field(translation_id, 'status', 'running')
    emit_update(socketio, translation_id, {'status': 'running', 'log': 'Translation task started by worker.'}, state_manager)

    def should_interrupt_current_task():
        if state_manager.exists(translation_id) and state_manager.get_translation_field(translation_id, 'interrupted'):
            _log_message_callback("interruption_check", f"Interruption signal detected for job {translation_id}. Halting processing.")
            return True
        return False

    # Setup unified logger for web interface
    def web_callback(log_entry):
        """Callback for WebSocket emission"""
        logs = state_manager.get_translation_field(translation_id, 'logs')
        if logs is None:
            logs = []
        logs.append(log_entry)
        state_manager.set_translation_field(translation_id, 'logs', logs)
        # Send full log entry for structured processing on client side
        emit_update(socketio, translation_id, {'log': log_entry['message'], 'log_entry': log_entry}, state_manager)
    
    def storage_callback(log_entry):
        """Callback for storing logs"""
        logs = state_manager.get_translation_field(translation_id, 'logs')
        if logs is None:
            logs = []
        logs.append(log_entry)
        state_manager.set_translation_field(translation_id, 'logs', logs)
    
    logger = setup_web_logger(web_callback, storage_callback)
    
    def _log_message_callback(message_key_from_translate_module, message_content="", data=None):
        """Legacy callback wrapper for backward compatibility"""
        # Skip debug messages for web interface
        if message_key_from_translate_module in ["llm_prompt_debug", "llm_raw_response_preview"]:
            return
        
        # Handle structured data from new logging system
        if data and isinstance(data, dict):
            log_type = data.get('type')
            if log_type == 'llm_request':
                logger.info("LLM Request", LogType.LLM_REQUEST, data)
            elif log_type == 'llm_response':
                logger.info("LLM Response", LogType.LLM_RESPONSE, data)
            elif log_type == 'progress':
                logger.info("Progress Update", LogType.PROGRESS, data)
            else:
                logger.info(message_content, data=data)
        else:
            # Map specific message patterns to appropriate log types
            if "error" in message_key_from_translate_module.lower():
                logger.error(message_content)
            elif "warning" in message_key_from_translate_module.lower():
                logger.warning(message_content)
            else:
                logger.info(message_content)

    def _update_translation_progress_callback(progress_percent):
        if state_manager.exists(translation_id):
            if not state_manager.get_translation_field(translation_id, 'interrupted'):
                state_manager.set_translation_field(translation_id, 'progress', progress_percent)
            progress = state_manager.get_translation_field(translation_id, 'progress')
            emit_update(socketio, translation_id, {'progress': progress}, state_manager)

    def _update_translation_stats_callback(new_stats_dict):
        if state_manager.exists(translation_id):
            state_manager.update_stats(translation_id, new_stats_dict)
            current_stats = state_manager.get_translation_field(translation_id, 'stats') or {}
            current_stats['elapsed_time'] = time.time() - current_stats.get('start_time', time.time())
            state_manager.set_translation_field(translation_id, 'stats', current_stats)
            emit_update(socketio, translation_id, {'stats': current_stats}, state_manager)

    # Get checkpoint manager and handle resume
    checkpoint_manager = state_manager.get_checkpoint_manager()
    resume_from_index = config.get('resume_from_index', 0)
    is_resume = config.get('is_resume', False)

    try:
        # Create checkpoint for new jobs (not for resumed jobs)
        if not is_resume:
            file_type = config['file_type']
            input_file_path = config.get('file_path')
            checkpoint_manager.start_job(
                translation_id,
                file_type,
                config,
                input_file_path
            )

        # PHASE 2: Validation and warnings at startup
        if config.get('llm_provider', 'ollama') == 'ollama':
            from src.core.context_optimizer import validate_configuration

            warnings = validate_configuration(
                chunk_size=config.get('chunk_size', 25),
                num_ctx=config.get('context_window', 2048),
                model_name=config['model']
            )

            # Send warnings to client via WebSocket
            for warning in warnings:
                emit_update(socketio, translation_id, {
                    'type': 'warning',
                    'message': warning
                }, state_manager)
                _log_message_callback("context_validation_warning", warning)

        # Generate unique output filename to avoid overwriting
        tentative_output_path = os.path.join(output_dir, config['output_filename'])
        output_filepath_on_server = get_unique_output_path(tentative_output_path)

        # Update config with the actual filename (may have been modified)
        actual_output_filename = os.path.basename(output_filepath_on_server)
        if actual_output_filename != config['output_filename']:
            _log_message_callback("output_filename_modified",
                f"ℹ️ Output filename modified to avoid overwriting: {config['output_filename']} → {actual_output_filename}")
            config['output_filename'] = actual_output_filename

        # Log translation start with unified logger
        logger.info("Translation Started", LogType.TRANSLATION_START, {
            'source_lang': config['source_language'],
            'target_lang': config['target_language'],
            'file_type': config['file_type'].upper(),
            'model': config['model'],
            'translation_id': translation_id,
            'output_file': config['output_filename'],
            'api_endpoint': config['llm_api_endpoint'],
            'chunk_size': config.get('chunk_size', 'default')
        })
        
        input_path_for_translate_module = config.get('file_path')
        if config['file_type'] == 'epub':
            if not input_path_for_translate_module:
                _log_message_callback("epub_error_no_path", "❌ EPUB translation requires a file path from upload.")
                raise Exception("EPUB translation requires a file_path.")

            await translate_epub_file(
                input_path_for_translate_module,
                output_filepath_on_server,
                config['source_language'],
                config['target_language'],
                config['model'],
                config['chunk_size'],
                config['llm_api_endpoint'],
                progress_callback=_update_translation_progress_callback,
                log_callback=_log_message_callback,
                stats_callback=_update_translation_stats_callback,
                check_interruption_callback=should_interrupt_current_task,
                llm_provider=config.get('llm_provider', 'ollama'),
                gemini_api_key=config.get('gemini_api_key', ''),
                openai_api_key=config.get('openai_api_key', ''),
                fast_mode=config.get('fast_mode', False),
                context_window=config.get('context_window', 2048),
                auto_adjust_context=config.get('auto_adjust_context', True),
                min_chunk_size=config.get('min_chunk_size', 5)
            )
            state_manager.set_translation_field(translation_id, 'result', "[EPUB file translated - download to view]")
            
        elif config['file_type'] == 'txt':
            temp_txt_file_path = None
            if 'text' in config and input_path_for_translate_module is None:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".txt", dir=output_dir) as tmp_f:
                    tmp_f.write(config['text'])
                    temp_txt_file_path = tmp_f.name
                input_path_for_translate_module = temp_txt_file_path

            # Use unified file processing logic
            from src.utils.file_utils import translate_text_file_with_callbacks

            await translate_text_file_with_callbacks(
                input_path_for_translate_module,
                output_filepath_on_server,
                config['source_language'],
                config['target_language'],
                config['model'],
                config['chunk_size'],
                config['llm_api_endpoint'],
                progress_callback=_update_translation_progress_callback,
                log_callback=_log_message_callback,
                stats_callback=_update_translation_stats_callback,
                check_interruption_callback=should_interrupt_current_task,
                llm_provider=config.get('llm_provider', 'ollama'),
                gemini_api_key=config.get('gemini_api_key', ''),
                openai_api_key=config.get('openai_api_key', ''),
                context_window=config.get('context_window', 2048),
                auto_adjust_context=config.get('auto_adjust_context', True),
                min_chunk_size=config.get('min_chunk_size', 5),
                checkpoint_manager=checkpoint_manager,
                translation_id=translation_id,
                resume_from_index=resume_from_index
            )

            if os.path.exists(output_filepath_on_server) and state_manager.get_translation_field(translation_id, 'status') not in ['error', 'interrupted_before_save']:
                state_manager.set_translation_field(translation_id, 'result', "[TXT file translated - content available for download]")
            elif not os.path.exists(output_filepath_on_server):
                state_manager.set_translation_field(translation_id, 'result', "[TXT file (partially) translated - content not loaded for preview or write failed]")

            if temp_txt_file_path and os.path.exists(temp_txt_file_path):
                os.remove(temp_txt_file_path)
                
        elif config['file_type'] == 'srt':
            # Use unified file processing logic
            from src.utils.file_utils import translate_srt_file_with_callbacks
            
            await translate_srt_file_with_callbacks(
                input_path_for_translate_module,
                output_filepath_on_server,
                config['source_language'],
                config['target_language'],
                config['model'],
                config['chunk_size'],
                config['llm_api_endpoint'],
                progress_callback=_update_translation_progress_callback,
                log_callback=_log_message_callback,
                stats_callback=_update_translation_stats_callback,
                check_interruption_callback=should_interrupt_current_task,
                llm_provider=config.get('llm_provider', 'ollama'),
                gemini_api_key=config.get('gemini_api_key', ''),
                openai_api_key=config.get('openai_api_key', ''),
                checkpoint_manager=checkpoint_manager,
                translation_id=translation_id,
                resume_from_block_index=resume_from_index
            )
            
            state_manager.set_translation_field(translation_id, 'result', "[SRT file translated - download to view]")
            
        else:
            _log_message_callback("unknown_file_type", f"❌ Unknown file type: {config['file_type']}")
            raise Exception(f"Unsupported file type: {config['file_type']}")

        _log_message_callback("save_process_info", f"💾 Translation process ended. File saved (or partially saved) at: {output_filepath_on_server}")
        state_manager.set_translation_field(translation_id, 'output_filepath', output_filepath_on_server)

        stats = state_manager.get_translation_field(translation_id, 'stats') or {}
        elapsed_time = time.time() - stats.get('start_time', time.time())
        _update_translation_stats_callback({'elapsed_time': elapsed_time})

        final_status_payload = {
            'result': state_manager.get_translation_field(translation_id, 'result'),
            'output_filename': config['output_filename'],
            'file_type': config['file_type']
        }
        
        if state_manager.get_translation_field(translation_id, 'interrupted'):
            state_manager.set_translation_field(translation_id, 'status', 'interrupted')
            _log_message_callback("summary_interrupted", f"🛑 Translation interrupted by user. Partial result saved. Time: {elapsed_time:.2f}s.")
            final_status_payload['status'] = 'interrupted'
            final_status_payload['progress'] = state_manager.get_translation_field(translation_id, 'progress') or 0

            # Mark checkpoint as interrupted in database
            checkpoint_manager.mark_interrupted(translation_id)
            _log_message_callback("checkpoint_interrupted", "⏸️ Checkpoint marked as interrupted")

            # Emit checkpoint_created event to trigger UI update
            socketio.emit('checkpoint_created', {
                'translation_id': translation_id,
                'status': 'interrupted',
                'message': 'Translation paused - checkpoint created'
            }, namespace='/')

            # DON'T clean up uploaded file on interruption - keep it for resume capability
            # The file will be preserved in the job-specific directory by checkpoint_manager
            # Only clean up if the preserved file exists (meaning backup was successful)
            preserved_path = config.get('preserved_input_path')
            if preserved_path and Path(preserved_path).exists():
                # Preserved file exists, we can safely delete the original upload
                if 'file_path' in config and config['file_path']:
                    uploaded_file_path = config['file_path']
                    upload_path = Path(uploaded_file_path)

                    if upload_path.exists() and upload_path != Path(preserved_path):
                        try:
                            # Only delete if it's in the uploads directory root (not in a job subdirectory)
                            uploads_dir = Path(output_dir) / 'uploads'
                            resolved_path = upload_path.resolve()

                            # Check if file is directly in uploads/ (not in a job subdirectory)
                            if resolved_path.parent.resolve() == uploads_dir.resolve():
                                upload_path.unlink()
                                _log_message_callback("cleanup_uploaded_file", f"🗑️ Cleaned up uploaded source file (preserved copy exists): {upload_path.name}")
                            else:
                                _log_message_callback("cleanup_skipped", f"ℹ️ Skipped cleanup - file is not in uploads root directory")
                        except Exception as e:
                            _log_message_callback("cleanup_error", f"⚠️ Could not delete uploaded file {upload_path.name}: {str(e)}")
                else:
                    _log_message_callback("cleanup_info", "ℹ️ Original upload file not found or already cleaned up")
            else:
                _log_message_callback("cleanup_skipped_no_preserve", "ℹ️ Skipped cleanup - preserved file not found, keeping original for resume")

        elif state_manager.get_translation_field(translation_id, 'status') != 'error':
            state_manager.set_translation_field(translation_id, 'status', 'completed')
            _log_message_callback("summary_completed", f"✅ Translation completed. Time: {elapsed_time:.2f}s.")
            final_status_payload['status'] = 'completed'
            _update_translation_progress_callback(100)
            final_status_payload['progress'] = 100

            # Cleanup completed job checkpoint (automatic immediate cleanup)
            checkpoint_manager.cleanup_completed_job(translation_id)
            _log_message_callback("checkpoint_cleanup", "🗑️ Checkpoint cleaned up automatically")
            
            # Clean up uploaded file if it exists and is in the uploads directory
            # On completion, we can safely delete the original upload file
            _log_message_callback("cleanup_start", f"🧹 Starting cleanup check...")
            if 'file_path' in config and config['file_path']:
                _log_message_callback("cleanup_filepath", f"📁 File path in config: {config['file_path']}")
                uploaded_file_path = config['file_path']
                # Convert to Path object for reliable path operations
                upload_path = Path(uploaded_file_path)

                # Check if file exists
                if upload_path.exists():
                    try:
                        # Only delete if it's in the uploads directory root (not in a job subdirectory)
                        uploads_dir = Path(output_dir) / 'uploads'
                        resolved_path = upload_path.resolve()

                        # Check if file is directly in uploads/ (not in a job subdirectory)
                        if resolved_path.parent.resolve() == uploads_dir.resolve():
                            upload_path.unlink()
                            _log_message_callback("cleanup_uploaded_file", f"🗑️ Cleaned up uploaded source file: {upload_path.name}")
                        else:
                            _log_message_callback("cleanup_skipped", f"ℹ️ Skipped cleanup - file is not in uploads root directory")
                    except Exception as e:
                        _log_message_callback("cleanup_error", f"⚠️ Could not delete uploaded file {upload_path.name}: {str(e)}")
            else:
                _log_message_callback("cleanup_no_filepath", f"📂 No file_path in config for cleanup")
        else:
            _log_message_callback("summary_error_final", f"❌ Translation finished with errors. Time: {elapsed_time:.2f}s.")
            final_status_payload['status'] = 'error'
            final_status_payload['error'] = state_manager.get_translation_field(translation_id, 'error') or 'Unknown error during finalization.'
            final_status_payload['progress'] = state_manager.get_translation_field(translation_id, 'progress') or 0
        
        stats = state_manager.get_translation_field(translation_id, 'stats') or {}
        if config['file_type'] == 'txt' or (config['file_type'] == 'epub' and stats.get('total_chunks', 0) > 0):
            final_stats = stats
            _log_message_callback("summary_stats_final", f"📊 Stats: {final_stats.get('completed_chunks', 0)} processed, {final_stats.get('failed_chunks', 0)} failed out of {final_stats.get('total_chunks', 0)} total segments/chunks.")
        elif config['file_type'] == 'srt' and stats.get('total_subtitles', 0) > 0:
            final_stats = stats
            _log_message_callback("summary_stats_final", f"📊 Stats: {final_stats.get('completed_subtitles', 0)} processed, {final_stats.get('failed_subtitles', 0)} failed out of {final_stats.get('total_subtitles', 0)} total subtitles.")
        
        emit_update(socketio, translation_id, final_status_payload, state_manager)

        # Trigger file list refresh in the frontend if a file was saved
        if os.path.exists(output_filepath_on_server) and final_status_payload['status'] in ['completed', 'interrupted']:
            socketio.emit('file_list_changed', {
                'reason': final_status_payload['status'],
                'filename': config.get('output_filename', 'unknown')
            }, namespace='/')

    except Exception as e:
        critical_error_msg = f"Critical error during translation task ({translation_id}): {str(e)}"
        _log_message_callback("critical_error_perform_task", critical_error_msg)
        print(f"!!! {critical_error_msg}")
        import traceback
        tb_str = traceback.format_exc()
        _log_message_callback("critical_error_perform_task_traceback", tb_str)
        print(tb_str)

        if state_manager.exists(translation_id):
            state_manager.set_translation_field(translation_id, 'status', 'error')
            state_manager.set_translation_field(translation_id, 'error', critical_error_msg)
            
            emit_update(socketio, translation_id, {
                'error': critical_error_msg, 
                'status': 'error',
                'result': state_manager.get_translation_field(translation_id, 'result') or f"Translation failed: {critical_error_msg}",
                'progress': state_manager.get_translation_field(translation_id, 'progress') or 0
            }, state_manager)


def start_translation_job(translation_id, config, state_manager, output_dir, socketio):
    """
    Start a translation job in a separate thread

    Args:
        translation_id (str): Translation job ID
        config (dict): Translation configuration
        state_manager: State manager instance
        output_dir (str): Output directory path
        socketio: SocketIO instance
    """
    thread = threading.Thread(
        target=run_translation_async_wrapper,
        args=(translation_id, config, state_manager, output_dir, socketio)
    )
    thread.daemon = True
    thread.start()