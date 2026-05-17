"""LocalIndexer — background crawler that parses, chunks, embeds, and persists
documents into a local ChromaDB vector store and a Whoosh keyword index.

Now optimized with Watchdog filesystem events to prevent full rescans.
"""

from __future__ import annotations

from contextlib import suppress
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

import config
from core.embedding_model import cache_embedding_model, embedding_model_is_cached
from core.markdown_parser import parse_file, chunk_text

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

log = logging.getLogger("uzephyr.indexer")

# File with mtime cache so we skip unchanged files
_MTIME_CACHE_FILE: Path = config.RUNTIME_DATA_DIR / ".mtime_cache.json"
_CHROMA_COLLECTION_NAME = "documents"


class LocalIndexer:
    """Crawl → parse → chunk → embed → persist into ChromaDB + Whoosh."""

    # Class-level lock: serialises ALL Whoosh writer access across every
    # LocalIndexer instance (index_batch, _process_deletes, etc.).
    _whoosh_writer_lock = threading.Lock()

    def __init__(self) -> None:
        self._chroma_client: Any = None
        self._collection: Any = None
        self._whoosh_index: Any = None
        self._embed_model: Any = None
        self._embed_model_lock = threading.Lock()
        self._mtime_cache: dict[str, float] = {}
        
        # Watcher state
        self._observer: Any = None
        self._watch_queue: set[Path] = set()
        self._delete_queue: set[Path] = set()
        self._watch_lock = threading.Lock()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def initialize(self) -> None:
        """Create / open the vector store and keyword index, and defer embeddings until needed."""
        self._init_chroma()
        self._init_whoosh()
        self._load_mtime_cache()
        
        # Start the background watcher
        self._start_watcher()
        log.info("LocalIndexer initialised.")

    # ── ChromaDB (semantic vectors) ───────────────────────────────────────

    def _init_chroma(self) -> None:
        import chromadb

        store_dir = config.VECTOR_STORE_DIR
        store_dir.mkdir(parents=True, exist_ok=True)
        self._chroma_client = chromadb.PersistentClient(path=str(store_dir))
        self._open_chroma_collection()

    def _open_chroma_collection(self) -> None:
        if self._chroma_client is None:
            raise RuntimeError("Chroma client is not initialized.")

        self._collection = self._chroma_client.get_or_create_collection(
            name=_CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        log.info("ChromaDB collection ready (%s docs).", self._collection.count())

    def _reset_chroma_collection(self) -> None:
        if self._chroma_client is None:
            self._init_chroma()
            return

        with suppress(Exception):
            self._chroma_client.delete_collection(name=_CHROMA_COLLECTION_NAME)

        self._open_chroma_collection()

    # ── Whoosh (keyword index) ────────────────────────────────────────────

    def _init_whoosh(self) -> None:
        from whoosh.fields import Schema, TEXT, ID, STORED
        from whoosh.index import create_in, open_dir, exists_in

        idx_dir = config.KEYWORD_INDEX_DIR
        idx_dir.mkdir(parents=True, exist_ok=True)

        lock_file = idx_dir / "MAIN_WRITELOCK"
        if lock_file.exists():
            try:
                lock_file.unlink()
            except PermissionError:
                pass

        schema = Schema(
            doc_id=ID(stored=True, unique=True),
            source=STORED,
            page=STORED,
            content=TEXT(stored=True),
        )

        if exists_in(str(idx_dir)):
            self._whoosh_index = open_dir(str(idx_dir))
        else:
            self._whoosh_index = create_in(str(idx_dir), schema)

    def _clear_whoosh_index(self) -> None:
        from whoosh.query import Every

        if self._whoosh_index is None:
            self._init_whoosh()
            return

        with LocalIndexer._whoosh_writer_lock:
            writer = self._open_whoosh_writer()
            try:
                writer.delete_by_query(Every())
                writer.commit()
            except Exception:
                writer.cancel()
                raise

    def _open_whoosh_writer(self, *, max_attempts: int = 5, retry_delay: float = 0.2) -> Any:
        """Open a Whoosh writer with a small retry window for lock contention."""
        from whoosh.index import LockError

        last_error: LockError | None = None
        for attempt in range(max_attempts):
            try:
                return self._whoosh_index.writer()
            except LockError as exc:
                last_error = exc
                if attempt == max_attempts - 1:
                    break
                time.sleep(retry_delay * (attempt + 1))

        assert last_error is not None
        raise last_error

    # ── Embedding model ───────────────────────────────────────────────────

    def _init_embedding_model(self) -> None:
        from sentence_transformers import SentenceTransformer
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cpu":
            log.warning("⚠ CUDA not detected. Embedding is running on CPU. Install PyTorch with CUDA for GPU acceleration.")

        cached_locally = embedding_model_is_cached()

        # Prefer the app-managed local copy; fall back to Hub download if not present.
        if cached_locally:
            model_path = str(config.EMBEDDING_MODEL_DIR)
            log.info("Loading embedding model from local path: %s", model_path)
        else:
            model_path = config.EMBEDDING_MODEL_NAME
            log.warning(
                "Local embedding model not found at '%s'. "
                "Falling back to Hugging Face Hub download. "
                "Run '/prepare' or 'python download_vector_model.py' to cache it locally.",
                config.EMBEDDING_MODEL_DIR,
            )

        self._embed_model = SentenceTransformer(model_path, device=device)
        if not cached_locally:
            try:
                cache_embedding_model(self._embed_model)
                log.info("Embedding model cached locally at %s.", config.EMBEDDING_MODEL_DIR)
            except Exception as exc:
                log.warning("Embedding model loaded but could not be cached locally: %s", exc)

        log.info("Embedding model '%s' loaded on %s.", config.EMBEDDING_MODEL_NAME, device.upper())

    def _ensure_embedding_model(self) -> Any:
        if self._embed_model is not None:
            return self._embed_model

        with self._embed_model_lock:
            if self._embed_model is None:
                self._init_embedding_model()

        return self._embed_model

    # ── mtime cache ───────────────────────────────────────────────────────

    def _load_mtime_cache(self) -> None:
        if _MTIME_CACHE_FILE.exists():
            try:
                self._mtime_cache = json.loads(_MTIME_CACHE_FILE.read_text(encoding="utf-8"))
            except Exception:
                self._mtime_cache = {}

    def _save_mtime_cache(self) -> None:
        _MTIME_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _MTIME_CACHE_FILE.write_text(json.dumps(self._mtime_cache), encoding="utf-8")

    @staticmethod
    def _is_dimension_mismatch_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return "dimension" in message and (
            "collection" in message
            or "embedding" in message
            or "index" in message
        )

    def rebuild_indexes(self, *, root: Path | None = None, files: list[Path] | None = None) -> int:
        """Recreate the local semantic and keyword indexes from the current file set."""
        targets = list(files) if files is not None else self.crawl(root)

        log.warning("Rebuilding local search indexes from scratch (%d target file(s)).", len(targets))

        self._reset_chroma_collection()
        self._clear_whoosh_index()
        self._mtime_cache = {}
        self._save_mtime_cache()

        return self.index_batch(targets, allow_rebuild=False)

    # ── File System Watcher (Incremental updates) ─────────────────────────

    def _is_valid_target(self, path: Path) -> bool:
        """Check if a file path is allowed to be indexed (avoids node_modules, .git, etc)."""
        for part in path.parts:
            if part in config.INDEX_IGNORE_PATTERNS or part.startswith("."):
                return False
        return True

    def _start_watcher(self) -> None:
        if not WATCHDOG_AVAILABLE:
            log.warning("Watchdog not installed. Auto-indexing disabled.")
            return

        root = config.SEARCH_DIR
        if not root.exists():
            return

        class FSEventHandler(FileSystemEventHandler):
            def __init__(self, indexer: LocalIndexer):
                self.indexer = indexer

            def on_modified(self, event):
                if not event.is_directory:
                    self.indexer._enqueue_update(Path(event.src_path))

            def on_created(self, event):
                if not event.is_directory:
                    self.indexer._enqueue_update(Path(event.src_path))

            def on_deleted(self, event):
                if not event.is_directory:
                    self.indexer._enqueue_delete(Path(event.src_path))

        self._observer = Observer()
        self._observer.schedule(FSEventHandler(self), str(root), recursive=True)
        self._observer.start()

        # Start a background thread to process the queue with a debounce
        threading.Thread(target=self._watch_consumer, daemon=True).start()
        log.info("Filesystem watcher started on %s", root)

    def _enqueue_update(self, path: Path):
        if self._is_valid_target(path):
            with self._watch_lock:
                self._watch_queue.add(path)

    def _enqueue_delete(self, path: Path):
        if self._is_valid_target(path):
            with self._watch_lock:
                self._delete_queue.add(path)

    def _watch_consumer(self):
        """Background loop that debounces events and processes index queues."""
        while True:
            time.sleep(3.0)  # Wait 3 seconds to let fast bulk-saves finish
            updates, deletes = [], []
            
            with self._watch_lock:
                if self._watch_queue or self._delete_queue:
                    updates = list(self._watch_queue)
                    deletes = list(self._delete_queue)
                    self._watch_queue.clear()
                    self._delete_queue.clear()

            if deletes:
                self._process_deletes(deletes)
            
            if updates:
                self.index_batch(updates)

    def _process_deletes(self, deletes: list[Path]) -> None:
        """Removes deleted files from ChromaDB, Whoosh, and cache."""
        from whoosh.index import LockError

        with LocalIndexer._whoosh_writer_lock:
            try:
                writer = self._open_whoosh_writer()
            except LockError:
                with self._watch_lock:
                    self._delete_queue.update(deletes)
                log.warning("Watcher delete processing deferred because the Whoosh index is busy.")
                return
            count = 0
            try:
                for path in deletes:
                    str_path = str(path)
                    self._collection.delete(where={"source": str_path})
                    writer.delete_by_term("source", str_path)
                    self._mtime_cache.pop(str_path, None)
                    count += 1
                writer.commit()
                self._save_mtime_cache()
                log.info("Watcher: Removed %d deleted file(s) from index.", count)
            except Exception as e:
                writer.cancel()
                log.error("Failed to process deletes: %s", e)

    # ── Batch Indexing ────────────────────────────────────────────────────

    def crawl(self, root: Path | None = None) -> list[Path]:
        """Recursively discover indexable files."""
        root = root or config.SEARCH_DIR
        files: list[Path] = []
        if not root.exists():
            return files

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in config.INDEX_IGNORE_PATTERNS and not d.startswith(".")]
            for fname in filenames:
                if fname in config.INDEX_IGNORE_PATTERNS or fname.startswith("."):
                    continue
                files.append(Path(dirpath) / fname)
        return files

    def index_all(self, root: Path | None = None) -> int:
        """Full directory scan (usually only runs on CLI start)."""
        files = self.crawl(root)
        
        # Clean up cache and index for files that were deleted while offline
        current_paths = {str(f) for f in files}
        stale_paths = [Path(k) for k in self._mtime_cache if k not in current_paths]
        if stale_paths:
            self._process_deletes(stale_paths)

        return self.index_batch(files)

    def index_batch(self, files: list[Path], *, allow_rebuild: bool = True) -> int:
        """Incrementally index a specific list of files if their mtime changed."""
        from whoosh.index import LockError

        indexed_count = 0
        rebuild_error: Exception | None = None

        with LocalIndexer._whoosh_writer_lock:
            try:
                writer = self._open_whoosh_writer()
            except LockError as exc:
                log.warning("Batch indexing deferred because the Whoosh index is busy: %s", exc)
                return 0

            try:
                for fpath in files:
                    str_path = str(fpath)
                    try:
                        current_mtime = fpath.stat().st_mtime
                    except OSError:
                        continue

                    cached_mtime = self._mtime_cache.get(str_path)
                    if cached_mtime is not None and cached_mtime >= current_mtime:
                        continue  # File unchanged

                    # Delete existing chunks for this file before re-indexing
                    if cached_mtime is not None:
                        self._collection.delete(where={"source": str_path})
                        writer.delete_by_term("source", str_path)

                    if self._index_file(fpath, writer):
                        self._mtime_cache[str_path] = current_mtime
                        indexed_count += 1

                writer.commit()
                if indexed_count > 0:
                    self._save_mtime_cache()
                    log.info("Indexed %d updated file(s).", indexed_count)
                return indexed_count

            except Exception as e:
                writer.cancel()
                if allow_rebuild and self._is_dimension_mismatch_error(e):
                    rebuild_error = e
                else:
                    log.error("Batch indexing failed: %s", e)
                    return 0

        if rebuild_error is not None:
            log.warning("Detected local vector-store dimension drift; rebuilding search indexes: %s", rebuild_error)
            return self.rebuild_indexes(files=files)

        return 0

    def _index_file(self, path: Path, whoosh_writer: Any) -> bool:
        """Parse, chunk, embed, and store a single file."""
        blocks = parse_file(path)
        if not blocks:
            return False

        all_chunks: list[dict[str, Any]] = []
        for block_idx, block in enumerate(blocks):
            text_chunks = chunk_text(
                block["text"],
                chunk_words=config.CHUNK_WORDS,
                overlap_words=config.CHUNK_OVERLAP,
            )
            for i, chunk in enumerate(text_chunks):
                all_chunks.append({
                    "text": chunk,
                    "source": str(path),
                    "source_name": block["source"],
                    "page": block.get("page"),
                    "block_idx": block_idx,
                    "chunk_idx": i,
                })

        if not all_chunks:
            return False

        texts = [c["text"] for c in all_chunks]
        embeddings = self.embed_model.encode(texts).tolist()

        ids: list[str] = []
        metadatas: list[dict[str, Any]] = []
        documents: list[str] = []
        
        for idx, chunk_info in enumerate(all_chunks):
            doc_id = f"{chunk_info['source']}::b{chunk_info['block_idx']}::chunk{chunk_info['chunk_idx']}"
            if chunk_info["page"]:
                doc_id += f"::p{chunk_info['page']}"
            ids.append(doc_id)
            metadatas.append({
                "source": chunk_info["source"],
                "source_name": chunk_info["source_name"],
                "page": chunk_info["page"] or 0,
            })
            documents.append(chunk_info["text"])

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )

        for doc_id, chunk_info in zip(ids, all_chunks):
            whoosh_writer.update_document(
                doc_id=doc_id,
                source=chunk_info["source"],
                page=chunk_info.get("page") or 0,
                content=chunk_info["text"],
            )

        return True

    # ── Accessors for the retriever ───────────────────────────────────────

    @property
    def collection(self) -> Any:
        return self._collection

    @property
    def whoosh_index(self) -> Any:
        return self._whoosh_index

    @property
    def embed_model(self) -> Any:
        return self._ensure_embedding_model()