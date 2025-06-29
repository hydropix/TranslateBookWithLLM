"""
Thread-safe translation state management
"""
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional


class TranslationStateManager:
    """Thread-safe manager for translation state"""
    
    def __init__(self):
        self._translations: Dict[str, Dict[str, Any]] = {}
        self._audiobook_jobs: Dict[str, Dict[str, Any]] = {}  # Store audiobook generation jobs
        self._lock = threading.RLock()  # Use RLock to allow nested locking
    
    def create_translation(self, translation_id: str, config: Dict[str, Any]) -> None:
        """Create a new translation entry"""
        with self._lock:
            self._translations[translation_id] = {
                'status': 'queued',
                'progress': 0,
                'stats': {
                    'start_time': time.time(),
                    'total_chunks': 0,
                    'completed_chunks': 0,
                    'failed_chunks': 0
                },
                'logs': [f"[{datetime.now().strftime('%H:%M:%S')}] Translation {translation_id} queued."],
                'result': None,
                'config': config,
                'interrupted': False,
                'output_filepath': None
            }
    
    def update_translation(self, translation_id: str, updates: Dict[str, Any]) -> bool:
        """Update translation state safely"""
        with self._lock:
            if translation_id not in self._translations:
                return False
            
            translation = self._translations[translation_id]
            
            # Handle nested updates for stats
            if 'stats' in updates and isinstance(updates['stats'], dict):
                if 'stats' not in translation:
                    translation['stats'] = {}
                translation['stats'].update(updates['stats'])
                updates = {k: v for k, v in updates.items() if k != 'stats'}
            
            # Handle logs append
            if 'log' in updates:
                if 'logs' not in translation:
                    translation['logs'] = []
                translation['logs'].append(updates['log'])
                updates = {k: v for k, v in updates.items() if k != 'log'}
            
            # Update remaining fields
            translation.update(updates)
            return True
    
    def get_translation(self, translation_id: str) -> Optional[Dict[str, Any]]:
        """Get translation state safely"""
        with self._lock:
            if translation_id not in self._translations:
                return None
            # Return a copy to prevent external modification
            return self._translations[translation_id].copy()
    
    def get_translation_field(self, translation_id: str, field: str, default=None):
        """Get a specific field from translation state"""
        with self._lock:
            if translation_id not in self._translations:
                return default
            return self._translations[translation_id].get(field, default)
    
    def set_translation_field(self, translation_id: str, field: str, value: Any) -> bool:
        """Set a specific field in translation state"""
        with self._lock:
            if translation_id not in self._translations:
                return False
            self._translations[translation_id][field] = value
            return True
    
    def append_log(self, translation_id: str, log_entry: str) -> bool:
        """Append a log entry to translation"""
        with self._lock:
            if translation_id not in self._translations:
                return False
            if 'logs' not in self._translations[translation_id]:
                self._translations[translation_id]['logs'] = []
            self._translations[translation_id]['logs'].append(log_entry)
            return True
    
    def update_stats(self, translation_id: str, stats_update: Dict[str, Any]) -> bool:
        """Update translation statistics"""
        with self._lock:
            if translation_id not in self._translations:
                return False
            if 'stats' not in self._translations[translation_id]:
                self._translations[translation_id]['stats'] = {}
            self._translations[translation_id]['stats'].update(stats_update)
            return True
    
    def exists(self, translation_id: str) -> bool:
        """Check if translation exists"""
        with self._lock:
            return translation_id in self._translations
    
    def get_all_translations(self) -> Dict[str, Dict[str, Any]]:
        """Get all translations (returns a copy)"""
        with self._lock:
            return self._translations.copy()
    
    def get_translation_summaries(self) -> list:
        """Get summaries of all translations for listing"""
        with self._lock:
            summaries = []
            for tid, data in self._translations.items():
                summaries.append({
                    "translation_id": tid,
                    "status": data.get('status'),
                    "progress": data.get('progress'),
                    "start_time": data.get('stats', {}).get('start_time'),
                    "output_filename": data.get('config', {}).get('output_filename'),
                    "file_type": data.get('config', {}).get('file_type', 'txt')
                })
            return sorted(summaries, key=lambda x: x.get('start_time', 0), reverse=True)
    
    def is_interrupted(self, translation_id: str) -> bool:
        """Check if translation is interrupted"""
        with self._lock:
            if translation_id not in self._translations:
                return False
            return self._translations[translation_id].get('interrupted', False)
    
    def set_interrupted(self, translation_id: str, interrupted: bool = True) -> bool:
        """Set interrupted flag for translation"""
        with self._lock:
            if translation_id not in self._translations:
                return False
            self._translations[translation_id]['interrupted'] = interrupted
            return True
    
    # Audiobook-specific methods
    def create_audiobook_job(self, audiobook_id: str, config: Dict[str, Any]) -> None:
        """Create a new audiobook generation job"""
        with self._lock:
            self._audiobook_jobs[audiobook_id] = {
                'status': 'queued',
                'progress': 0,
                'current_chapter': None,
                'total_chapters': 0,
                'estimated_duration': None,
                'output_files': [],
                'logs': [f"[{datetime.now().strftime('%H:%M:%S')}] Audiobook job {audiobook_id} created."],
                'config': config,
                'start_time': time.time(),
                'error': None
            }
    
    def update_audiobook_job(self, audiobook_id: str, updates: Dict[str, Any]) -> bool:
        """Update audiobook job state"""
        with self._lock:
            if audiobook_id not in self._audiobook_jobs:
                return False
            
            job = self._audiobook_jobs[audiobook_id]
            
            # Handle logs append
            if 'log' in updates:
                if 'logs' not in job:
                    job['logs'] = []
                job['logs'].append(updates['log'])
                updates = {k: v for k, v in updates.items() if k != 'log'}
            
            # Update remaining fields
            job.update(updates)
            return True
    
    def get_audiobook_job(self, audiobook_id: str) -> Optional[Dict[str, Any]]:
        """Get audiobook job state"""
        with self._lock:
            if audiobook_id not in self._audiobook_jobs:
                return None
            return self._audiobook_jobs[audiobook_id].copy()
    
    def append_audiobook_log(self, audiobook_id: str, log_entry: str) -> bool:
        """Append a log entry to audiobook job"""
        with self._lock:
            if audiobook_id not in self._audiobook_jobs:
                return False
            if 'logs' not in self._audiobook_jobs[audiobook_id]:
                self._audiobook_jobs[audiobook_id]['logs'] = []
            self._audiobook_jobs[audiobook_id]['logs'].append(log_entry)
            return True


# Global instance
_state_manager = TranslationStateManager()


def get_state_manager() -> TranslationStateManager:
    """Get the global state manager instance"""
    return _state_manager