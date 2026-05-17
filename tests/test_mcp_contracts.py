from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import config
from core.mcp_client import MCPStdioClient
from core.mcp_contracts import MCPErrorKind, MCPServerSettings, MCPServerState, MCPToolError, MCPToolResult


class MCPConfigTests(unittest.TestCase):
    def test_get_mcp_server_configs_returns_typed_settings(self) -> None:
        env = {
            "MCP_SERVERS_JSON": json.dumps(
                [
                    {
                        "name": "JSON Archive",
                        "command": "npx",
                        "args": ["-y", "archive-server"],
                        "env": {"TOKEN": "abc"},
                        "cwd": "relative-json",
                        "tool_prefix": "json-tools",
                        "connect_timeout_seconds": 3.5,
                        "discovery_timeout_seconds": 5.5,
                        "tool_timeout_seconds": 12,
                        "max_retries": 4,
                        "retry_backoff_seconds": 1.25,
                    }
                ]
            ),
            "MCP_SERVER_COMMAND": "python -m archive.single",
            "MCP_SERVER_NAME": "Single Archive",
            "MCP_SERVER_ARGS": "--transport stdio --verbose",
            "MCP_SERVER_ENV": "FOO=bar;BAZ=qux",
            "MCP_SERVER_CWD": "relative-single",
            "MCP_TOOL_PREFIX": "single-tools",
            "MCP_SERVER_CONNECT_TIMEOUT_SECONDS": "7",
            "MCP_SERVER_DISCOVERY_TIMEOUT_SECONDS": "11",
            "MCP_SERVER_TOOL_TIMEOUT_SECONDS": "17",
            "MCP_SERVER_MAX_RETRIES": "1",
            "MCP_SERVER_RETRY_BACKOFF_SECONDS": "0.75",
            "MCP_SERVER_2_COMMAND": "node indexed-server.js",
            "MCP_SERVER_2_NAME": "Indexed Archive",
            "MCP_SERVER_2_ARGS": json.dumps(["--stdio"]),
            "MCP_SERVER_2_ENV_JSON": json.dumps({"HELLO": "world"}),
            "MCP_SERVER_2_CWD": "relative-indexed",
            "MCP_SERVER_2_TOOL_PREFIX": "indexed-tools",
            "MCP_SERVER_2_CONNECT_TIMEOUT_SECONDS": "6",
            "MCP_SERVER_2_DISCOVERY_TIMEOUT_SECONDS": "9",
            "MCP_SERVER_2_TOOL_TIMEOUT_SECONDS": "14",
            "MCP_SERVER_2_MAX_RETRIES": "3",
            "MCP_SERVER_2_RETRY_BACKOFF_SECONDS": "0.2",
        }

        with patch.dict(os.environ, env, clear=True):
            configs = config.get_mcp_server_configs()

        self.assertEqual([cfg.name for cfg in configs], ["JSON Archive", "Single Archive", "Indexed Archive"])
        self.assertTrue(all(isinstance(cfg, MCPServerSettings) for cfg in configs))

        self.assertEqual(configs[0].args, ["-y", "archive-server"])
        self.assertEqual(configs[0].env, {"TOKEN": "abc"})
        self.assertEqual(configs[0].cwd, config.PROJECT_ROOT / "relative-json")
        self.assertEqual(configs[0].tool_prefix, "json-tools")
        self.assertEqual(configs[0].connect_timeout_seconds, 3.5)
        self.assertEqual(configs[0].discovery_timeout_seconds, 5.5)
        self.assertEqual(configs[0].tool_timeout_seconds, 12.0)
        self.assertEqual(configs[0].max_retries, 4)
        self.assertEqual(configs[0].retry_backoff_seconds, 1.25)

        self.assertEqual(configs[1].args, ["--transport", "stdio", "--verbose"])
        self.assertEqual(configs[1].env, {"FOO": "bar", "BAZ": "qux"})
        self.assertEqual(configs[1].cwd, config.PROJECT_ROOT / "relative-single")
        self.assertEqual(configs[1].connect_timeout_seconds, 7.0)
        self.assertEqual(configs[1].discovery_timeout_seconds, 11.0)
        self.assertEqual(configs[1].tool_timeout_seconds, 17.0)
        self.assertEqual(configs[1].max_retries, 1)
        self.assertEqual(configs[1].retry_backoff_seconds, 0.75)

        self.assertEqual(configs[2].args, ["--stdio"])
        self.assertEqual(configs[2].env, {"HELLO": "world"})
        self.assertEqual(configs[2].cwd, config.PROJECT_ROOT / "relative-indexed")
        self.assertEqual(configs[2].connect_timeout_seconds, 6.0)
        self.assertEqual(configs[2].discovery_timeout_seconds, 9.0)
        self.assertEqual(configs[2].tool_timeout_seconds, 14.0)
        self.assertEqual(configs[2].max_retries, 3)
        self.assertEqual(configs[2].retry_backoff_seconds, 0.2)

    def test_from_config_skips_blank_command(self) -> None:
        settings = MCPServerSettings.from_config({"name": "Broken", "command": "  "}, index=1, project_root=Path("E:/project"))
        self.assertIsNone(settings)


