"""
Vigil — Phase 5: File Watcher compatibility wrapper.
Exposes start_watcher from backend.ingestion.watch_folder.
"""

from backend.ingestion.watch_folder import start_watcher, CallAudioFileHandler

__all__ = ["start_watcher", "CallAudioFileHandler"]
