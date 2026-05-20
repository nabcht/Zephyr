"""Tool engine — registry, schema generation, and MCP-backed tool loading."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from rich.console import Console

from core.mcp_client import MCPStdioClient
from core.mcp_contracts import MCPServerStatus, MCPToolError, MCPToolResult
from core.mcp_runtime import MCPRuntimeManager
from core.tool_executor import ToolExecutionResult, ToolExecutor
from core.tool_registry import ToolDef, ToolRegistry

if TYPE_CHECKING:
    from core.memory import MemoryManager
    from skills.skill_loader import SkillLoader

log = logging.getLogger("zephyr.tool_engine")


class ToolEngine:
    """Central registry for callable tools used by the LLM runtime."""

    def __init__(self, memory: MemoryManager) -> None:
        self.memory = memory
        self._registry = ToolRegistry()
        self._mcp_runtime = MCPRuntimeManager(memory)
        self._executor = ToolExecutor()
        self._recent_executions: list[ToolExecutionResult] = []
        self.skill_loader: SkillLoader | None = None

    def register(
        self,
        fn: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
        sensitive: bool = False,
        tags: list[str] | None = None,
        parameters: dict[str, Any] | None = None,
        source: str = "manual",
    ) -> None:
        self._registry.register(
            fn=fn,
            name=name,
            description=description,
            sensitive=sensitive,
            tags=tags,
            parameters=parameters,
            source=source,
        )

    def unregister(self, name: str) -> None:
        self._registry.unregister(name)

    def list_tool_names(self) -> list[str]:
        return self._registry.list_tool_names()

    def list_tools(self) -> list[ToolDef]:
        return self._registry.list_tools()

    def get_mcp_server_statuses(self) -> list[MCPServerStatus]:
        """Return runtime status for configured MCP servers."""
        return self._mcp_runtime.get_server_statuses()

    async def aclose(self) -> None:
        """Release external resources owned by the tool engine."""
        await self._mcp_runtime.aclose()

    def get_openai_tool_schemas(
        self,
        allowed_tags: list[str] | None = None,
        *,
        compact_for_provider: bool = False,
    ) -> list[dict[str, Any]]:
        return self._registry.get_openai_tool_schemas(
            allowed_tags=allowed_tags,
            compact_for_provider=compact_for_provider,
        )

    async def execute(
        self,
        name: str,
        args: dict[str, Any],
        *,
        allowed_tags: list[str] | None = None,
        console: Console | None = None,
        allow_sensitive_tools: bool | None = None,
    ) -> str:
        """Execute a registered tool and normalize the result to a string."""
        result = await self.execute_detailed(
            name,
            args,
            allowed_tags=allowed_tags,
            console=console,
            allow_sensitive_tools=allow_sensitive_tools,
        )
        return result.display_text

    async def execute_detailed(
        self,
        name: str,
        args: dict[str, Any],
        *,
        allowed_tags: list[str] | None = None,
        console: Console | None = None,
        allow_sensitive_tools: bool | None = None,
    ) -> ToolExecutionResult:
        """Execute a registered tool and retain structured execution metadata."""
        tool_def = self._registry.get(name)
        result = await self._executor.execute_detailed(
            tool_def,
            {**args, **({"__tool_name__": name} if tool_def is None else {})},
            allowed_tags=allowed_tags,
            console=console,
            allow_sensitive_tools=allow_sensitive_tools,
        )
        self._remember_execution(result)
        return result

    def get_recent_tool_executions(
        self,
        *,
        source: str | None = None,
        limit: int | None = None,
    ) -> list[ToolExecutionResult]:
        executions = self._recent_executions
        if source is not None:
            executions = [execution for execution in executions if execution.source == source]
        if limit is not None:
            executions = executions[:limit]
        return list(executions)

    async def load_all_skills(self) -> None:
        """Register built-in tools, then discover dynamic skills from the skills directory."""
        self._registry.remove_by_source({"builtin", "local", "mcp"})
        await self.aclose()
        self._register_memory_tools()

        from skills.skill_loader import SkillLoader

        if self.skill_loader is None:
            self.skill_loader = SkillLoader(self)

        await self.skill_loader.load()
        await self._register_mcp_tools(force_refresh=True)

    async def refresh_mcp_tools(self) -> None:
        """Re-discover MCP tools without reloading local skills or search state."""
        self._registry.remove_by_source({"mcp"})
        await self._register_mcp_tools(force_refresh=True)

    async def reload_mcp_runtime(self) -> None:
        """Rebuild MCP clients from current config and refresh registered MCP tools."""
        self._registry.remove_by_source({"mcp"})
        self._recent_executions = [execution for execution in self._recent_executions if execution.source != "mcp"]
        await self._mcp_runtime.reload()
        await self._register_mcp_tools(force_refresh=True)

    async def _register_mcp_tools(self, *, force_refresh: bool = False) -> None:
        for discovered in await self._mcp_runtime.discover_tools(force_refresh=force_refresh):
            mcp_client = discovered.client
            remote_tool = discovered.tool
            existing = self._registry.get(remote_tool.local_name)
            if existing is not None:
                log.warning(
                    "Skipping MCP tool '%s' from '%s' because '%s' is already registered from source '%s'.",
                    remote_tool.remote_name,
                    mcp_client.server_name,
                    remote_tool.local_name,
                    existing.source,
                )
                continue

            self.register(
                self._make_mcp_runner(mcp_client, remote_tool.remote_name),
                name=remote_tool.local_name,
                description=remote_tool.description,
                tags=self._mcp_tags_for_tool(mcp_client, remote_tool.local_name),
                parameters=remote_tool.parameters,
                source="mcp",
            )

    def _make_mcp_runner(self, mcp_client: MCPStdioClient, remote_name: str) -> Callable[..., Any]:
        async def runner(**kwargs: Any) -> MCPToolResult:
            try:
                return await mcp_client.invoke_tool(remote_name, kwargs)
            except MCPToolError as exc:
                if self._is_archive_mcp_tool(mcp_client, remote_name):
                    log.warning(
                        "Archive MCP tool '%s' on server '%s' is unavailable (%s): %s",
                        remote_name,
                        mcp_client.server_name,
                        exc.kind,
                        exc,
                    )
                    return MCPToolResult(
                        tool_name=remote_name,
                        rendered_content=f"Archive tool '{remote_name}' is temporarily unavailable: {exc}",
                        structured_content={
                            "server_name": mcp_client.server_name,
                            "error_kind": str(exc.kind),
                            "remote_name": remote_name,
                        },
                        is_error=True,
                    )
                raise
            except Exception:
                raise

        return runner

    def _remember_execution(self, result: ToolExecutionResult) -> None:
        self._recent_executions.insert(0, result)
        del self._recent_executions[12:]

    @staticmethod
    def _is_archive_mcp_tool(mcp_client: MCPStdioClient, tool_name: str) -> bool:
        server_name = mcp_client.server_name.lower()
        lowered_tool_name = tool_name.lower()
        return server_name == "archive" or server_name.startswith("archive-") or lowered_tool_name.startswith("mcp_archive_")

    def _mcp_tags_for_tool(self, mcp_client: MCPStdioClient, local_tool_name: str) -> list[str]:
        if self._is_archive_mcp_tool(mcp_client, local_tool_name):
            return ["archive-direct"]
        return ["universal"]

    def _register_memory_tools(self) -> None:
        self.register(
            self.memory.memory_durable_fact,
            name="memory_durable_fact",
            description=(
                "Save a durable fact about the user or a learned insight to long-term memory. "
                "Use this when you learn something worth remembering across sessions."
            ),
            tags=["universal"],
            source="builtin",
        )
        self.register(
            self.memory.memory_force_delete_durable_fact,
            name="memory_force_delete_durable_fact",
            description=(
                "Delete a specific durable fact from long-term memory by its exact text. "
                "Use when a fact is outdated or incorrect."
            ),
            sensitive=True,
            tags=["supervisor", "general"],
            source="builtin",
        )

        from skills.skill_writer import write_skill

        self.register(
            write_skill,
            name="write_skill",
            description=(
                "Create a new Python skill package following the agentskills.io standard. "
                "Args: skill_name (str) — name of the new skill (e.g. 'weather_lookup'); "
                "code (str) — full Python source with at least one public async function; "
                "description (str, optional) — short one-line description of what the skill does. "
                "The skill is saved as a directory package and activated with /reload."
            ),
            sensitive=True,
            tags=["coder"],
            source="builtin",
        )
