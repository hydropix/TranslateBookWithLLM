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

from src.core.epub_processor import translate_epub_file
from src.utils.unified_logger import setup_web_logger, LogType
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
        emit_update(socketio, translation_id, {'log': log_entry['message']}, state_manager)
    
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

    try:
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

        output_filepath_on_server = os.path.join(output_dir, config['output_filename'])
        
        input_path_for_translate_module = config.get('file_path')
        
        # Debug logging for file paths
        if input_path_for_translate_module:
            _log_message_callback("debug_input_path", f"🔍 Input file path: {input_path_for_translate_module}")
            input_path_obj = Path(input_path_for_translate_module)
            if input_path_obj.exists():
                _log_message_callback("debug_input_resolved", f"🔍 Resolved path: {input_path_obj.resolve()}")
                _log_message_callback("debug_parent_dir", f"🔍 Parent directory: {input_path_obj.parent.name}")
        
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
                custom_instructions=config.get('custom_instructions', ''),
                llm_provider=config.get('llm_provider', 'ollama'),
                gemini_api_key=config.get('gemini_api_key', ''),
                enable_post_processing=config.get('enable_post_processing', False),
                post_processing_instructions=config.get('post_processing_instructions', '')
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
                custom_instructions=config.get('custom_instructions', ''),
                llm_provider=config.get('llm_provider', 'ollama'),
                gemini_api_key=config.get('gemini_api_key', ''),
                enable_post_processing=config.get('enable_post_processing', False),
                post_processing_instructions=config.get('post_processing_instructions', '')
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
                custom_instructions=config.get('custom_instructions', ''),
                llm_provider=config.get('llm_provider', 'ollama'),
                gemini_api_key=config.get('gemini_api_key', ''),
                enable_post_processing=config.get('enable_post_processing', False),
                post_processing_instructions=config.get('post_processing_instructions', '')
            )
            
            state_manager.set_translation_field(translation_id, 'result', "[SRT file translated - download to view]")
            
        else:
            _log_message_callback("unknown_file_type", f"❌ Unknown file type: {config['file_type']}")
            raise Exception(f"Unsupported file type: {config['file_type']}")

        _log_message_callback("save_process_info", f"💾 Translation process ended. File saved (or partially saved) at: {output_filepath_on_server}")
        state_manager.set_translation_field(translation_id, 'output_filepath', output_filepath_on_server)
        
        # Log debug info about uploaded file path for troubleshooting
        if 'file_path' in config and config['file_path']:
            _log_message_callback("debug_file_path", f"🔍 Debug - Uploaded file path: {config['file_path']}")
            upload_path = Path(config['file_path'])
            if upload_path.exists():
                _log_message_callback("debug_file_exists", f"🔍 Debug - File exists at: {upload_path.resolve()}")
                _log_message_callback("debug_path_parts", f"🔍 Debug - Path parts: {upload_path.resolve().parts}")

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
            
            # Also clean up uploaded file on interruption if translation produced output
            if 'file_path' in config and config['file_path'] and os.path.exists(output_filepath_on_server):
                uploaded_file_path = config['file_path']
                # Convert to Path object for reliable path operations
                upload_path = Path(uploaded_file_path)
                
                # Check if file exists
                if upload_path.exists():
                    # Check if it's in the uploads directory (to avoid deleting user's original files)
                    # Use Path operations to handle cross-platform path separators
                    try:
                        # Get the absolute path and check if 'uploads' is in the path parts
                        resolved_path = upload_path.resolve()
                        path_parts = resolved_path.parts
                        
                        # Log path parts for debugging
                        _log_message_callback("cleanup_path_parts", f"📋 Path parts: {path_parts}")
                        _log_message_callback("cleanup_parent_name", f"📋 Parent directory name: {resolved_path.parent.name}")
                        
                        # Check both: if 'uploads' is in path parts OR if parent directory is 'uploads'
                        is_in_uploads = 'uploads' in path_parts or resolved_path.parent.name == 'uploads'
                        
                        # Additional safety check: ensure the file is within the translated_files/uploads directory
                        uploads_dir = Path(output_dir) / 'uploads'
                        _log_message_callback("cleanup_uploads_dir", f"📋 Expected uploads directory: {uploads_dir}")
                        
                        try:
                            # Check if the file is within the uploads directory
                            resolved_path.relative_to(uploads_dir.resolve())
                            is_in_uploads = True
                            _log_message_callback("cleanup_check", f"🔍 File is confirmed to be in uploads directory")
                        except ValueError:
                            # File is not in the uploads directory
                            _log_message_callback("cleanup_check", f"🔍 File is NOT in uploads directory (relative_to check failed)")
                        
                        if is_in_uploads:
                            upload_path.unlink()  # More reliable than os.remove
                            _log_message_callback("cleanup_uploaded_file", f"🗑️ Cleaned up uploaded source file: {upload_path.name}")
                        else:
                            _log_message_callback("cleanup_skipped", f"ℹ️ Skipped cleanup - file not in uploads directory: {upload_path.name}")
                    except Exception as e:
                        _log_message_callback("cleanup_error", f"⚠️ Could not delete uploaded file {upload_path.name}: {str(e)}")

        elif state_manager.get_translation_field(translation_id, 'status') != 'error':
            state_manager.set_translation_field(translation_id, 'status', 'completed')
            _log_message_callback("summary_completed", f"✅ Translation completed. Time: {elapsed_time:.2f}s.")
            final_status_payload['status'] = 'completed'
            _update_translation_progress_callback(100)
            final_status_payload['progress'] = 100
            
            # Clean up uploaded file if it exists and is in the uploads directory
            _log_message_callback("cleanup_start", f"🧹 Starting cleanup check...")
            if 'file_path' in config and config['file_path']:
                _log_message_callback("cleanup_filepath", f"📁 File path in config: {config['file_path']}")
                uploaded_file_path = config['file_path']
                # Convert to Path object for reliable path operations
                upload_path = Path(uploaded_file_path)
                
                # Check if file exists
                if upload_path.exists():
                    # Check if it's in the uploads directory (to avoid deleting user's original files)
                    # Use Path operations to handle cross-platform path separators
                    try:
                        # Get the absolute path and check if 'uploads' is in the path parts
                        resolved_path = upload_path.resolve()
                        path_parts = resolved_path.parts
                        
                        # Log path parts for debugging
                        _log_message_callback("cleanup_path_parts", f"📋 Path parts: {path_parts}")
                        _log_message_callback("cleanup_parent_name", f"📋 Parent directory name: {resolved_path.parent.name}")
                        
                        # Check both: if 'uploads' is in path parts OR if parent directory is 'uploads'
                        is_in_uploads = 'uploads' in path_parts or resolved_path.parent.name == 'uploads'
                        
                        # Additional safety check: ensure the file is within the translated_files/uploads directory
                        uploads_dir = Path(output_dir) / 'uploads'
                        _log_message_callback("cleanup_uploads_dir", f"📋 Expected uploads directory: {uploads_dir}")
                        
                        try:
                            # Check if the file is within the uploads directory
                            resolved_path.relative_to(uploads_dir.resolve())
                            is_in_uploads = True
                            _log_message_callback("cleanup_check", f"🔍 File is confirmed to be in uploads directory")
                        except ValueError:
                            # File is not in the uploads directory
                            _log_message_callback("cleanup_check", f"🔍 File is NOT in uploads directory (relative_to check failed)")
                        
                        if is_in_uploads:
                            upload_path.unlink()  # More reliable than os.remove
                            _log_message_callback("cleanup_uploaded_file", f"🗑️ Cleaned up uploaded source file: {upload_path.name}")
                        else:
                            _log_message_callback("cleanup_skipped", f"ℹ️ Skipped cleanup - file not in uploads directory: {upload_path.name}")
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


