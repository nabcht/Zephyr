"""Hybrid memory — SQLite session history + Markdown durable-facts RAG."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite
from rank_bm25 import BM25Okapi

import config
from core import linker
from core.archive import ArchiveBridge

log = logging.getLogger("zephyr.memory")


class MemoryManager:
    """Manages short-term (SQLite) and long-term (memories.md) storage."""

    def __init__(self) -> None:
        self._db: aiosqlite.Connection | None = None
        self._memories_path: Path = config.MEMORIES_FILE
        self.archive = ArchiveBridge(project_name=config.PROJECT_ROOT.name)
        # BM25 cache: invalidated when memories.md mtime changes
        self._bm25_cache: BM25Okapi | None = None
        self._bm25_facts: list[str] = []
        self._bm25_mtime: float = 0.0

    # ── Lifecycle ─────────────────────────────────────────────────────────
    async def initialize(self) -> None:
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        if not self._memories_path.exists():
            self._memories_path.write_text(
                "# μZephyr Durable Memory\n",
                encoding="utf-8",
            )

        self._db = await aiosqlite.connect(str(config.DB_PATH))
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                session   TEXT    NOT NULL,
                role      TEXT    NOT NULL,
                content   TEXT    NOT NULL,
                timestamp TEXT    NOT NULL
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS session_attachments (
                attachment_id TEXT PRIMARY KEY,
                session       TEXT    NOT NULL,
                name          TEXT    NOT NULL,
                stored_path   TEXT    NOT NULL UNIQUE,
                media_type    TEXT    NOT NULL,
                size_bytes    INTEGER NOT NULL,
                created_at    TEXT    NOT NULL
            )
        """)
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_session_attachments_session ON session_attachments (session, created_at)"
        )
        await self._db.commit()
        log.info("Memory subsystem ready (db=%s)", config.DB_PATH)

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None
        await self.archive.aclose()

    def set_mcp_clients(self, clients: list[Any]) -> None:
        self.archive.set_mcp_clients(clients)

    # ══════════════════════════════════════════════════════════════════════
    #  SHORT-TERM: SQLite session history
    # ══════════════════════════════════════════════════════════════════════
    async def add_message(self, session: str, role: str, content: str) -> None:
        if self._db is None:
            raise RuntimeError("MemoryManager is not initialised — call initialize() first.")
        ts = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "INSERT INTO messages (session, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session, role, content, ts),
        )
        await self._db.commit()

    async def get_session_history(
        self,
        session: str,
        limit: int = 20,
    ) -> list[dict[str, str]]:
        if self._db is None:
            raise RuntimeError("MemoryManager is not initialised — call initialize() first.")
        cursor = await self._db.execute(
            "SELECT role, content FROM messages WHERE session = ? ORDER BY id DESC LIMIT ?",
            (session, limit),
        )
        rows = await cursor.fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    @staticmethod
    def _attachment_row_to_record(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "attachment_id": str(row[0]),
            "session_id": str(row[1]),
            "name": str(row[2]),
            "stored_path": str(row[3]),
            "media_type": str(row[4]),
            "size_bytes": int(row[5]),
            "created_at": str(row[6]),
        }

    async def add_session_attachment(
        self,
        session: str,
        attachment_id: str,
        *,
        name: str,
        stored_path: str,
        media_type: str,
        size_bytes: int,
    ) -> dict[str, Any]:
        if self._db is None:
            raise RuntimeError("MemoryManager is not initialised — call initialize() first.")

        created_at = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            (
                "INSERT INTO session_attachments "
                "(attachment_id, session, name, stored_path, media_type, size_bytes, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)"
            ),
            (attachment_id, session, name, stored_path, media_type, int(size_bytes), created_at),
        )
        await self._db.commit()
        return {
            "attachment_id": attachment_id,
            "session_id": session,
            "name": name,
            "stored_path": stored_path,
            "media_type": media_type,
            "size_bytes": int(size_bytes),
            "created_at": created_at,
        }

    async def get_session_attachments(self, session: str) -> list[dict[str, Any]]:
        if self._db is None:
            raise RuntimeError("MemoryManager is not initialised — call initialize() first.")

        cursor = await self._db.execute(
            (
                "SELECT attachment_id, session, name, stored_path, media_type, size_bytes, created_at "
                "FROM session_attachments WHERE session = ? ORDER BY created_at ASC"
            ),
            (session,),
        )
        rows = await cursor.fetchall()
        return [self._attachment_row_to_record(row) for row in rows]

    async def get_session_attachment(self, session: str, attachment_id: str) -> dict[str, Any] | None:
        if self._db is None:
            raise RuntimeError("MemoryManager is not initialised — call initialize() first.")

        cursor = await self._db.execute(
            (
                "SELECT attachment_id, session, name, stored_path, media_type, size_bytes, created_at "
                "FROM session_attachments WHERE session = ? AND attachment_id = ?"
            ),
            (session, attachment_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._attachment_row_to_record(row)

    async def remove_session_attachment(self, session: str, attachment_id: str) -> dict[str, Any] | None:
        if self._db is None:
            raise RuntimeError("MemoryManager is not initialised — call initialize() first.")

        existing = await self.get_session_attachment(session, attachment_id)
        if existing is None:
            return None

        await self._db.execute(
            "DELETE FROM session_attachments WHERE session = ? AND attachment_id = ?",
            (session, attachment_id),
        )
        await self._db.commit()
        return existing

    # ══════════════════════════════════════════════════════════════════════
    #  LONG-TERM: Markdown durable facts
    # ══════════════════════════════════════════════════════════════════════
    def _read_facts(self) -> list[str]:
        """Return every fact line from memories.md (stripped, non-empty, prefixed with '- ')."""
        if not self._memories_path.exists():
            return []
        lines = self._memories_path.read_text(encoding="utf-8").splitlines()
        return [ln.strip() for ln in lines if ln.strip().startswith("- ")]

    async def get_durable_facts(self) -> str:
        """Return all durable facts as a newline-joined string."""
        return "\n".join(self._read_facts())

    async def get_relevant_facts(self, query: str, top_k: int = 5) -> str:
        """BM25 keyword search over durable facts; return top_k most relevant."""
        facts = self._read_facts()
        if not facts:
            return ""

        # Rebuild BM25 only when memories.md has changed
        try:
            current_mtime = self._memories_path.stat().st_mtime
        except OSError:
            current_mtime = 0.0

        if (
            self._bm25_cache is None
            or current_mtime != self._bm25_mtime
            or facts != self._bm25_facts
        ):
            tokenized = [f.lower().split() for f in facts]
            self._bm25_cache = BM25Okapi(tokenized)
            self._bm25_facts = facts
            self._bm25_mtime = current_mtime

        scores = self._bm25_cache.get_scores(query.lower().split())
        ranked = sorted(zip(scores, facts), reverse=True)
        return "\n".join(fact for _, fact in ranked[:top_k])

    # ── Tools (exposed to the LLM) ───────────────────────────────────────
    async def memory_durable_fact(self, fact: str) -> str:
        """Save a durable fact about the user or a learned insight to long-term memory.

        Args:
            fact: The fact to persist (e.g. "User prefers dark themes").
        """
        clean = fact.strip()

        # Deduplication: skip if an identical fact already exists (case-insensitive).
        clean_lower = clean.lower()
        for existing in self._read_facts():
            # _read_facts() returns lines like "- <fact text>"
            existing_text = existing[2:].strip().lower() if existing.startswith("- ") else existing.lower()
            if existing_text == clean_lower:
                log.info("Duplicate fact skipped: %s", clean)
                return f"Fact already in durable memory (duplicate skipped): {clean}"

        # 1. Append to memories.md (existing behaviour)
        entry = f"- {clean}\n"
        with self._memories_path.open("a", encoding="utf-8") as fh:
            fh.write(entry)

        # 2. Append to timeline.log (μBrain evidence stream — append-only)
        config.BRAIN_DIR.mkdir(parents=True, exist_ok=True)
        config.ENTITIES_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with config.TIMELINE_FILE.open("a", encoding="utf-8") as tl:
            tl.write(f"[{ts}] {clean}\n")

        # Count total lines in a single read pass (the fact we just wrote is included)
        with config.TIMELINE_FILE.open("r", encoding="utf-8") as tl:
            line_no = sum(1 for _ in tl)

        # 3. Update entity files for any #Person or [[Project]] tokens
        linker.update_entities_from_fact(clean, line_no)

        try:
            await self.archive.add_observation(clean)
        except Exception as exc:
            log.warning("Archive sync skipped for durable fact '%s': %s", clean, exc)

        log.info("Durable fact saved: %s", clean)
        return f"Saved to durable memory: {clean}"

    async def memory_force_delete_durable_fact(self, fact_substring: str) -> str:
        """Delete a durable fact from long-term memory that contains the given substring.

        Args:
            fact_substring: A distinctive part of the fact to remove.
        """
        lines = self._memories_path.read_text(encoding="utf-8").splitlines()
        new_lines = []
        deleted =[]
        
        search_target = fact_substring.strip().lower()
        
        for ln in lines:
            # Only process actual facts (lines starting with '- ')
            if ln.strip().startswith("- ") and search_target in ln.lower():
                deleted.append(ln.strip())
            else:
                new_lines.append(ln)
                
        if not deleted:
            return f"Fact not found containing: '{fact_substring}'"
            
        self._memories_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        log.info("Durable fact(s) deleted: %s", deleted)
        
        # Invalidate BM25 cache so the retriever forgets it instantly
        self._bm25_mtime = 0.0 
        
        return f"Deleted from durable memory: {deleted[0]}"
