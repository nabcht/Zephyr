"""Lifecycle and discovery helpers for configured MCP servers."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Callable, Sequence

import config
from core.mcp_client import MCPStdioClient
from core.mcp_contracts import MCPServerSettings, MCPServerStatus, MCPToolSpec

if TYPE_CHECKING:
    from core.memory import MemoryManager

log = logging.getLogger("zephyr.mcp_runtime")


@dataclass(slots=True)
class MCPDiscoveredTool:
    """A discovered remote MCP tool paired with its owning client."""

    client: MCPStdioClient
    tool: MCPToolSpec


class MCPRuntimeManager:
    """Own configured MCP client lifecycle outside the tool registry."""

    def __init__(
        self,
        memory: MemoryManager,
        *,
        settings: Sequence[MCPServerSettings] | None = None,
        client_factory: Callable[[MCPServerSettings], MCPStdioClient] = MCPStdioClient,
    ) -> None:
        self._memory = memory
        self._client_factory = client_factory
        resolved_settings = list(settings) if settings is not None else config.get_mcp_server_configs()
        self._clients = [client_factory(server_settings) for server_settings in resolved_settings]
        self._cached_tool_inventory: dict[str, list[MCPToolSpec]] = {}

        set_mcp_clients = getattr(self._memory, "set_mcp_clients", None)
        if callable(set_mcp_clients):
            set_mcp_clients(self._clients)

    @property
    def clients(self) -> list[MCPStdioClient]:
        return list(self._clients)

    def get_server_statuses(self) -> list[MCPServerStatus]:
        """Return runtime status for configured MCP servers."""
        return [client.get_status() for client in self._clients]

    async def aclose(self) -> None:
        """Close all managed MCP clients."""
        for client in self._clients:
            await client.close()

    async def reload(self, *, settings: Sequence[MCPServerSettings] | None = None) -> None:
        """Rebuild managed MCP clients from the latest configuration."""
        await self.aclose()

        resolved_settings = list(settings) if settings is not None else config.get_mcp_server_configs()
        self._clients = [self._client_factory(server_settings) for server_settings in resolved_settings]
        self._cached_tool_inventory = {}

        set_mcp_clients = getattr(self._memory, "set_mcp_clients", None)
        if callable(set_mcp_clients):
            set_mcp_clients(self._clients)

    async def discover_tools(self, *, force_refresh: bool = False) -> list[MCPDiscoveredTool]:
        """Discover tools across all enabled MCP clients using cached inventory when available."""
        discovered: list[MCPDiscoveredTool] = []

        for client in self._clients:
            if not client.enabled:
                continue

            server_name = client.server_name
            has_cached_inventory = server_name in self._cached_tool_inventory

            if not force_refresh and has_cached_inventory:
                tools = list(self._cached_tool_inventory[server_name])
            else:
                try:
                    tools = await client.list_tools()
                except Exception as exc:
                    log.warning("MCP discovery skipped for '%s': %s", server_name, exc)
                    await client.close()
                    if not has_cached_inventory:
                        continue
                    log.info("Using cached MCP inventory for '%s' after refresh failure.", server_name)
                    tools = list(self._cached_tool_inventory[server_name])
                else:
                    self._cached_tool_inventory[server_name] = list(tools)

            for tool in tools:
                discovered.append(MCPDiscoveredTool(client=client, tool=tool))

        return discovered