def run_audiobook_async_wrapper(audiobook_id, config, state_manager, output_dir, socketio):
    """
    Wrapper for running audiobook generation in async context
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(perform_audiobook_generation(audiobook_id, config, state_manager, output_dir, socketio))
    except Exception as e:
        error_msg = f"Critical error in audiobook generation {audiobook_id}: {str(e)}"
        print(error_msg)
        if state_manager.get_audiobook_job(audiobook_id):
            state_manager.update_audiobook_job(audiobook_id, {
                'status': 'error',
                'error': error_msg,
                'log': f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {error_msg}"
            })
            emit_update(socketio, f"audiobook_{audiobook_id}", {'error': error_msg, 'status': 'error'}, state_manager)
    finally:
        loop.close()


async def perform_audiobook_generation(audiobook_id, config, state_manager, output_dir, socketio):
    """
    Perform the actual audiobook generation
    """
    from src.core.audio_processor import AudioProcessor, COQUI_AVAILABLE
    from src.config import Config
    
    # Update status to running
    state_manager.update_audiobook_job(audiobook_id, {
        'status': 'running',
        'log': f"[{datetime.now().strftime('%H:%M:%S')}] Starting audiobook generation..."
    })
    emit_update(socketio, f"audiobook_{audiobook_id}", {'status': 'running'}, state_manager)
    
    if not COQUI_AVAILABLE:
        error_msg = "Coqui TTS is not installed. Please install it with: pip install TTS"
        state_manager.update_audiobook_job(audiobook_id, {
            'status': 'error',
            'error': error_msg,
            'log': f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {error_msg}"
        })
        return
    
    try:
        # Get the translation data
        translation_id = config['translation_id']
        translation_data = state_manager.get_translation(translation_id)
        
        if not translation_data:
            raise ValueError(f"Translation {translation_id} not found")
        
        source_file = config['source_file']
        if not source_file or not os.path.exists(source_file):
            raise ValueError(f"Source file not found: {source_file}")
        
        # Initialize audio processor
        app_config = Config()
        audio_processor = AudioProcessor(app_config)
        
        # Create output directory for audiobook
        audiobook_dir = os.path.join(output_dir, f"audiobook_{audiobook_id}")
        os.makedirs(audiobook_dir, exist_ok=True)
        
        # Progress callback
        async def progress_callback(message):
            state_manager.update_audiobook_job(audiobook_id, {
                'log': f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
            })
            emit_update(socketio, f"audiobook_{audiobook_id}", {'log': message}, state_manager)
        
        # Determine file type and process accordingly
        file_type = translation_data['config'].get('file_type', 'txt')
        
        if file_type == 'epub':
            # Process EPUB to audiobook
            from src.core.epub_processor import EPUBProcessor
            
            # Extract text content from EPUB
            epub_processor = EPUBProcessor()
            chapters = await epub_processor.extract_chapters_for_audio(source_file)
            
            state_manager.update_audiobook_job(audiobook_id, {
                'total_chapters': len(chapters),
                'log': f"[{datetime.now().strftime('%H:%M:%S')}] Found {len(chapters)} chapters to convert"
            })
            
            # Convert chapters to audiobook
            audio_files = await audio_processor.process_epub_to_audiobook(
                chapters,
                audiobook_dir,
                language=config['target_language'],
                voice_sample=config.get('voice_sample'),
                progress_callback=progress_callback
            )
            
        else:
            # Process text file to single audio
            with open(source_file, 'r', encoding='utf-8') as f:
                text_content = f.read()
            
            # Estimate duration
            duration = audio_processor.estimate_audio_duration(text_content)
            state_manager.update_audiobook_job(audiobook_id, {
                'estimated_duration': f"{duration:.1f} minutes",
                'log': f"[{datetime.now().strftime('%H:%M:%S')}] Estimated duration: {duration:.1f} minutes"
            })
            
            # Generate audio
            output_file = os.path.join(
                audiobook_dir,
                f"{Path(source_file).stem}_audiobook.{config.get('output_format', 'mp3')}"
            )
            
            result = await audio_processor.text_to_speech(
                text_content,
                output_file,
                language=config['target_language'],
                voice_sample=config.get('voice_sample'),
                progress_callback=progress_callback
            )
            
            audio_files = [result] if result else []
        
        # Update final status
        if audio_files:
            state_manager.update_audiobook_job(audiobook_id, {
                'status': 'completed',
                'output_files': audio_files,
                'progress': 100,
                'log': f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Audiobook generation completed!"
            })
            emit_update(socketio, f"audiobook_{audiobook_id}", {
                'status': 'completed',
                'output_files': audio_files,
                'progress': 100
            }, state_manager)
        else:
            raise ValueError("No audio files were generated")
        
        # Cleanup
        audio_processor.close()
        
    except Exception as e:
        error_msg = f"Audiobook generation failed: {str(e)}"
        state_manager.update_audiobook_job(audiobook_id, {
            'status': 'error',
            'error': error_msg,
            'log': f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {error_msg}"
        })
        emit_update(socketio, f"audiobook_{audiobook_id}", {
            'status': 'error',
            'error': error_msg
        }, state_manager)
        
        import traceback
        print(f"Audiobook generation error: {traceback.format_exc()}")


def start_audiobook_generation(audiobook_id, config, state_manager, output_dir, socketio):
    """
    Start audiobook generation in a separate thread
    """
    thread = threading.Thread(
        target=run_audiobook_async_wrapper,
        args=(audiobook_id, config, state_manager, output_dir, socketio)
    )
    thread.daemon = True
    thread.start()