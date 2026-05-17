from __future__ import annotations

import unittest
from unittest.mock import patch

import config
from backend.services.command_center_runtime_service import CommandCenterRuntimeService
from core.mcp_contracts import MCPErrorKind, MCPServerSettings, MCPServerStatus, MCPServerState
from core.tool_executor import ToolExecutionResult
from core.tool_registry import ToolDef


class _FakeToolEngine:
    def __init__(
        self,
        *,
        tools: list[ToolDef] | None = None,
        statuses: list[MCPServerStatus] | None = None,
        recent_executions: list[ToolExecutionResult] | None = None,
    ) -> None:
        self._tools = list(tools or [])
        self._statuses = list(statuses or [])
        self._recent_executions = list(recent_executions or [])

    def list_tools(self) -> list[ToolDef]:
        return list(self._tools)

    def get_mcp_server_statuses(self) -> list[MCPServerStatus]:
        return list(self._statuses)

    def get_recent_tool_executions(self, *, source: str | None = None, limit: int | None = None) -> list[ToolExecutionResult]:
        recent = list(self._recent_executions)
        if source is not None:
            recent = [execution for execution in recent if execution.source == source]
        if limit is not None:
            recent = recent[:limit]
        return recent


class CommandCenterRuntimeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = CommandCenterRuntimeService()

    def test_build_tool_entries_sorts_and_labels_tools(self) -> None:
        tool_engine = _FakeToolEngine(
            tools=[
                ToolDef(name="manual_tool", description="Manual", fn=lambda: None, source="manual"),
                ToolDef(name="builtin_tool", description="Built-in", fn=lambda: None, source="builtin"),
                ToolDef(name="local_tool", description="Local", fn=lambda: None, source="local"),
                ToolDef(name="mcp_tool", description="MCP", fn=lambda: None, source="mcp"),
            ]
        )

        entries = self.service.build_tool_entries(tool_engine)

        self.assertEqual([entry.name for entry in entries], ["local_tool", "builtin_tool", "mcp_tool", "manual_tool"])
        self.assertEqual(entries[0].source_label, "Skill")
        self.assertEqual(entries[1].source_label, "Built-in")
        self.assertEqual(entries[2].source_label, "MCP")
        self.assertEqual(entries[3].source_label, "Manual")

    def test_build_mcp_overview_reports_uninitialized_runtime(self) -> None:
        with patch.object(config, "MCP_ENABLED", True), patch.object(
            config,
            "EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED",
            True,
        ), patch.object(config, "get_mcp_server_configs", return_value=[MCPServerSettings(name="archive", command="python", args=[], env={})]):
            overview = self.service.build_mcp_overview(None)

        self.assertTrue(overview.enabled)
        self.assertTrue(overview.configured)
        self.assertEqual(
            overview.message,
            "Runtime is not initialized yet. Send a chat turn, reload tools, or prepare the runtime to inspect MCP servers.",
        )

    def test_build_mcp_overview_serializes_server_statuses(self) -> None:
        tool_engine = _FakeToolEngine(
            statuses=[
                MCPServerStatus(
                    name="archive",
                    tool_prefix="mcp",
                    command="python",
                    args=["-m", "archive"],
                    connected=False,
                    discovered_tools=["mcp_archive_search"],
                    last_error="MCP tool 'search' failed.",
                    last_discovered_at="2026-05-17T12:00:00Z",
                    last_successful_connection_at="2026-05-17T11:55:00Z",
                    state=MCPServerState.ERROR,
                    last_error_kind=MCPErrorKind.EXECUTION,
                    last_error_tool_name="search",
                    degraded_reason="Most recent MCP tool execution failed: search.",
                )
            ],
            recent_executions=[
                ToolExecutionResult(
                    tool_name="mcp_archive_search",
                    source="mcp",
                    display_text="2 hits",
                    executed_at="2026-05-17T12:02:00Z",
                    structured_content={"hits": 2, "query": "runtime"},
                )
            ],
        )

        with patch.object(config, "MCP_ENABLED", True), patch.object(
            config,
            "EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED",
            True,
        ), patch.object(config, "get_mcp_server_configs", return_value=[]):
            overview = self.service.build_mcp_overview(tool_engine)

        self.assertTrue(overview.configured)
        self.assertEqual(
            overview.message,
            "1 MCP server(s) configured. Showing cached inventory from the last successful discovery refresh for servers with current errors.",
        )
        self.assertEqual(len(overview.servers), 1)
        self.assertEqual(overview.servers[0].name, "archive")
        self.assertEqual(overview.servers[0].discovered_tools, ["mcp_archive_search"])
        self.assertEqual(overview.servers[0].state, MCPServerState.ERROR)
        self.assertEqual(overview.servers[0].last_discovered_at, "2026-05-17T12:00:00Z")
        self.assertEqual(overview.servers[0].last_successful_connection_at, "2026-05-17T11:55:00Z")
        self.assertEqual(overview.servers[0].last_error_kind, MCPErrorKind.EXECUTION)
        self.assertEqual(overview.servers[0].last_error_tool_name, "search")
        self.assertEqual(overview.servers[0].degraded_reason, "Most recent MCP tool execution failed: search.")
        self.assertEqual(len(overview.recent_executions), 1)
        self.assertEqual(overview.recent_executions[0].tool_name, "mcp_archive_search")
        self.assertEqual(overview.recent_executions[0].structured_content_type, "object")
        self.assertEqual(overview.recent_executions[0].structured_content_preview, '{"hits": 2, "query": "runtime"}')


if __name__ == "__main__":
    unittest.main()