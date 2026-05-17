"""Typed MCP contracts and config normalization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from pathlib import Path
import re
import shlex
from typing import Any, Mapping


@dataclass(slots=True)
class MCPServerSettings:
    """Connection settings for a single stdio MCP server."""

    name: str
    command: str
    args: list[str]
    env: dict[str, str]
    cwd: Path | None = None
    tool_prefix: str = "mcp"
    connect_timeout_seconds: float = 10.0
    discovery_timeout_seconds: float = 15.0
    tool_timeout_seconds: float = 30.0
    max_retries: int = 2
    retry_backoff_seconds: float = 0.5

    @classmethod
    def from_config(cls, raw: Mapping[str, Any], *, index: int, project_root: Path) -> MCPServerSettings | None:
        """Normalize a loose environment-derived server config."""
        command = str(raw.get("command", "")).strip()
        if not command:
            return None

        name = str(raw.get("name") or f"server-{index}").strip() or f"server-{index}"
        tool_prefix = str(raw.get("tool_prefix") or raw.get("prefix") or "mcp").strip() or "mcp"
        return cls(
            name=name,
            command=command,
            args=parse_mcp_arg_list(raw.get("args", [])),
            env=parse_mcp_env_mapping(raw.get("env", {})),
            cwd=resolve_mcp_cwd(raw.get("cwd"), project_root=project_root),
            tool_prefix=tool_prefix,
            connect_timeout_seconds=_coerce_float(
                raw.get("connect_timeout_seconds", raw.get("connect_timeout")),
                default=10.0,
                minimum=0.1,
            ),
            discovery_timeout_seconds=_coerce_float(
                raw.get("discovery_timeout_seconds", raw.get("discovery_timeout")),
                default=15.0,
                minimum=0.1,
            ),
            tool_timeout_seconds=_coerce_float(
                raw.get("tool_timeout_seconds", raw.get("tool_timeout")),
                default=30.0,
                minimum=0.1,
            ),
            max_retries=_coerce_int(
                raw.get("max_retries", raw.get("retry_attempts")),
                default=2,
                minimum=0,
            ),
            retry_backoff_seconds=_coerce_float(
                raw.get("retry_backoff_seconds", raw.get("retry_backoff")),
                default=0.5,
                minimum=0.0,
            ),
        )


@dataclass(slots=True)
class MCPToolSpec:
    """Normalized MCP tool metadata used by the local tool registry."""

    local_name: str
    remote_name: str
    description: str
    parameters: dict[str, Any]


@dataclass(slots=True)
class MCPServerStatus:
    """Runtime status summary for an MCP server connection."""

    name: str
    tool_prefix: str
    command: str
    args: list[str]
    connected: bool
    discovered_tools: list[str]
    last_error: str | None = None
    last_discovered_at: str | None = None
    last_successful_connection_at: str | None = None
    state: MCPServerState | None = None
    last_error_kind: MCPErrorKind | None = None
    last_error_tool_name: str | None = None
    degraded_reason: str | None = None

    def __post_init__(self) -> None:
        if self.state is None:
            self.state = self.derive_state()
        if self.degraded_reason is None:
            self.degraded_reason = self.derive_degraded_reason()

    def derive_state(self) -> MCPServerState:
        if self.last_error:
            return MCPServerState.ERROR
        if self.connected:
            return MCPServerState.CONNECTED
        return MCPServerState.READY

    def derive_degraded_reason(self) -> str | None:
        if self.last_error_kind == MCPErrorKind.CONFIGURATION:
            return "Server configuration is incomplete."
        if self.last_error_kind == MCPErrorKind.DEPENDENCY:
            return "Required MCP dependencies are unavailable."
        if self.last_error_kind == MCPErrorKind.CONNECTION:
            return "Most recent MCP connection attempt failed."
        if self.last_error_kind == MCPErrorKind.EXECUTION:
            if self.last_error_tool_name:
                return f"Most recent MCP tool execution failed: {self.last_error_tool_name}."
            return "Most recent MCP tool execution failed."
        if self.last_error_kind == MCPErrorKind.REMOTE:
            if self.last_error_tool_name:
                return f"Remote MCP server reported an error for tool: {self.last_error_tool_name}."
            return "Remote MCP server reported an error."
        if not self.last_discovered_at and not self.discovered_tools:
            return "Tool discovery has not completed yet."
        return None


class MCPServerState(StrEnum):
    """Normalized operator-facing MCP server states."""

    READY = "ready"
    CONNECTED = "connected"
    ERROR = "error"


class MCPErrorKind(StrEnum):
    """Normalized MCP failure categories used across runtime boundaries."""

    CONFIGURATION = "configuration"
    DEPENDENCY = "dependency"
    CONNECTION = "connection"
    EXECUTION = "execution"
    REMOTE = "remote"


@dataclass(slots=True)
class MCPToolResult:
    """Structured MCP tool invocation outcome."""

    tool_name: str
    rendered_content: str
    structured_content: Any | None = None
    is_error: bool = False

    @property
    def display_text(self) -> str:
        return self.rendered_content or "Done."


class MCPToolError(RuntimeError):
    """Typed MCP failure with enough metadata for logs and fallbacks."""

    def __init__(
        self,
        *,
        kind: MCPErrorKind,
        server_name: str,
        message: str,
        tool_name: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.server_name = server_name
        self.tool_name = tool_name
        self.cause = cause

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        *,
        kind: MCPErrorKind,
        server_name: str,
        tool_name: str | None = None,
        fallback_message: str | None = None,
    ) -> MCPToolError:
        if isinstance(exc, cls):
            return exc
        message = fallback_message or str(exc) or exc.__class__.__name__
        return cls(
            kind=kind,
            server_name=server_name,
            tool_name=tool_name,
            message=message,
            cause=exc,
        )


def parse_mcp_env_mapping(raw: Any) -> dict[str, str]:
    """Parse either JSON or KEY=VALUE env mappings into a dictionary."""
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items()}

    if not isinstance(raw, str):
        return {}

    stripped = raw.strip()
    if not stripped:
        return {}

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        return {str(key): str(value) for key, value in parsed.items()}

    mapping: dict[str, str] = {}
    for part in re.split(r"[;,]", stripped):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            mapping[key] = value
    return mapping


def parse_mcp_arg_list(raw: Any) -> list[str]:
    """Parse either JSON or shell-style args into a list of strings."""
    if isinstance(raw, list):
        return [str(item) for item in raw]

    if not isinstance(raw, str):
        return []

    stripped = raw.strip()
    if not stripped:
        return []

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, list):
        return [str(item) for item in parsed]

    return shlex.split(stripped, posix=False)


def resolve_mcp_cwd(raw: Any, *, project_root: Path) -> Path | None:
    """Resolve an optional cwd value against the current project root."""
    if raw is None:
        return None

    stripped = str(raw).strip()
    if not stripped:
        return None

    candidate = Path(stripped).expanduser()
    return candidate if candidate.is_absolute() else project_root / candidate


def _coerce_float(raw: Any, *, default: float, minimum: float) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return max(value, minimum)


def _coerce_int(raw: Any, *, default: int, minimum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(value, minimum)