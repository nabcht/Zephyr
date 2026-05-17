from __future__ import annotations

import unittest

from backend.services.mission_session_service import MissionSessionService
from core.blackboard import Blackboard
from core.mission_service import MissionService


class MissionStreamSnapshotTests(unittest.TestCase):
    def test_initial_progress_snapshot_includes_status_sections(self) -> None:
        snapshot = MissionSessionService._initial_progress_snapshot("stabilize MCP mission flow")

        self.assertIn("Mission in progress", snapshot)
        self.assertIn("Sandbox: No code proposed yet", snapshot)
        self.assertIn("Review: No review completed yet", snapshot)
        self.assertIn("MCP: No MCP tool results recorded yet", snapshot)
        self.assertIn("Recent milestones:", snapshot)

    def test_progress_snapshot_reports_failed_sandbox_from_argument_drift_feedback(self) -> None:
        board = Blackboard(mission_id="mission-1", goal="Fix MCP mission flow")
        board.set_code("print('ok')")
        board.set_sandbox_feedback(
            "❌ ERROR: Sandbox verification requires executable Python in the 'code' field, not only a description."
        )

        snapshot = MissionService._format_progress_snapshot(
            board,
            "Sandbox verification failed for the latest code proposal.",
            1,
        )

        self.assertIn("Sandbox: Latest code failed sandbox verification", snapshot)
        self.assertIn("Review: Awaiting reviewer verification", snapshot)

    def test_progress_snapshot_reports_hardened_sandbox_success(self) -> None:
        board = Blackboard(mission_id="mission-2", goal="Fix MCP mission flow")
        board.set_code("print('ok')")
        board.set_sandbox_feedback("✅ TEST PASSED\nBACKEND: DOCKER\nSTDOUT:\nok\n")

        snapshot = MissionService._format_progress_snapshot(
            board,
            "Sandbox verification passed for the latest code proposal.",
            1,
        )

        self.assertIn("Sandbox: Latest code passed sandbox verification", snapshot)

    def test_progress_snapshot_includes_recent_mcp_execution_summary(self) -> None:
        board = Blackboard(mission_id="mission-3", goal="Inspect MCP results")

        snapshot = MissionService._format_progress_snapshot(
            board,
            "Archive search completed.",
            1,
            latest_mcp_execution_summary='mcp_archive_search returned object: {"hits": 2}',
        )

        self.assertIn('MCP: mcp_archive_search returned object: {"hits": 2}', snapshot)


if __name__ == "__main__":
    unittest.main()