"""
SQLite database manager for translation job persistence.
"""

import sqlite3
import json
import os
import time
from typing import Optional, Dict, List, Any
from datetime import datetime
import threading


class Database:
    """
    Manages SQLite database for translation job checkpoints.
    Thread-safe for concurrent access.
    """

    def __init__(self, db_path: str = "data/jobs.db"):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.RLock()

        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Initialize schema
        self._initialize_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    def _initialize_schema(self):
        """Create database tables if they don't exist."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Translation jobs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS translation_jobs (
                    translation_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    config JSON NOT NULL,
                    progress JSON NOT NULL,
                    translation_context JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    paused_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)

            # Checkpoint chunks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS checkpoint_chunks (
                    translation_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    original_text TEXT NOT NULL,
                    translated_text TEXT,
                    chunk_data JSON,
                    status TEXT NOT NULL,
                    completed_at TIMESTAMP,
                    PRIMARY KEY (translation_id, chunk_index),
                    FOREIGN KEY (translation_id) REFERENCES translation_jobs(translation_id)
                        ON DELETE CASCADE
                )
            """)

            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_status
                ON translation_jobs(status)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_translation
                ON checkpoint_chunks(translation_id)
            """)

            conn.commit()

    def create_job(self, translation_id: str, file_type: str, config: Dict[str, Any]) -> bool:
        """
        Create a new translation job record.

        Args:
            translation_id: Unique job identifier
            file_type: Type of file (txt, srt, epub)
            config: Full translation configuration

        Returns:
            True if created successfully
        """
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                progress = {
                    'current_chunk_index': -1,
                    'total_chunks': 0,
                    'completed_chunks': 0,
                    'failed_chunks': 0,
                    'start_time': time.time()  # Use timestamp for compatibility with existing code
                }

                cursor.execute("""
                    INSERT INTO translation_jobs
                    (translation_id, status, file_type, config, progress)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    translation_id,
                    'running',
                    file_type,
                    json.dumps(config),
                    json.dumps(progress)
                ))

                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # Job already exists
                return False
            except Exception as e:
                print(f"Error creating job: {e}")
                return False

    def update_job_progress(
        self,
        translation_id: str,
        current_chunk_index: Optional[int] = None,
        total_chunks: Optional[int] = None,
        completed_chunks: Optional[int] = None,
        failed_chunks: Optional[int] = None,
        status: Optional[str] = None
    ) -> bool:
        """
        Update job progress information.

        Args:
            translation_id: Job identifier
            current_chunk_index: Current chunk being processed
            total_chunks: Total number of chunks
            completed_chunks: Number of completed chunks
            failed_chunks: Number of failed chunks
            status: Job status (running, paused, completed, error)

        Returns:
            True if updated successfully
        """
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                # Get current progress
                cursor.execute(
                    "SELECT progress FROM translation_jobs WHERE translation_id = ?",
                    (translation_id,)
                )
                row = cursor.fetchone()
                if not row:
                    return False

                progress = json.loads(row['progress'])

                # Update fields
                if current_chunk_index is not None:
                    progress['current_chunk_index'] = current_chunk_index
                if total_chunks is not None:
                    progress['total_chunks'] = total_chunks
                if completed_chunks is not None:
                    progress['completed_chunks'] = completed_chunks
                if failed_chunks is not None:
                    progress['failed_chunks'] = failed_chunks

                # Build update query
                updates = ["progress = ?", "updated_at = CURRENT_TIMESTAMP"]
                params = [json.dumps(progress)]

                if status:
                    updates.append("status = ?")
                    params.append(status)

                    if status == 'paused':
                        updates.append("paused_at = CURRENT_TIMESTAMP")
                    elif status == 'completed':
                        updates.append("completed_at = CURRENT_TIMESTAMP")

                params.append(translation_id)

                cursor.execute(
                    f"UPDATE translation_jobs SET {', '.join(updates)} WHERE translation_id = ?",
                    params
                )

                conn.commit()
                return True
            except Exception as e:
                print(f"Error updating job progress: {e}")
                return False

    def save_chunk(
        self,
        translation_id: str,
        chunk_index: int,
        original_text: str,
        translated_text: Optional[str] = None,
        chunk_data: Optional[Dict[str, Any]] = None,
        status: str = 'completed'
    ) -> bool:
        """
        Save a translated chunk to database.

        Args:
            translation_id: Job identifier
            chunk_index: Index of the chunk
            original_text: Original text
            translated_text: Translated text (if completed)
            chunk_data: Additional chunk metadata (context_before, context_after, etc.)
            status: Chunk status (completed, failed)

        Returns:
            True if saved successfully
        """
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT OR REPLACE INTO checkpoint_chunks
                    (translation_id, chunk_index, original_text, translated_text,
                     chunk_data, status, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    translation_id,
                    chunk_index,
                    original_text,
                    translated_text,
                    json.dumps(chunk_data) if chunk_data else None,
                    status
                ))

                conn.commit()
                return True
            except Exception as e:
                print(f"Error saving chunk: {e}")
                return False

    def get_job(self, translation_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve job information.

        Args:
            translation_id: Job identifier

        Returns:
            Job data dictionary or None if not found
        """
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT * FROM translation_jobs WHERE translation_id = ?",
                    (translation_id,)
                )
                row = cursor.fetchone()

                if not row:
                    return None

                return {
                    'translation_id': row['translation_id'],
                    'status': row['status'],
                    'file_type': row['file_type'],
                    'config': json.loads(row['config']),
                    'progress': json.loads(row['progress']),
                    'translation_context': json.loads(row['translation_context']) if row['translation_context'] else None,
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'],
                    'paused_at': row['paused_at'],
                    'completed_at': row['completed_at']
                }
            except Exception as e:
                print(f"Error getting job: {e}")
                return None

    def get_chunks(self, translation_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all chunks for a job.

        Args:
            translation_id: Job identifier

        Returns:
            List of chunk dictionaries ordered by chunk_index
        """
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT * FROM checkpoint_chunks
                    WHERE translation_id = ?
                    ORDER BY chunk_index
                """, (translation_id,))

                chunks = []
                for row in cursor.fetchall():
                    chunks.append({
                        'chunk_index': row['chunk_index'],
                        'original_text': row['original_text'],
                        'translated_text': row['translated_text'],
                        'chunk_data': json.loads(row['chunk_data']) if row['chunk_data'] else None,
                        'status': row['status'],
                        'completed_at': row['completed_at']
                    })

                return chunks
            except Exception as e:
                print(f"Error getting chunks: {e}")
                return []

    def get_resumable_jobs(self) -> List[Dict[str, Any]]:
        """
        Get all jobs that can be resumed (status = paused or interrupted).

        Returns:
            List of job dictionaries
        """
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT * FROM translation_jobs
                    WHERE status IN ('paused', 'interrupted', 'error')
                    ORDER BY updated_at DESC
                """)

                jobs = []
                for row in cursor.fetchall():
                    jobs.append({
                        'translation_id': row['translation_id'],
                        'status': row['status'],
                        'file_type': row['file_type'],
                        'config': json.loads(row['config']),
                        'progress': json.loads(row['progress']),
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at'],
                        'paused_at': row['paused_at']
                    })

                return jobs
            except Exception as e:
                print(f"Error getting resumable jobs: {e}")
                return []

    def update_translation_context(
        self,
        translation_id: str,
        context: Dict[str, Any]
    ) -> bool:
        """
        Update translation context for continuity.

        Args:
            translation_id: Job identifier
            context: Context data (last_llm_context, context_accumulator, etc.)

        Returns:
            True if updated successfully
        """
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE translation_jobs
                    SET translation_context = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE translation_id = ?
                """, (json.dumps(context), translation_id))

                conn.commit()
                return True
            except Exception as e:
                print(f"Error updating translation context: {e}")
                return False

    def delete_job(self, translation_id: str) -> bool:
        """
        Delete a job and all its chunks (CASCADE).

        Args:
            translation_id: Job identifier

        Returns:
            True if deleted successfully
        """
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute(
                    "DELETE FROM translation_jobs WHERE translation_id = ?",
                    (translation_id,)
                )

                conn.commit()
                return True
            except Exception as e:
                print(f"Error deleting job: {e}")
                return False

    def close(self):
        """Close database connection."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
