"""Rebuild timeline.log, truth.md, and entities from durable memories."""

from __future__ import annotations

import argparse

from core.memory_repair import rebuild_memory_brain_from_memories


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild timeline.log, truth.md, and entity backlinks from knowledge/memories.md.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create .bak copies of existing timeline.log or truth.md before rewriting them.",
    )
    args = parser.parse_args()

    result = rebuild_memory_brain_from_memories(backup_existing=not args.no_backup)

    print(
        "Rebuilt memory brain from "
        f"{result.raw_fact_count} memory entries "
        f"({result.fact_count} unique facts, {result.duplicate_count} duplicate(s) skipped)."
    )
    print(f"timeline.log: {result.timeline_path}")
    print(f"truth.md: {result.truth_path}")
    print(f"entity files: {result.entity_file_count}")
    if result.backup_paths:
        print("backups:")
        for path in result.backup_paths:
            print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())