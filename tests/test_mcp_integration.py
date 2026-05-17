from __future__ import annotations

import unittest
from unittest.mock import patch

import config
from core.mcp_contracts import MCPErrorKind, MCPServerSettings, MCPServerStatus, MCPToolError, MCPToolResult, MCPToolSpec
from core.mcp_runtime import MCPRuntimeManager
from core.tool_engine import ToolEngine


class _FakeMemory:
    def __init__(self) -> None:
        self.clients = None

    def set_mcp_clients(self, clients: list[object]) -> None:
        self.clients = list(clients)


class _FakeServerClient:
    def __init__(
        self,
        settings: MCPServerSettings,
        *,
        tools: list[MCPToolSpec] | None = None,
    ) -> None:
        self.settings = settings
        self.server_name = settings.name
        self.enabled = bool(settings.command)
        self._tools = list(tools or [])
        self._list_failure: Exception | None = None
        self._invoke_failures: dict[str, Exception] = {}
        self._invoke_results: dict[str, MCPToolResult] = {}
        self.list_tools_calls = 0
        self.invoke_calls = 0
        self.reconnects = 0
        self.closed = False

    def get_status(self) -> MCPServerStatus:
        return MCPServerStatus(
            name=self.settings.name,
            tool_prefix=self.settings.tool_prefix,
            command=self.settings.command,
            args=list(self.settings.args),
            connected=not self.closed,
            discovered_tools=[tool.local_name for tool in self._tools],
            last_error=str(self._list_failure) if self._list_failure else None,
        )

    async def list_tools(self) -> list[MCPToolSpec]:
        self.list_tools_calls += 1
        if self._list_failure is not None:
            raise self._list_failure
        self.closed = False
        return list(self._tools)

    async def invoke_tool(self, remote_name: str, arguments: dict[str, object] | None = None) -> MCPToolResult:
        del arguments
        self.invoke_calls += 1
        if self.closed:
            self.closed = False
            self.reconnects += 1

        failure = self._invoke_failures.get(remote_name)
        if failure is not None:
            raise failure

        result = self._invoke_results.get(remote_name)
        if result is not None:
            return result
        return MCPToolResult(tool_name=remote_name, rendered_content=f"{self.server_name}:{remote_name}")

    async def close(self) -> None:
        self.closed = True


def _tool(local_name: str, remote_name: str = "search") -> MCPToolSpec:
    return MCPToolSpec(
        local_name=local_name,
        remote_name=remote_name,
        description=f"MCP tool {remote_name}",
        parameters={"type": "object"},
    )


class MCPIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _build_engine(
        self,
        settings: list[MCPServerSettings],
        client_factory: object,
    ) -> tuple[ToolEngine, dict[str, _FakeServerClient]]:
        memory = _FakeMemory()
        created_clients: dict[str, _FakeServerClient] = {}

        def tracked_factory(server_settings: MCPServerSettings) -> _FakeServerClient:
            client = client_factory(server_settings)
            created_clients[server_settings.name] = client
            return client

        with patch.object(config, "get_mcp_server_configs", return_value=[]):
            engine = ToolEngine(memory)

        engine._mcp_runtime = MCPRuntimeManager(memory, settings=settings, client_factory=tracked_factory)
        return engine, created_clients

    async def test_refresh_failure_reuses_cached_inventory_and_execution_reconnects(self) -> None:
        archive_settings = MCPServerSettings(name="Archive", command="python", args=[], env={})

        def client_factory(server_settings: MCPServerSettings) -> _FakeServerClient:
            return _FakeServerClient(server_settings, tools=[_tool("mcp_archive_search")])

        engine, created_clients = self._build_engine([archive_settings], client_factory)

        await engine.refresh_mcp_tools()
        archive = created_clients["Archive"]
        archive._list_failure = RuntimeError("refresh boom")

        await engine.refresh_mcp_tools()

        self.assertIn("mcp_archive_search", engine.list_tool_names())
        self.assertTrue(archive.closed)
        self.assertEqual(archive.list_tools_calls, 2)

        archive._invoke_results["search"] = MCPToolResult(
            tool_name="search",
            rendered_content="2 hits",
            structured_content={"hits": 2, "query": "runtime"},
        )

        result = await engine.execute_detailed("mcp_archive_search", {"query": "runtime"})

        self.assertEqual(result.display_text, "2 hits")
        self.assertEqual(result.structured_content, {"hits": 2, "query": "runtime"})
        self.assertEqual(archive.reconnects, 1)

    async def test_archive_execution_failure_recovers_on_next_call(self) -> None:
        archive_settings = MCPServerSettings(name="Archive", command="python", args=[], env={})

        def client_factory(server_settings: MCPServerSettings) -> _FakeServerClient:
            return _FakeServerClient(server_settings, tools=[_tool("mcp_archive_search")])

        engine, created_clients = self._build_engine([archive_settings], client_factory)
        await engine.refresh_mcp_tools()

        archive = created_clients["Archive"]
        archive._invoke_failures["search"] = MCPToolError(
            kind=MCPErrorKind.EXECUTION,
            server_name="Archive",
            tool_name="search",
            message="tool exploded",
        )

        failure = await engine.execute_detailed("mcp_archive_search", {"query": "runtime"})

        self.assertTrue(failure.is_error)
        self.assertIn("temporarily unavailable", failure.display_text)
        self.assertEqual(failure.structured_content, {
            "server_name": "Archive",
            "error_kind": "execution",
            "remote_name": "search",
        })

        del archive._invoke_failures["search"]
        archive._invoke_results["search"] = MCPToolResult(
            tool_name="search",
            rendered_content="Recovered",
            structured_content={"hits": 1},
        )

        recovered = await engine.execute_detailed("mcp_archive_search", {"query": "runtime"})

        self.assertFalse(recovered.is_error)
        self.assertEqual(recovered.display_text, "Recovered")
        self.assertEqual(recovered.structured_content, {"hits": 1})

    async def test_duplicate_tool_names_bind_to_first_available_server_then_refresh_to_backup(self) -> None:
        settings = [
            MCPServerSettings(name="Archive", command="python", args=[], env={}),
            MCPServerSettings(name="Backup", command="python", args=[], env={}),
        ]

        def client_factory(server_settings: MCPServerSettings) -> _FakeServerClient:
            client = _FakeServerClient(server_settings, tools=[_tool("mcp_shared_search")])
            if server_settings.name == "Archive":
                client._invoke_results["search"] = MCPToolResult(tool_name="search", rendered_content="archive result")
            else:
                client._invoke_results["search"] = MCPToolResult(tool_name="search", rendered_content="backup result")
            return client

        engine, created_clients = self._build_engine(settings, client_factory)

        await engine.refresh_mcp_tools()

        first = await engine.execute("mcp_shared_search", {"query": "runtime"})

        self.assertEqual(first, "archive result")
        self.assertEqual(engine.list_tool_names().count("mcp_shared_search"), 1)

        created_clients["Archive"]._tools = []

        await engine.refresh_mcp_tools()

        second = await engine.execute("mcp_shared_search", {"query": "runtime"})

        self.assertEqual(second, "backup result")
        self.assertEqual(engine.list_tool_names().count("mcp_shared_search"), 1)


if __name__ == "__main__":
    unittest.main()