"""Browser history search — queries local Chrome / Edge SQLite history."""

from __future__ import annotations

import os
import platform
import shutil
import sqlite3
import tempfile
from pathlib import Path


def _find_history_db() -> Path | None:
    """Locate the default Chrome or Edge History SQLite file on the current OS."""
    system = platform.system()
    candidates: list[Path] = []

    if system == "Windows":
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        candidates = [
            local / "Google" / "Chrome" / "User Data" / "Default" / "History",
            local / "Microsoft" / "Edge" / "User Data" / "Default" / "History",
        ]
    elif system == "Darwin":
        home = Path.home()
        candidates = [
            home / "Library" / "Application Support" / "Google" / "Chrome" / "Default" / "History",
            home / "Library" / "Application Support" / "Microsoft Edge" / "Default" / "History",
        ]
    else:  # Linux
        home = Path.home()
        candidates = [
            home / ".config" / "google-chrome" / "Default" / "History",
            home / ".config" / "microsoft-edge" / "Default" / "History",
            home / ".config" / "chromium" / "Default" / "History",
        ]

    for p in candidates:
        if p.exists():
            return p
    return None


async def browser_search(query: str, max_results: int = 20) -> str:
    """Search your local browser history (Chrome/Edge) for pages matching a keyword.

    Args:
        query: Keyword to search in visited URLs and page titles.
        max_results: Maximum number of history entries to return.
    """
    db_path = _find_history_db()
    if db_path is None:
        return "Could not find a Chrome or Edge History database on this system."

    # Copy to a temp file to avoid the SQLite lock held by the browser
    tmp = Path(tempfile.mkdtemp()) / "History_copy"
    try:
        shutil.copy2(db_path, tmp)
    except PermissionError:
        return "Permission denied copying browser history. Close the browser or run with appropriate privileges."

    try:
        conn = sqlite3.connect(str(tmp))
        cursor = conn.execute(
            """
            SELECT url, title, datetime(last_visit_time / 1000000 - 11644473600, 'unixepoch') AS visit_time
            FROM urls
            WHERE url LIKE ? OR title LIKE ?
            ORDER BY last_visit_time DESC
            LIMIT ?
            """,
            (f"%{query}%", f"%{query}%", max_results),
        )
        rows = cursor.fetchall()
        conn.close()
    except sqlite3.Error as exc:
        return f"SQLite error reading browser history: {exc}"
    finally:
        tmp.unlink(missing_ok=True)

    if not rows:
        return f"No browser history entries matching '{query}'."

    lines: list[str] = []
    for url, title, visit_time in rows:
        lines.append(f"• [{title or 'Untitled'}]({url})  — {visit_time or 'unknown'}")
    return "\n".join(lines)
