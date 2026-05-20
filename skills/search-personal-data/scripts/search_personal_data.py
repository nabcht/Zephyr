"""Optimised personal data search — hybrid semantic + keyword retrieval.

Uses ChromaDB vectors for conceptual matches and Whoosh for exact keyword
hits. Falls back to a simple recursive grep when the index is not yet built.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger("zephyr.search_personal_data")

# Singleton retriever reference, injected at startup by the tool engine
_retriever: Any = None  # core.retriever.HybridRetriever | None


def _set_retriever(retriever: Any) -> None:
    """Called once during initialisation to wire up the hybrid retriever."""
    global _retriever
    _retriever = retriever


# ── Fallback grep (original behaviour) ───────────────────────────────────────

_TEXT_EXTENSIONS: set[str] = {
    ".txt", ".md", ".py", ".json", ".csv", ".log", ".yaml", ".yml",
    ".toml", ".cfg", ".ini", ".html", ".xml", ".rst",
}
_MAX_FILE_SIZE: int = 5 * 1024 * 1024


def _grep_search(query: str, directory: str, max_results: int) -> str:
    """Legacy recursive keyword scan for when the index is unavailable."""
    root = Path(directory) if directory else Path.home() / "Documents"
    if not root.exists():
        return f"Directory does not exist: {root}"

    query_lower = query.lower()
    matches: list[str] = []

    for dirpath, _dirnames, filenames in os.walk(root):
        if len(matches) >= max_results:
            break
        for fname in filenames:
            if len(matches) >= max_results:
                break
            fpath = Path(dirpath) / fname
            if fpath.suffix.lower() not in _TEXT_EXTENSIONS:
                continue
            if fpath.stat().st_size > _MAX_FILE_SIZE:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except (PermissionError, OSError):
                continue
            if query_lower in text.lower():
                idx = text.lower().find(query_lower)
                start = max(0, idx - 80)
                end = min(len(text), idx + len(query) + 80)
                snippet = text[start:end].replace("\n", " ").strip()
                matches.append(f"• **{fpath}**\n  …{snippet}…")

    if not matches:
        return f"No files containing '{query}' found under {root}."
    return "\n\n".join(matches)


# ── Primary tool function ────────────────────────────────────────────────────


async def search_personal_data(
    query: str,
    directory: str = "",
    max_results: int = 10,
) -> str:
    """Search local files using hybrid semantic + keyword retrieval.

    Args:
        query: The search query — can be a keyword or a natural-language question.
        directory: Root directory to search in. Defaults to user's ~/Documents.
        max_results: Maximum number of matching snippets to return.
    """
    # Defensive fix: Cast to int to prevent TypeError from string inputs
    try:
        max_results = int(max_results)
    except (ValueError, TypeError):
        max_results = 10

    # If the index has been built, use the optimised path
    if _retriever is not None:
        try:
            results = await _retriever.search(
                query,
                semantic_k=min(max_results, 3),
                keyword_k=min(max_results, 5),
            )
            if results:
                return _retriever.format_results(results[:max_results])
            log.debug("Index returned no results; falling back to grep.")
        except Exception as exc:
            log.warning("Hybrid search failed, falling back to grep: %s", exc)

    # Fallback to the original recursive keyword scan
    return _grep_search(query, directory, max_results)

