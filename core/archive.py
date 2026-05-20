"""Claude-Mem archive bridge used by hybrid memory retrieval and sync."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Sequence

import httpx

import config
from core.mcp_client import MCPStdioClient
from core.mcp_contracts import MCPToolError

log = logging.getLogger("zephyr.archive")

_SEARCH_TOOL_CANDIDATES: tuple[str, ...] = (
    "search",
    "archive_search",
    "mcp_archive_search",
)
_DETAIL_TOOL_CANDIDATES: tuple[str, ...] = (
    "get_observations",
    "archive_get_observations",
    "mcp_archive_get_observations",
)
_WRITE_TOOL_CANDIDATES: tuple[str, ...] = (
    "add_observation",
    "archive_add_observation",
    "mcp_archive_add_observation",
    "create_observation",
    "record_observation",
    "save_observation",
)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z]+", "-", value).strip("-").lower()
    return slug or "zephyr"


def _summarize_title(text: str, limit: int = 96) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


class ArchiveBridge:
    """Thin bridge to Claude-Mem for archive search and durable-fact imports."""

    def __init__(
        self,
        *,
        project_name: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._project_name = project_name or config.PROJECT_ROOT.name
        self._project_slug = _slugify(self._project_name)
        self._mcp_clients: list[MCPStdioClient] = []
        self._http_client = http_client or httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=2.0))
        self._owns_http_client = http_client is None
        self._memory_session_id = f"zephyr-{self._project_slug}-archive"
        self._content_session_id = f"zephyr-{self._project_slug}-archive-content"

    @property
    def project_name(self) -> str:
        return self._project_name

    def set_mcp_clients(self, clients: Sequence[MCPStdioClient]) -> None:
        self._mcp_clients = list(clients)

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self._http_client.aclose()

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        match = await self._find_tool(
            exact_names=_SEARCH_TOOL_CANDIDATES,
            required_tokens=(("search",),),
        )
        if match is None:
            return []

        client, tool_name = match
        payload: dict[str, Any] = {
            "query": query,
            "limit": limit,
            "type": "observations",
        }
        selected_project = project or self._project_name
        if selected_project:
            payload["project"] = selected_project

        try:
            rendered = await client.call_tool(tool_name, payload)
        except MCPToolError as exc:
            log.warning("Archive search failed via %s (%s): %s", tool_name, exc.kind, exc)
            return []
        except Exception as exc:
            log.warning("Archive search failed via %s: %s", tool_name, exc)
            return []
        return self._parse_search_payload(rendered)

    async def get_observations(
        self,
        ids: Sequence[int],
        *,
        limit: int | None = None,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        match = await self._find_tool(
            exact_names=_DETAIL_TOOL_CANDIDATES,
            required_tokens=(("get", "observation"),),
        )
        if match is None:
            return []

        client, tool_name = match
        payload: dict[str, Any] = {"ids": list(ids)}
        if limit is not None:
            payload["limit"] = limit
        selected_project = project or self._project_name
        if selected_project:
            payload["project"] = selected_project

        try:
            rendered = await client.call_tool(tool_name, payload)
        except MCPToolError as exc:
            log.warning("Archive observation lookup failed via %s (%s): %s", tool_name, exc.kind, exc)
            return []
        except Exception as exc:
            log.warning("Archive observation lookup failed via %s: %s", tool_name, exc)
            return []
        parsed = self._parse_json_payload(rendered)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            observations = parsed.get("observations")
            if isinstance(observations, list):
                return [item for item in observations if isinstance(item, dict)]
        return []

    async def add_observation(self, text: str) -> bool:
        """Persist a durable fact to Claude-Mem.

        The installed Claude-Mem MCP server on this machine only exposes read-side
        tools, so this method first tries a write-capable MCP tool if one exists
        and otherwise falls back to the worker's supported `/api/import` route.
        """
        title = _summarize_title(text)

        write_match = await self._find_tool(
            exact_names=_WRITE_TOOL_CANDIDATES,
            required_tokens=(("observation", "add"), ("observation", "create"), ("observation", "record")),
        )
        if write_match is not None:
            client, tool_name = write_match
            candidate_payloads = [
                {"text": text},
                {"title": title, "text": text},
                {"title": title, "narrative": text, "facts": [text]},
            ]
            for payload in candidate_payloads:
                try:
                    await client.call_tool(tool_name, payload)
                    return True
                except MCPToolError as exc:
                    log.debug("Archive MCP write payload rejected by %s (%s): %s", tool_name, exc.kind, exc)
                except Exception as exc:
                    log.debug("Archive MCP write payload rejected by %s: %s", tool_name, exc)

        await self._import_observation(text=text, title=title)
        return True

    async def _import_observation(self, *, text: str, title: str) -> None:
        now = datetime.now(timezone.utc)
        created_at = now.isoformat().replace("+00:00", "Z")
        created_at_epoch = int(now.timestamp() * 1000)

        payload = {
            "sessions": [
                {
                    "content_session_id": self._content_session_id,
                    "memory_session_id": self._memory_session_id,
                    "project": self._project_name,
                    "platform_source": "zephyr",
                    "user_prompt": "Imported durable facts from Zephyr.",
                    "started_at": created_at,
                    "started_at_epoch": created_at_epoch,
                    "completed_at": created_at,
                    "completed_at_epoch": created_at_epoch,
                    "status": "completed",
                }
            ],
            "observations": [
                {
                    "memory_session_id": self._memory_session_id,
                    "project": self._project_name,
                    "text": text,
                    "type": "discovery",
                    "title": title,
                    "subtitle": "Imported from Zephyr durable memory",
                    "facts": json.dumps([text], ensure_ascii=False),
                    "narrative": text,
                    "concepts": json.dumps(["zephyr", "durable-memory"], ensure_ascii=False),
                    "files_read": json.dumps([], ensure_ascii=False),
                    "files_modified": json.dumps([], ensure_ascii=False),
                    "prompt_number": 0,
                    "discovery_tokens": 0,
                    "agent_type": "zephyr",
                    "agent_id": "memory_durable_fact",
                    "created_at": created_at,
                    "created_at_epoch": created_at_epoch,
                }
            ],
        }

        try:
            response = await self._http_client.post(self._worker_url("/api/import"), json=payload)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            log.warning(
                "Claude-Mem worker is unavailable at %s: %s",
                self._worker_url(""),
                exc,
            )
        except Exception as exc:
            log.warning("Archive import failed: %s", exc)

    def _worker_url(self, path: str) -> str:
        return f"http://{config.CLAUDE_MEM_WORKER_HOST}:{config.CLAUDE_MEM_WORKER_PORT}{path}"

    async def _find_tool(
        self,
        *,
        exact_names: Sequence[str],
        required_tokens: Sequence[tuple[str, ...]] = (),
    ) -> tuple[MCPStdioClient, str] | None:
        for client in self._ranked_clients():
            remote_tools = await self._get_remote_tool_names(client)
            for exact_name in exact_names:
                if exact_name in remote_tools:
                    return client, exact_name

            for remote_name in remote_tools:
                lowered = remote_name.lower()
                if any(all(token in lowered for token in token_group) for token_group in required_tokens):
                    return client, remote_name
        return None

    async def _get_remote_tool_names(self, client: MCPStdioClient) -> list[str]:
        remote_tools = list(getattr(client, "discovered_remote_tools", []))
        if remote_tools:
            return remote_tools

        try:
            specs = await client.list_tools()
        except Exception as exc:
            log.debug("Archive tool discovery failed for %s: %s", getattr(client, "server_name", "unknown"), exc)
            return []
        return [spec.remote_name for spec in specs]

    def _ranked_clients(self) -> list[MCPStdioClient]:
        def rank(client: MCPStdioClient) -> tuple[int, str]:
            server_name = getattr(client, "server_name", "").lower()
            if server_name == "archive":
                return (0, server_name)
            if "archive" in server_name:
                return (1, server_name)
            if "claude" in server_name or "mem" in server_name:
                return (2, server_name)
            return (3, server_name)

        return sorted(self._mcp_clients, key=rank)

    @staticmethod
    def _parse_json_payload(raw: str) -> Any:
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return None

    def _parse_search_payload(self, raw: str) -> list[dict[str, Any]]:
        parsed = self._parse_json_payload(raw)
        if isinstance(parsed, dict):
            content = parsed.get("content")
            if isinstance(content, list):
                text_blocks = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_blocks.append(str(block.get("text", "")))
                if text_blocks:
                    return self._parse_search_table("\n".join(text_blocks))

            results = parsed.get("results")
            if isinstance(results, dict):
                observations = results.get("observations")
                if isinstance(observations, list):
                    return [
                        {
                            "id": item.get("id"),
                            "title": item.get("title") or "Untitled",
                            "text": item.get("narrative") or item.get("text") or item.get("title") or "",
                            "raw": item,
                        }
                        for item in observations
                        if isinstance(item, dict)
                    ]

        return self._parse_search_table(raw)

    @staticmethod
    def _parse_search_table(raw: str) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|"):
                continue

            columns = [column.strip() for column in stripped.strip("|").split("|")]
            if len(columns) < 4:
                continue

            raw_id = columns[0].lstrip("#")
            if not raw_id.isdigit():
                continue

            title = columns[3] if len(columns) > 3 else f"Observation #{raw_id}"
            hits.append(
                {
                    "id": int(raw_id),
                    "title": title,
                    "text": title,
                    "raw": {"line": stripped},
                }
            )
        return hits