"""
index_files.py — Surgical implementation of Knowledge Grounding.
Reuses core indexer logic to ensure compatibility with HybridRetriever.
"""

import logging
import asyncio
from pathlib import Path
from typing import Optional
import config
from core.indexer import LocalIndexer

log = logging.getLogger("uzephyr.skills.index_files")

# Reference to the global indexer set by the shared runtime at startup
_global_indexer: Optional[LocalIndexer] = None


def _set_indexer(indexer: LocalIndexer) -> None:
    """Called once during initialisation to wire up the shared indexer."""
    global _global_indexer
    _global_indexer = indexer


class FileSourceWatcher:
    """Watches a specific directory and indexes files using the core LocalIndexer."""
    
    def __init__(self, watch_dir: Optional[str] = None, indexer: Optional[LocalIndexer] = None):
        # Default to a folder named 'file-src' in your project root
        self.watch_dir = Path(watch_dir) if watch_dir else config.PROJECT_ROOT / "file-src"
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        # Reuse the global indexer to avoid duplicate Whoosh writers;
        # fall back to a new instance only when no global is available.
        self.indexer = indexer or _global_indexer or LocalIndexer()
        self._owns_indexer = (indexer is None and _global_indexer is None)
        self._running = False
        
    def start_watching(self) -> str:
        """Initializes the indexer and starts the Watchdog observer."""
        try:
            # Only initialise if we created our own indexer
            if self._owns_indexer:
                self.indexer.initialize()
            
            # Perform an initial scan of existing files
            count = self.indexer.index_all(root=self.watch_dir)
            self._running = True
            
            return (
                f"📁 **Hot-Watch Active**: {self.watch_dir}\n"
                f"📚 Pre-indexed {count} files. I am now watching this folder.\n"
                "Drop files here, and they will be ready for discussion instantly."
            )
        except Exception as e:
            log.error("Failed to start Hot-Watch: %s", e)
            return f"❌ Error starting watcher: {e}"

    def stop(self):
        """Gracefully stops the background observer."""
        # Only stop the observer if we own the indexer
        if self._owns_indexer and hasattr(self.indexer, "_observer") and self.indexer._observer:
            self.indexer._observer.stop()
            self.indexer._observer.join()
        self._running = False

# Singleton instance for the session
_watcher = None

async def start_file_watch(watch_dir: Optional[str] = None) -> str:
    """Begin watching a folder for automatic RAG indexing."""
    global _watcher
    if _watcher and _watcher._running:
        return f"Watcher is already running on {_watcher.watch_dir}"
    
    _watcher = FileSourceWatcher(watch_dir)
    return _watcher.start_watching()

async def stop_file_watch() -> str:
    """Stop the active file watcher."""
    global _watcher
    if not _watcher or not _watcher._running:
        return "No active watcher to stop."
    _watcher.stop()
    return "🛑 File watcher stopped."