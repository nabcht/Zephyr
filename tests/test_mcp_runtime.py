from __future__ import annotations

import unittest
from unittest.mock import patch

from core.mcp_contracts import MCPServerSettings, MCPServerStatus, MCPToolSpec
from core.mcp_runtime import MCPRuntimeManager


class _FakeMemory:
    def __init__(self) -> None:
        self.clients = None

    def set_mcp_clients(self, clients: list[object]) -> None:
        self.clients = clients


class _FakeClient:
    def __init__(self, settings: MCPServerSettings, *, tools: list[MCPToolSpec] | None = None, failure: Exception | None = None) -> None:
        self.settings = settings
        self.server_name = settings.name
        self.enabled = bool(settings.command)
        self._tools = list(tools or [])
        self._failure = failure
        self.list_tools_calls = 0
        self.closed = False

    def get_status(self) -> MCPServerStatus:
        return MCPServerStatus(
            name=self.settings.name,
            tool_prefix=self.settings.tool_prefix,
            command=self.settings.command,
            args=list(self.settings.args),
            connected=not self.closed,
            discovered_tools=[tool.local_name for tool in self._tools],
            last_error=str(self._failure) if self._failure else None,
        )

    async def list_tools(self) -> list[MCPToolSpec]:
        self.list_tools_calls += 1
        if self._failure is not None:
            raise self._failure
        return list(self._tools)

    async def close(self) -> None:
        self.closed = True


class MCPRuntimeManagerTests(unittest.IsolatedAsyncioTestCase):
    def test_initialization_propagates_clients_to_memory(self) -> None:
        memory = _FakeMemory()
        settings = [MCPServerSettings(name="Archive", command="python", args=[], env={})]

        manager = MCPRuntimeManager(memory, settings=settings, client_factory=_FakeClient)

        self.assertIsNotNone(memory.clients)
        self.assertEqual(memory.clients, manager.clients)
        self.assertEqual(len(manager.clients), 1)

    def test_get_server_statuses_delegates_to_clients(self) -> None:
        memory = _FakeMemory()
        settings = [MCPServerSettings(name="Archive", command="python", args=["-m", "archive"], env={}, tool_prefix="mcp")]

        manager = MCPRuntimeManager(memory, settings=settings, client_factory=_FakeClient)
        statuses = manager.get_server_statuses()

        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0].name, "Archive")
        self.assertEqual(statuses[0].args, ["-m", "archive"])

    async def test_discover_tools_skips_failed_clients_and_closes_them(self) -> None:
        memory = _FakeMemory()
        good_tool = MCPToolSpec(
            local_name="mcp_archive_search",
            remote_name="search",
            description="Search archive",
            parameters={"type": "object"},
        )
        settings = [
            MCPServerSettings(name="Archive", command="python", args=[], env={}),
            MCPServerSettings(name="Broken", command="python", args=[], env={}),
        ]
        created_clients: dict[str, _FakeClient] = {}

        def client_factory(server_settings: MCPServerSettings) -> _FakeClient:
            if server_settings.name == "Broken":
                client = _FakeClient(server_settings, failure=RuntimeError("boom"))
            else:
                client = _FakeClient(server_settings, tools=[good_tool])
            created_clients[server_settings.name] = client
            return client

        manager = MCPRuntimeManager(memory, settings=settings, client_factory=client_factory)
        discovered = await manager.discover_tools()

        self.assertEqual(len(discovered), 1)
        self.assertEqual(discovered[0].client.server_name, "Archive")
        self.assertEqual(discovered[0].tool.remote_name, "search")
        self.assertTrue(created_clients["Broken"].closed)

    async def test_discover_tools_uses_cached_inventory_without_forcing_refresh(self) -> None:
        memory = _FakeMemory()
        tool = MCPToolSpec(
            local_name="mcp_archive_search",
            remote_name="search",
            description="Search archive",
            parameters={"type": "object"},
        )
        created_clients: dict[str, _FakeClient] = {}

        def client_factory(server_settings: MCPServerSettings) -> _FakeClient:
            client = _FakeClient(server_settings, tools=[tool])
            created_clients[server_settings.name] = client
            return client

        manager = MCPRuntimeManager(
            memory,
            settings=[MCPServerSettings(name="Archive", command="python", args=[], env={})],
            client_factory=client_factory,
        )

        first = await manager.discover_tools()
        second = await manager.discover_tools()

        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(created_clients["Archive"].list_tools_calls, 1)

    async def test_force_refresh_reuses_cached_inventory_after_failure(self) -> None:
        memory = _FakeMemory()
        tool = MCPToolSpec(
            local_name="mcp_archive_search",
            remote_name="search",
            description="Search archive",
            parameters={"type": "object"},
        )
        created_clients: dict[str, _FakeClient] = {}

        def client_factory(server_settings: MCPServerSettings) -> _FakeClient:
            client = _FakeClient(server_settings, tools=[tool])
            created_clients[server_settings.name] = client
            return client

        manager = MCPRuntimeManager(
            memory,
            settings=[MCPServerSettings(name="Archive", command="python", args=[], env={})],
            client_factory=client_factory,
        )

        await manager.discover_tools()
        created_clients["Archive"]._failure = RuntimeError("boom")
        discovered = await manager.discover_tools(force_refresh=True)

        self.assertEqual(len(discovered), 1)
        self.assertEqual(discovered[0].tool.remote_name, "search")
        self.assertEqual(created_clients["Archive"].list_tools_calls, 2)
        self.assertTrue(created_clients["Archive"].closed)

    async def test_reload_replaces_clients_from_latest_config(self) -> None:
        memory = _FakeMemory()
        manager = MCPRuntimeManager(
            memory,
            settings=[MCPServerSettings(name="Archive", command="python", args=[], env={})],
            client_factory=_FakeClient,
        )

        original_client = manager.clients[0]
        replacement = MCPServerSettings(name="Remote", command="npx", args=["-y", "mcp-remote"], env={})

        with patch("core.mcp_runtime.config.get_mcp_server_configs", return_value=[replacement]):
            await manager.reload()

        self.assertTrue(original_client.closed)
        self.assertEqual([client.server_name for client in manager.clients], ["Remote"])
        self.assertEqual(memory.clients, manager.clients)


if __name__ == "__main__":
    unittest.main()