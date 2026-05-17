---
name: index-files
description: Index local files and optionally watch a folder for automatic RAG indexing using ChromaDB and Whoosh. Use when the user wants to make local files searchable or enable hot-watch on a directory.
compatibility: Requires Python 3.10+, ChromaDB, and Whoosh. The core LocalIndexer must be initialised.
---

# index-files

Provides two async tools:

- **`start_file_watch(watch_dir=None)`** — starts indexing files in the given
  directory (defaults to `file-src/` in the project root) and keeps the index
  updated.
- **`stop_file_watch()`** — gracefully stops the active watcher.

## Implementation

Logic lives in `scripts/index_files.py`.