class MCPClientContractTests(unittest.TestCase):
    def test_qualify_tool_name_sanitizes_components(self) -> None:
        client = MCPStdioClient(
            MCPServerSettings(
                name="Archive Search",
                command="python",
                args=[],
                env={},
                tool_prefix="MCP Tools",
            )
        )

        self.assertEqual(client.qualify_tool_name("Search Facts!"), "mcp_tools_archive_search_search_facts")

    def test_render_result_prefers_text_and_json_blocks(self) -> None:
        class TextBlock:
            type = "text"
            text = "alpha"

        class JsonBlock:
            def model_dump(self, *, mode: str) -> dict[str, int]:
                self.last_mode = mode
                return {"beta": 2}

        rendered = MCPStdioClient._render_result(SimpleNamespace(content=[TextBlock(), JsonBlock()]))
        self.assertEqual(rendered, 'alpha\n{"beta": 2}')

    def test_render_result_falls_back_to_structured_content(self) -> None:
        rendered = MCPStdioClient._render_result(
            SimpleNamespace(content=[], structuredContent={"ok": True})
        )
        self.assertEqual(rendered, '{"ok": true}')


class MCPClientInvocationTests(unittest.IsolatedAsyncioTestCase):
    async def test_invoke_tool_returns_typed_result(self) -> None:
        client = MCPStdioClient(
            MCPServerSettings(
                name="Archive",
                command="python",
                args=[],
                env={},
            )
        )

        class SuccessQueue:
            async def put(self, command: object) -> None:
                assert isinstance(command, object)
                command.future.set_result(
                    MCPToolResult(
                        tool_name="search",
                        rendered_content="payload",
                        structured_content={"hits": 1},
                    )
                )

        client._worker_queue = SuccessQueue()  # type: ignore[assignment]
        client._ensure_worker = AsyncMock()  # type: ignore[method-assign]

        result = await client.invoke_tool("search", {"query": "runtime"})

        self.assertEqual(result.tool_name, "search")
        self.assertEqual(result.rendered_content, "payload")
        self.assertEqual(result.structured_content, {"hits": 1})
        self.assertEqual(result.display_text, "payload")

    async def test_invoke_tool_wraps_failures_as_typed_errors(self) -> None:
        client = MCPStdioClient(
            MCPServerSettings(
                name="Archive",
                command="python",
                args=[],
                env={},
            )
        )

        class FailureQueue:
            async def put(self, command: object) -> None:
                assert isinstance(command, object)
                command.future.set_exception(RuntimeError("boom"))

        client._worker_queue = FailureQueue()  # type: ignore[assignment]
        client._ensure_worker = AsyncMock()  # type: ignore[method-assign]

        with self.assertRaises(MCPToolError) as caught:
            await client.invoke_tool("search", {"query": "runtime"})

        self.assertEqual(caught.exception.kind, MCPErrorKind.EXECUTION)
        self.assertEqual(caught.exception.server_name, "Archive")
        self.assertEqual(caught.exception.tool_name, "search")

        status = client.get_status()
        self.assertEqual(status.state, MCPServerState.ERROR)
        self.assertEqual(status.last_error_kind, MCPErrorKind.EXECUTION)
        self.assertEqual(status.last_error_tool_name, "search")
        self.assertEqual(status.degraded_reason, "Most recent MCP tool execution failed: search.")

    async def test_list_tools_wraps_discovery_failures_with_typed_status_metadata(self) -> None:
        client = MCPStdioClient(
            MCPServerSettings(
                name="Archive",
                command="python",
                args=[],
                env={},
            )
        )

        with patch.object(client, "_open_session", side_effect=RuntimeError("offline")):
            with self.assertRaises(MCPToolError) as caught:
                await client.list_tools()

        self.assertEqual(caught.exception.kind, MCPErrorKind.CONNECTION)
        status = client.get_status()
        self.assertEqual(status.state, MCPServerState.ERROR)
        self.assertEqual(status.last_error_kind, MCPErrorKind.CONNECTION)
        self.assertIsNone(status.last_error_tool_name)
        self.assertIsNone(status.last_discovered_at)
        self.assertEqual(status.degraded_reason, "Most recent MCP connection attempt failed.")

    async def test_list_tools_retries_transient_connection_failures(self) -> None:
        client = MCPStdioClient(
            MCPServerSettings(
                name="Archive",
                command="python",
                args=[],
                env={},
                max_retries=1,
                retry_backoff_seconds=0.0,
            )
        )
        attempts = 0

        @asynccontextmanager
        async def flaky_session(*_args: object, **_kwargs: object):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ConnectionError("offline")

            class Session:
                async def list_tools(self) -> object:
                    tool = SimpleNamespace(name="search", description="Search", inputSchema={"type": "object"})
                    return SimpleNamespace(tools=[tool])

            yield Session()

        with patch.object(client, "_open_session", flaky_session):
            tools = await client.list_tools()

        self.assertEqual(attempts, 2)
        self.assertEqual([tool.remote_name for tool in tools], ["search"])
        self.assertIsNone(client.get_status().last_error)

    async def test_list_tools_records_discovery_and_connection_timestamps(self) -> None:
        client = MCPStdioClient(
            MCPServerSettings(
                name="Archive",
                command="python",
                args=[],
                env={},
            )
        )

        @asynccontextmanager
        async def fake_session(*_args: object, **_kwargs: object) -> object:
            class Session:
                async def list_tools(self) -> object:
                    tool = SimpleNamespace(name="search", description="Search", inputSchema={"type": "object"})
                    return SimpleNamespace(tools=[tool])

            yield Session()

        with patch.object(client, "_open_session", fake_session):
            tools = await client.list_tools()

        status = client.get_status()
        self.assertEqual([tool.remote_name for tool in tools], ["search"])
        self.assertIsNotNone(status.last_discovered_at)
        self.assertIsNotNone(status.last_successful_connection_at)
        self.assertEqual(status.degraded_reason, None)

    async def test_invoke_tool_retries_transient_connection_failures(self) -> None:
        client = MCPStdioClient(
            MCPServerSettings(
                name="Archive",
                command="python",
                args=[],
                env={},
                max_retries=1,
                retry_backoff_seconds=0.0,
            )
        )
        connection_error = MCPToolError(
            kind=MCPErrorKind.CONNECTION,
            server_name="Archive",
            message="offline",
        )

        class SuccessQueue:
            async def put(self, command: object) -> None:
                assert isinstance(command, object)
                command.future.set_result(
                    MCPToolResult(
                        tool_name="search",
                        rendered_content="payload",
                        structured_content={"hits": 1},
                    )
                )

        async def ensure_worker() -> None:
            if not hasattr(ensure_worker, "calls"):
                ensure_worker.calls = 0  # type: ignore[attr-defined]
            ensure_worker.calls += 1  # type: ignore[attr-defined]
            if ensure_worker.calls == 1:  # type: ignore[attr-defined]
                raise connection_error
            client._worker_queue = SuccessQueue()  # type: ignore[assignment]

        client._ensure_worker = AsyncMock(side_effect=ensure_worker)  # type: ignore[method-assign]

        result = await client.invoke_tool("search", {"query": "runtime"})

        self.assertEqual(result.display_text, "payload")
        self.assertEqual(client._ensure_worker.await_count, 2)
        self.assertIsNone(client.get_status().last_error)


if __name__ == "__main__":
    unittest.main()