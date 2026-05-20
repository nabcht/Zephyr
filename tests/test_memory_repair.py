from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import config
from core.memory_repair import rebuild_memory_brain_from_memories
from core.truth_synthesis import get_truth_synthesis_health


class MemoryRepairTests(unittest.TestCase):
    def test_rebuilds_brain_from_imported_memories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            memories_path = root / "knowledge" / "memories.md"
            brain_dir = root / "knowledge" / "brain"
            entities_dir = brain_dir / "entities"
            timeline_path = brain_dir / "timeline.log"
            truth_path = brain_dir / "truth.md"

            memories_path.parent.mkdir(parents=True, exist_ok=True)
            entities_dir.mkdir(parents=True, exist_ok=True)

            memories_path.write_text(
                "\n".join(
                    [
                        "# Durable Memory",
                        "- #Alice built [[Zephyr]]",
                        "- preferred editor is vscode",
                        "- PREFERRED EDITOR IS VSCODE",
                        "- feature is enabled",
                        "- feature is disabled",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.object(config, "MEMORIES_FILE", memories_path), patch.object(config, "BRAIN_DIR", brain_dir), patch.object(config, "ENTITIES_DIR", entities_dir), patch.object(config, "TIMELINE_FILE", timeline_path), patch.object(config, "TRUTH_FILE", truth_path):
                result = rebuild_memory_brain_from_memories(
                    now=datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc),
                    backup_existing=False,
                )

                self.assertEqual(result.raw_fact_count, 5)
                self.assertEqual(result.fact_count, 4)
                self.assertEqual(result.duplicate_count, 1)
                self.assertEqual(result.timeline_line_count, 4)

                timeline_lines = timeline_path.read_text(encoding="utf-8").splitlines()
                self.assertEqual(
                    timeline_lines,
                    [
                        "[2026-05-20T11:59:57Z] #Alice built [[Zephyr]]",
                        "[2026-05-20T11:59:58Z] preferred editor is vscode",
                        "[2026-05-20T11:59:59Z] feature is enabled",
                        "[2026-05-20T12:00:00Z] feature is disabled",
                    ],
                )

                truth_text = truth_path.read_text(encoding="utf-8")
                self.assertIn("- #Alice built [[Zephyr]]", truth_text)
                self.assertIn("- preferred editor is vscode", truth_text)
                self.assertIn("- feature is disabled", truth_text)
                self.assertNotIn("- feature is enabled", truth_text)

                self.assertTrue((entities_dir / "Alice.md").exists())
                self.assertTrue((entities_dir / "Zephyr.md").exists())

                health = get_truth_synthesis_health(lines=40)
                self.assertTrue(health.healthy)
                self.assertEqual(health.detail, "truth.md covers recent timeline facts with no detected simple contradictions.")


if __name__ == "__main__":
    unittest.main()