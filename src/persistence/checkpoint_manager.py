"""
Checkpoint manager for translation job persistence and resume functionality.
"""

import os
import shutil
from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path
from .database import Database


class CheckpointManager:
    """
    Manages translation job checkpoints including database persistence
    and file storage for uploaded files.
    """

    def __init__(self, db_path: str = "data/jobs.db"):
        """
        Initialize checkpoint manager.

        Args:
            db_path: Path to SQLite database
        """
        self.db = Database(db_path)
        self.uploads_dir = Path("data/uploads")
        self.uploads_dir.mkdir(parents=True, exist_ok=True)

    def start_job(
        self,
        translation_id: str,
        file_type: str,
        config: Dict[str, Any],
        input_file_path: Optional[str] = None
    ) -> bool:
        """
        Start tracking a new translation job.

        Args:
            translation_id: Unique job identifier
            file_type: Type of file (txt, srt, epub)
            config: Full translation configuration
            input_file_path: Path to input file (will be preserved if it's a temp file)

        Returns:
            True if started successfully
        """
        # Preserve input file first (updates config with preserved_input_path)
        if input_file_path:
            self._preserve_input_file(translation_id, input_file_path, config)

        # Create job in database with updated config
        success = self.db.create_job(translation_id, file_type, config)

        return success

    def get_job(self, translation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job information by translation ID.

        Args:
            translation_id: Job identifier

        Returns:
            Job dictionary or None if not found
        """
        return self.db.get_job(translation_id)

    def update_job_config(self, translation_id: str, config: Dict[str, Any]) -> bool:
        """
        Update the configuration of an existing job.

        Args:
            translation_id: Job identifier
            config: New configuration dictionary

        Returns:
            True if updated successfully
        """
        return self.db.update_job_config(translation_id, config)

    def _preserve_input_file(
        self,
        translation_id: str,
        input_file_path: str,
        config: Dict[str, Any]
    ):
        """
        Preserve the input file for resume capability.

        Args:
            translation_id: Job identifier
            input_file_path: Original input file path
            config: Translation configuration (will be updated with preserved path)
        """
        # Check if file is in temp directory
        input_path = Path(input_file_path)

        # Only preserve if file exists
        if not input_path.exists():
            print(f"Warning: Input file does not exist: {input_file_path}")
            return

        # Always preserve uploaded files for web interface
        # For CLI, only preserve if explicitly needed
        job_upload_dir = self.uploads_dir / translation_id
        job_upload_dir.mkdir(parents=True, exist_ok=True)

        # Keep the original filename (including any hash prefix)
        preserved_path = job_upload_dir / input_path.name

        try:
            shutil.copy2(input_file_path, preserved_path)
            # Update config with preserved path (stored in DB)
            config['preserved_input_path'] = str(preserved_path)
            print(f"Input file preserved: {preserved_path}")
        except Exception as e:
            print(f"Warning: Could not preserve input file: {e}")

    def save_checkpoint(
        self,
        translation_id: str,
        chunk_index: int,
        original_text: str,
        translated_text: Optional[str],
        chunk_data: Optional[Dict[str, Any]] = None,
        translation_context: Optional[Dict[str, Any]] = None,
        total_chunks: Optional[int] = None,
        completed_chunks: Optional[int] = None,
        failed_chunks: Optional[int] = None
    ) -> bool:
        """
        Save a checkpoint after translating a chunk.

        Args:
            translation_id: Job identifier
            chunk_index: Index of the chunk
            original_text: Original chunk text
            translated_text: Translated text (None if failed)
            chunk_data: Additional chunk metadata
            translation_context: LLM context for continuity
            total_chunks: Total number of chunks
            completed_chunks: Number of completed chunks
            failed_chunks: Number of failed chunks

        Returns:
            True if saved successfully
        """
        # Save chunk
        chunk_status = 'completed' if translated_text else 'failed'
        chunk_saved = self.db.save_chunk(
            translation_id,
            chunk_index,
            original_text,
            translated_text,
            chunk_data,
            chunk_status
        )

        # Update job progress
        progress_saved = self.db.update_job_progress(
            translation_id,
            current_chunk_index=chunk_index,
            total_chunks=total_chunks,
            completed_chunks=completed_chunks,
            failed_chunks=failed_chunks
        )

        # Update translation context if provided
        if translation_context:
            self.db.update_translation_context(translation_id, translation_context)

        return chunk_saved and progress_saved

    def load_checkpoint(self, translation_id: str) -> Optional[Dict[str, Any]]:
        """
        Load checkpoint data for a job.

        Args:
            translation_id: Job identifier

        Returns:
            Dictionary containing:
                - job: Job metadata and config
                - chunks: List of completed chunks
                - resume_from_index: Index to resume from
        """
        # Get job data
        job = self.db.get_job(translation_id)
        if not job:
            return None

        # Get chunks
        chunks = self.db.get_chunks(translation_id)

        # Determine resume point
        progress = job['progress']
        resume_from_index = progress['current_chunk_index'] + 1

        return {
            'job': job,
            'chunks': chunks,
            'resume_from_index': resume_from_index,
            'translation_context': job.get('translation_context')
        }

    def get_resumable_jobs(self) -> List[Dict[str, Any]]:
        """
        Get all jobs that can be resumed.

        Returns:
            List of job summaries with progress information
        """
        jobs = self.db.get_resumable_jobs()

        # Enrich with additional info
        for job in jobs:
            progress = job['progress']
            total = progress.get('total_chunks', 0)
            completed = progress.get('completed_chunks', 0)

            if total > 0:
                job['progress_percentage'] = int((completed / total) * 100)
            else:
                job['progress_percentage'] = 0

            # Get input and output file names from config
            config = job['config']

            # Extract input filename (use file_path, then preserved_input_path as fallback)
            input_path = config.get('file_path') or config.get('preserved_input_path', 'unknown')
            if input_path != 'unknown':
                job['input_filename'] = Path(input_path).name
            else:
                job['input_filename'] = 'unknown'

            # Extract output filename
            output_filename = config.get('output_filename', 'unknown')
            job['output_filename'] = output_filename if output_filename != 'unknown' else 'unknown'

        return jobs

    def mark_paused(self, translation_id: str) -> bool:
        """
        Mark a job as paused (user-initiated stop).

        Args:
            translation_id: Job identifier

        Returns:
            True if updated successfully
        """
        return self.db.update_job_progress(translation_id, status='paused')

    def mark_interrupted(self, translation_id: str) -> bool:
        """
        Mark a job as interrupted (unexpected stop/error).

        Args:
            translation_id: Job identifier

        Returns:
            True if updated successfully
        """
        return self.db.update_job_progress(translation_id, status='interrupted')

    def mark_completed(self, translation_id: str) -> bool:
        """
        Mark a job as completed.

        Args:
            translation_id: Job identifier

        Returns:
            True if updated successfully
        """
        return self.db.update_job_progress(translation_id, status='completed')

    def mark_running(self, translation_id: str) -> bool:
        """
        Mark a job as running (resumed).

        Args:
            translation_id: Job identifier

        Returns:
            True if updated successfully
        """
        return self.db.update_job_progress(translation_id, status='running')

    def delete_checkpoint(self, translation_id: str) -> bool:
        """
        Delete a job checkpoint completely (user-initiated cleanup).

        Args:
            translation_id: Job identifier

        Returns:
            True if deleted successfully
        """
        # Delete from database (chunks deleted via CASCADE)
        db_deleted = self.db.delete_job(translation_id)

        # Delete preserved files
        job_upload_dir = self.uploads_dir / translation_id
        if job_upload_dir.exists():
            try:
                shutil.rmtree(job_upload_dir)
            except Exception as e:
                print(f"Warning: Could not delete upload directory: {e}")

        return db_deleted

    def cleanup_completed_job(self, translation_id: str) -> bool:
        """
        Automatically clean up a completed job (immediate cleanup).

        Args:
            translation_id: Job identifier

        Returns:
            True if cleaned up successfully
        """
        return self.delete_checkpoint(translation_id)

    def get_preserved_input_path(self, translation_id: str) -> Optional[str]:
        """
        Get the preserved input file path for a job.

        Args:
            translation_id: Job identifier

        Returns:
            Path to preserved input file or None
        """
        job = self.db.get_job(translation_id)
        if not job:
            return None

        config = job['config']
        preserved_path = config.get('preserved_input_path')

        if preserved_path and Path(preserved_path).exists():
            return preserved_path

        return None

    def build_translated_output(
        self,
        translation_id: str,
        file_type: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Build the complete translated output from saved chunks.

        Args:
            translation_id: Job identifier
            file_type: Type of file (txt, srt, epub)

        Returns:
            Tuple of (translated_text, error_message)
        """
        chunks = self.db.get_chunks(translation_id)

        if not chunks:
            return None, "No chunks found for this job"

        if file_type in ['txt', 'epub_simple']:
            # Simple concatenation for text-based formats
            translated_parts = []
            for chunk in chunks:
                if chunk['status'] == 'completed' and chunk['translated_text']:
                    translated_parts.append(chunk['translated_text'])
                else:
                    # Use original text if translation failed
                    translated_parts.append(chunk['original_text'])

            return '\n'.join(translated_parts), None

        elif file_type == 'srt':
            # SRT needs special handling to reconstruct from blocks
            # Each chunk contains block_translations dict mapping subtitle index to translated text
            job = self.db.get_job(translation_id)
            if not job:
                return None, "Job not found"

            # Build a complete translations dictionary from all blocks
            all_translations = {}
            for chunk in chunks:
                block_translations = chunk.get('chunk_data', {}).get('block_translations', {})
                for idx_str, trans_text in block_translations.items():
                    idx = int(idx_str)
                    all_translations[idx] = trans_text

            if not all_translations:
                return None, "No translations found in checkpoint"

            # Now we need to reconstruct the SRT file
            # We need the original subtitle structure (timing, numbering)
            # This should be stored in the config or we need to re-parse the original file
            config = job['config']
            preserved_input_path = config.get('preserved_input_path')

            if not preserved_input_path or not Path(preserved_input_path).exists():
                return None, "Original SRT file not found, cannot reconstruct"

            # Re-parse the original SRT to get structure
            from src.core.srt_processor import SRTProcessor
            srt_processor = SRTProcessor()

            with open(preserved_input_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            subtitles = srt_processor.parse_srt(original_content)

            # Update subtitles with translations
            updated_subtitles = srt_processor.update_translated_subtitles(
                subtitles, all_translations
            )

            # Reconstruct SRT
            translated_srt = srt_processor.reconstruct_srt(updated_subtitles)

            return translated_srt, None

        elif file_type == 'epub':
            # EPUB simplified mode - checkpoint recovery not yet implemented
            # The new simplified mode translates XHTML files individually and modifies them in place
            # Resume would require re-processing the EPUB from the last successfully translated file
            return None, "EPUB checkpoint resume not yet implemented for simplified mode"

        else:
            return None, f"Unknown file type: {file_type}"

    def close(self):
        """Close database connection."""
        self.db.close()
