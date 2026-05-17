"""Runtime-backed assembly helpers for command-center status surfaces."""

from __future__ import annotations

from backend.schemas.command_center import (
    MCPOverviewResponse,
    MCPServerStatusResponse,
    MCPToolExecutionResponse,
    ToolCatalogEntryResponse,
)
import config


class CommandCenterRuntimeService:
    """Build tool catalog and MCP status payloads from the active runtime."""

    _SOURCE_ORDER = {"local": 0, "builtin": 1, "mcp": 2, "manual": 3}

    def build_tool_entries(self, tool_engine: object | None) -> list[ToolCatalogEntryResponse]:
        if tool_engine is None:
            return []

        tools = sorted(
            tool_engine.list_tools(),
            key=lambda tool: (self._SOURCE_ORDER.get(tool.source, 99), tool.source, tool.name.lower()),
        )
        return [
            ToolCatalogEntryResponse(
                name=tool.name,
                description=tool.description,
                source=tool.source,
                source_label=self._source_label(tool.source),
                tags=list(tool.tags),
            )
            for tool in tools
        ]

    def build_mcp_overview(self, tool_engine: object | None) -> MCPOverviewResponse:
        configured = bool(config.get_mcp_server_configs())

        if tool_engine is None:
            return MCPOverviewResponse(
                enabled=config.MCP_ENABLED,
                external_integrations_enabled=config.EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED,
                configured=configured,
                message="Runtime is not initialized yet. Send a chat turn, reload tools, or prepare the runtime to inspect MCP servers.",
            )

        statuses = tool_engine.get_mcp_server_statuses()
        if not statuses:
            return MCPOverviewResponse(
                enabled=config.MCP_ENABLED,
                external_integrations_enabled=config.EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED,
                configured=configured,
                message=self._empty_mcp_message(),
            )

        return MCPOverviewResponse(
            enabled=config.MCP_ENABLED,
            external_integrations_enabled=config.EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED,
            configured=True,
            message=self._configured_mcp_message(statuses),
            servers=[
                MCPServerStatusResponse(
                    name=status.name,
                    tool_prefix=status.tool_prefix,
                    command=status.command,
                    args=list(status.args),
                    connected=status.connected,
                    discovered_tools=list(status.discovered_tools),
                    state=status.state,
                    last_error=status.last_error,
                    last_discovered_at=status.last_discovered_at,
                    last_successful_connection_at=status.last_successful_connection_at,
                    last_error_kind=status.last_error_kind,
                    last_error_tool_name=status.last_error_tool_name,
                    degraded_reason=status.degraded_reason,
                )
                for status in statuses
            ],
            recent_executions=self._build_recent_mcp_executions(tool_engine),
        )

    @staticmethod
    def _configured_mcp_message(statuses: list[object]) -> str:
        count = len(statuses)
        if any(getattr(status, "last_error", None) and getattr(status, "last_discovered_at", None) for status in statuses):
            return (
                f"{count} MCP server(s) configured. Showing cached inventory from the last successful discovery "
                "refresh for servers with current errors."
            )
        if any(getattr(status, "last_discovered_at", None) for status in statuses):
            return f"{count} MCP server(s) configured. Tool inventory reflects the last successful discovery refresh."
        return f"{count} MCP server(s) configured. Tool inventory has not been refreshed yet."

    @staticmethod
    def _empty_mcp_message() -> str:
        if not config.MCP_ENABLED:
            return "MCP is disabled. Set MCP_ENABLED=true and configure MCP_SERVERS to enable server tools."
        if not config.EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED:
            return (
                "MCP server tools are disabled because external subprocess integrations are off. "
                "Re-enable EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED=true after confirming the required tools are installed."
            )
        return "No MCP servers are configured. Set MCP_ENABLED=true and MCP_SERVERS in the environment."

    @staticmethod
    def _build_recent_mcp_executions(tool_engine: object) -> list[MCPToolExecutionResponse]:
        getter = getattr(tool_engine, "get_recent_tool_executions", None)
        if not callable(getter):
            return []

        recent = getter(source="mcp", limit=4)
        return [
            MCPToolExecutionResponse(
                tool_name=execution.tool_name,
                executed_at=execution.executed_at,
                display_text=execution.display_text,
                structured_content=execution.structured_content,
                structured_content_type=execution.structured_content_type,
                structured_content_preview=execution.structured_content_preview(),
                is_error=execution.is_error,
                error_type=execution.error_type,
            )
            for execution in recent
        ]

    @staticmethod
    def _source_label(source: str) -> str:
        labels = {
            "builtin": "Built-in",
            "local": "Skill",
            "manual": "Manual",
            "mcp": "MCP",
        }
        return labels.get(source, source.replace("_", " ").title())