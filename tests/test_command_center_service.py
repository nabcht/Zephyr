from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from backend.schemas.command_center import CommandCenterOverviewResponse, DurableMemoryResponse, MCPOverviewResponse
from backend.services.command_center_service import CommandCenterService
from core.memory_repair import MemoryBrainRepairResult


class _FakeRuntime:
    def __init__(self) -> None:
        self.memory = object()
        self.tool_engine = None
        self.llm = None


class CommandCenterServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_repair_memory_brain_returns_summary_and_overview(self) -> None:
        service = CommandCenterService()
        runtime = _FakeRuntime()
        overview = CommandCenterOverviewResponse(
            runtime_initialized=False,
            commands=[],
            tools=[],
            mcp=MCPOverviewResponse(
                enabled=True,
                external_integrations_enabled=True,
                configured=False,
                message="No MCP servers are configured.",
            ),
            memory=DurableMemoryResponse(facts=["- imported fact"]),
        )
        repaired = MemoryBrainRepairResult(
            raw_fact_count=6,
            fact_count=4,
            duplicate_count=2,
            timeline_line_count=4,
            entity_file_count=3,
            timeline_path=Path("knowledge/brain/timeline.log"),
            truth_path=Path("knowledge/brain/truth.md"),
            backup_paths=(
                Path("knowledge/brain/timeline.log.bak"),
                Path("knowledge/brain/truth.md.bak"),
            ),
        )

        with (
            patch("backend.services.command_center_service.rebuild_memory_brain_from_memories", return_value=repaired),
            patch("backend.services.command_center_service.ensure_memory_ready", new=AsyncMock(return_value=runtime)),
            patch.object(service, "_build_overview", new=AsyncMock(return_value=overview)) as build_overview,
        ):
            response = await service.repair_memory_brain()

        self.assertEqual(response.overview, overview)
        self.assertEqual(response.raw_fact_count, 6)
        self.assertEqual(response.fact_count, 4)
        self.assertEqual(response.duplicate_count, 2)
        self.assertEqual(response.timeline_line_count, 4)
        self.assertEqual(response.entity_file_count, 3)
        self.assertEqual(response.timeline_path, str(Path("knowledge/brain/timeline.log")))
        self.assertEqual(response.truth_path, str(Path("knowledge/brain/truth.md")))
        self.assertEqual(
            response.backup_paths,
            [
                str(Path("knowledge/brain/timeline.log.bak")),
                str(Path("knowledge/brain/truth.md.bak")),
            ],
        )
        self.assertIn("restored 4 unique fact(s)", response.message)
        self.assertIn("2 duplicate(s) skipped", response.message)
        self.assertIn("Preserved 2 backup file(s)", response.message)
        build_overview.assert_awaited_once_with(runtime)


if __name__ == "__main__":
    unittest.main()