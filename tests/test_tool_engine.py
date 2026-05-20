from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import config
from core.mcp_runtime import MCPDiscoveredTool
from core.mcp_contracts import MCPToolResult, MCPToolSpec
from core.tool_engine import ToolEngine


class _FakeMemory:
    def __init__(self) -> None:
        self.clients = None

    def set_mcp_clients(self, clients: list[object]) -> None:
        self.clients = list(clients)


class ToolEngineSchemaTests(unittest.TestCase):
    def test_schema_filtering_respects_allowed_tags(self) -> None:
        engine = ToolEngine(_FakeMemory())
        engine.register(lambda text: text, name="universal_tool", tags=["universal"])
        engine.register(lambda text: text, name="coder_tool", tags=["coder"])

        schemas = engine.get_openai_tool_schemas(allowed_tags=["researcher"])
        names = [schema["function"]["name"] for schema in schemas]

        self.assertEqual(names, ["universal_tool"])

    def test_compact_provider_schema_flag_is_forwarded_to_registry(self) -> None:
        engine = ToolEngine(_FakeMemory())
        engine.register(
            lambda search_text: search_text,
            name="search_repository",
            description="Search the repository for matching files and symbols. Use this for repository lookups.",
        )

        compact_schema = engine.get_openai_tool_schemas(compact_for_provider=True)[0]

        self.assertNotIn(
            "description",
            compact_schema["function"]["parameters"]["properties"]["search_text"],
        )


class ToolEngineExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_execute_runs_sync_tool(self) -> None:
        engine = ToolEngine(_FakeMemory())

        def uppercase(text: str) -> str:
            return text.upper()

        engine.register(uppercase, name="uppercase")
        result = await engine.execute("uppercase", {"text": "zephyr"})

        self.assertEqual(result, "ZEPHYR")

    async def test_execute_runs_async_tool(self) -> None:
        engine = ToolEngine(_FakeMemory())

        async def greet(name: str) -> str:
            return f"hello {name}"

        engine.register(greet, name="greet")
        result = await engine.execute("greet", {"name": "runtime"})

        self.assertEqual(result, "hello runtime")

    async def test_execute_rejects_disallowed_tool(self) -> None:
        engine = ToolEngine(_FakeMemory())
        engine.register(lambda text: text, name="coder_tool", tags=["coder"])

        result = await engine.execute("coder_tool", {"text": "hidden"}, allowed_tags=["researcher"])

        self.assertEqual(result, "Error: tool 'coder_tool' is not allowed for this agent.")

    async def test_execute_respects_sensitive_denial(self) -> None:
        with patch.object(config, "REQUIRE_CONFIRMATION", True):
            engine = ToolEngine(_FakeMemory())
            engine.register(lambda: "should not run", name="danger", sensitive=True)

            result = await engine.execute("danger", {}, allow_sensitive_tools=False)

        self.assertEqual(result, "User denied execution of this tool.")

    async def test_execute_formats_tool_errors(self) -> None:
        engine = ToolEngine(_FakeMemory())

        def boom() -> str:
            raise ValueError("bad input")

        engine.register(boom, name="boom")
        result = await engine.execute("boom", {})

        self.assertEqual(result, "Tool 'boom' raised an error: ValueError: bad input")

    async def test_execute_reports_unknown_tools(self) -> None:
        engine = ToolEngine(_FakeMemory())

        result = await engine.execute("missing_tool", {})

        self.assertEqual(result, "Error: unknown tool 'missing_tool'.")

    async def test_execute_detailed_preserves_mcp_structured_result_metadata(self) -> None:
        engine = ToolEngine(_FakeMemory())

        async def mcp_tool() -> MCPToolResult:
            return MCPToolResult(
                tool_name="search",
                rendered_content="2 hits",
                structured_content={"hits": 2, "query": "runtime"},
            )

        engine.register(mcp_tool, name="mcp_search", source="mcp")

        result = await engine.execute_detailed("mcp_search", {})

        self.assertEqual(result.display_text, "2 hits")
        self.assertEqual(result.structured_content, {"hits": 2, "query": "runtime"})
        self.assertEqual(result.structured_content_type, "object")
        self.assertEqual(engine.get_recent_tool_executions(source="mcp", limit=1)[0].tool_name, "mcp_search")

    async def test_refresh_mcp_tools_replaces_stale_mcp_registrations(self) -> None:
        engine = ToolEngine(_FakeMemory())
        engine.register(lambda: "manual", name="manual_tool", source="manual")
        engine.register(lambda: "stale", name="mcp_old_tool", source="mcp")

        fake_client = SimpleNamespace(server_name="Archive", call_tool=AsyncMock(return_value="ok"))
        discovered = [
            MCPDiscoveredTool(
                client=fake_client,
                tool=MCPToolSpec(
                    local_name="mcp_archive_search",
                    remote_name="search",
                    description="Search archive",
                    parameters={"type": "object"},
                ),
            )
        ]
        engine._mcp_runtime.discover_tools = AsyncMock(return_value=discovered)  # type: ignore[method-assign]

        await engine.refresh_mcp_tools()

        names = engine.list_tool_names()
        self.assertIn("manual_tool", names)
        self.assertIn("mcp_archive_search", names)
        self.assertNotIn("mcp_old_tool", names)
        engine._mcp_runtime.discover_tools.assert_awaited_once_with(force_refresh=True)  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main()