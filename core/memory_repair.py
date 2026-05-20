"""Repair helpers for rebuilding the memory brain from durable memories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil

import config
from core import linker
from core.truth_synthesis import recent_unique_facts


@dataclass(frozen=True, slots=True)
class MemoryBrainRepairResult:
    """Summary of a durable-memory brain rebuild."""

    raw_fact_count: int
    fact_count: int
    duplicate_count: int
    timeline_line_count: int
    entity_file_count: int
    timeline_path: Path
    truth_path: Path
    backup_paths: tuple[Path, ...]


def _extract_durable_facts(memories_text: str) -> list[str]:
    facts: list[str] = []
    for line in memories_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        fact = stripped[2:].strip()
        if fact:
            facts.append(fact)
    return facts


def _dedupe_facts(facts: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for fact in facts:
        normalized = fact.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(fact)
    return unique


def _next_backup_path(path: Path) -> Path:
    candidate = path.with_name(f"{path.name}.bak")
    suffix = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.bak{suffix}")
        suffix += 1
    return candidate


def _backup_existing_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup_path = _next_backup_path(path)
    shutil.copy2(path, backup_path)
    return backup_path


def _reset_entity_files() -> None:
    config.ENTITIES_DIR.mkdir(parents=True, exist_ok=True)
    for path in config.ENTITIES_DIR.iterdir():
        if path.name == ".gitkeep":
            continue
        if path.is_file():
            path.unlink()


def _render_timeline_lines(facts: list[str], *, now: datetime | None = None) -> list[str]:
    if not facts:
        return []
    cursor = now or datetime.now(timezone.utc)
    if cursor.tzinfo is None:
        cursor = cursor.replace(tzinfo=timezone.utc)
    else:
        cursor = cursor.astimezone(timezone.utc)

    start = cursor - timedelta(seconds=len(facts) - 1)
    lines: list[str] = []
    for index, fact in enumerate(facts):
        stamp = start + timedelta(seconds=index)
        lines.append(f"[{stamp.strftime('%Y-%m-%dT%H:%M:%SZ')}] {fact}")
    return lines


def _render_truth_lines(timeline_lines: list[str]) -> list[str]:
    facts = recent_unique_facts(timeline_lines, limit=max(len(timeline_lines), 1))
    lines = ["# Truth Layer", ""]
    lines.extend(f"- {fact}" for fact in facts)
    return lines


def rebuild_memory_brain_from_memories(
    *,
    now: datetime | None = None,
    backup_existing: bool = True,
) -> MemoryBrainRepairResult:
    """Rebuild timeline.log, truth.md, and entity files from memories.md."""
    if not config.MEMORIES_FILE.exists():
        raise FileNotFoundError(f"memories file not found: {config.MEMORIES_FILE}")

    raw_facts = _extract_durable_facts(config.MEMORIES_FILE.read_text(encoding="utf-8"))
    if not raw_facts:
        raise ValueError("No durable facts found in memories.md.")

    facts = _dedupe_facts(raw_facts)
    duplicate_count = len(raw_facts) - len(facts)

    config.BRAIN_DIR.mkdir(parents=True, exist_ok=True)
    config.ENTITIES_DIR.mkdir(parents=True, exist_ok=True)

    backup_paths: list[Path] = []
    if backup_existing:
        for path in (config.TIMELINE_FILE, config.TRUTH_FILE):
            backup_path = _backup_existing_file(path)
            if backup_path is not None:
                backup_paths.append(backup_path)

    _reset_entity_files()

    timeline_lines = _render_timeline_lines(facts, now=now)
    config.TIMELINE_FILE.write_text("\n".join(timeline_lines) + "\n", encoding="utf-8")

    for line_no, fact in enumerate(facts, start=1):
        linker.update_entities_from_fact(fact, line_no)

    truth_lines = _render_truth_lines(timeline_lines)
    config.TRUTH_FILE.write_text("\n".join(truth_lines).rstrip() + "\n", encoding="utf-8")

    entity_file_count = sum(
        1 for path in config.ENTITIES_DIR.iterdir()
        if path.is_file() and path.name != ".gitkeep"
    )

    return MemoryBrainRepairResult(
        raw_fact_count=len(raw_facts),
        fact_count=len(facts),
        duplicate_count=duplicate_count,
        timeline_line_count=len(timeline_lines),
        entity_file_count=entity_file_count,
        timeline_path=config.TIMELINE_FILE,
        truth_path=config.TRUTH_FILE,
        backup_paths=tuple(backup_paths),
    )