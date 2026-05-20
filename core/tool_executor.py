"""Tool execution and approval policy helpers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from typing import Any, Callable, Protocol

import config
from core.mcp_contracts import MCPToolResult
from rich.console import Console
from rich.prompt import Confirm

log = logging.getLogger("zephyr.tool_executor")


class RegisteredTool(Protocol):
    """Structural contract for a registered tool entry."""

    name: str
    fn: Callable[..., Any]
    sensitive: bool
    tags: list[str]
    source: str


@dataclass(slots=True)
class ToolExecutionResult:
    """Normalized tool execution envelope with optional structured payloads."""

    tool_name: str
    source: str
    display_text: str
    executed_at: str
    structured_content: Any | None = None
    is_error: bool = False
    error_type: str | None = None

    @property
    def structured_content_type(self) -> str | None:
        if self.structured_content is None:
            return None
        if isinstance(self.structured_content, dict):
            return "object"
        if isinstance(self.structured_content, list):
            return "array"
        if isinstance(self.structured_content, str):
            return "string"
        if isinstance(self.structured_content, bool):
            return "boolean"
        if isinstance(self.structured_content, (int, float)):
            return "number"
        return type(self.structured_content).__name__.lower()

    def structured_content_preview(self, *, max_length: int = 180) -> str | None:
        if self.structured_content is None:
            return None
        try:
            rendered = json.dumps(self.structured_content, ensure_ascii=False, sort_keys=True)
        except TypeError:
            rendered = str(self.structured_content)
        return _truncate_text(rendered, max_length=max_length)

    def summary(self, *, max_length: int = 140) -> str:
        if self.structured_content is not None:
            content_type = self.structured_content_type or "structured"
            preview = self.structured_content_preview(max_length=max_length)
            if preview:
                return f"{self.tool_name} returned {content_type}: {preview}"
            return f"{self.tool_name} returned {content_type} structured content"
        if self.is_error:
            return f"{self.tool_name} failed: {_truncate_text(self.display_text, max_length=max_length)}"
        return f"{self.tool_name}: {_truncate_text(self.display_text, max_length=max_length)}"


def tool_is_allowed(tool_def: RegisteredTool, allowed_tags: list[str] | None) -> bool:
    """Return whether a tool is available to the current agent tag set."""
    if allowed_tags is None:
        return True
    return "universal" in tool_def.tags or any(tag in allowed_tags for tag in tool_def.tags)


class ToolExecutor:
    """Execute tools while enforcing tag filters and sensitive-tool approval."""

    def __init__(
        self,
        *,
        require_confirmation: Callable[[], bool] | None = None,
        confirm: Callable[..., bool] = Confirm.ask,
    ) -> None:
        self._require_confirmation = require_confirmation or (lambda: config.REQUIRE_CONFIRMATION)
        self._confirm = confirm

    async def execute(
        self,
        tool_def: RegisteredTool | None,
        args: dict[str, Any],
        *,
        allowed_tags: list[str] | None = None,
        console: Console | None = None,
        allow_sensitive_tools: bool | None = None,
    ) -> str:
        """Execute a registered tool and normalize the result to a string."""
        result = await self.execute_detailed(
            tool_def,
            args,
            allowed_tags=allowed_tags,
            console=console,
            allow_sensitive_tools=allow_sensitive_tools,
        )
        return result.display_text

    async def execute_detailed(
        self,
        tool_def: RegisteredTool | None,
        args: dict[str, Any],
        *,
        allowed_tags: list[str] | None = None,
        console: Console | None = None,
        allow_sensitive_tools: bool | None = None,
    ) -> ToolExecutionResult:
        """Execute a registered tool and retain structured result metadata when available."""
        executed_at = _utc_now_iso()
        if tool_def is None:
            requested_name = args.get("__tool_name__", "")
            return ToolExecutionResult(
                tool_name=str(requested_name),
                source="unknown",
                display_text=f"Error: unknown tool '{requested_name}'.",
                executed_at=executed_at,
                is_error=True,
                error_type="UnknownTool",
            )

        if not tool_is_allowed(tool_def, allowed_tags):
            return ToolExecutionResult(
                tool_name=tool_def.name,
                source=tool_def.source,
                display_text=f"Error: tool '{tool_def.name}' is not allowed for this agent.",
                executed_at=executed_at,
                is_error=True,
                error_type="DisallowedTool",
            )

        if tool_def.sensitive and self._require_confirmation():
            approved = await self._resolve_sensitive_tool_approval(
                tool_name=tool_def.name,
                args=args,
                console=console,
                allow_sensitive_tools=allow_sensitive_tools,
            )
            if not approved:
                return ToolExecutionResult(
                    tool_name=tool_def.name,
                    source=tool_def.source,
                    display_text="User denied execution of this tool.",
                    executed_at=executed_at,
                    is_error=True,
                    error_type="UserDenied",
                )

        try:
            result = tool_def.fn(**args)
            if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                result = await result
            return self._coerce_result(tool_def, result, executed_at=executed_at)
        except Exception as exc:
            error_msg = f"Tool '{tool_def.name}' raised an error: {type(exc).__name__}: {exc}"
            log.exception(error_msg)
            return ToolExecutionResult(
                tool_name=tool_def.name,
                source=tool_def.source,
                display_text=error_msg,
                executed_at=executed_at,
                is_error=True,
                error_type=type(exc).__name__,
            )

    @staticmethod
    def _coerce_result(
        tool_def: RegisteredTool,
        result: Any,
        *,
        executed_at: str,
    ) -> ToolExecutionResult:
        if isinstance(result, MCPToolResult):
            return ToolExecutionResult(
                tool_name=tool_def.name,
                source=tool_def.source,
                display_text=result.display_text,
                executed_at=executed_at,
                structured_content=result.structured_content,
                is_error=result.is_error,
                error_type="MCPToolResultError" if result.is_error else None,
            )

        return ToolExecutionResult(
            tool_name=tool_def.name,
            source=tool_def.source,
            display_text=str(result) if result is not None else "Done.",
            executed_at=executed_at,
        )

    async def _resolve_sensitive_tool_approval(
        self,
        *,
        tool_name: str,
        args: dict[str, Any],
        console: Console | None,
        allow_sensitive_tools: bool | None,
    ) -> bool:
        if allow_sensitive_tools is False:
            return False

        if allow_sensitive_tools is True:
            if console:
                console.print(f"  [warning]Sensitive tool approved:[/] {tool_name}({args})")
            return True

        if console:
            console.print(f"  [warning]⚠ Sensitive tool:[/] {tool_name}({args})")

        try:
            return await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self._confirm(f"  Allow '{tool_name}'?", default=False),
            )
        except (EOFError, KeyboardInterrupt):
            return False


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _truncate_text(text: str, *, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."