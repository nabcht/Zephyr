"""Helpers for connecting to a stdio-based MCP server and exposing its tools."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
import re
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable, TypeVar

from core.mcp_contracts import MCPErrorKind, MCPServerSettings, MCPServerState, MCPServerStatus, MCPToolError, MCPToolResult, MCPToolSpec

try:
    from mcp import ClientSession, StdioServerParameters, stdio_client
except ImportError:  # pragma: no cover - exercised via runtime configuration
    ClientSession = None  # type: ignore[assignment]
    StdioServerParameters = None  # type: ignore[assignment]
    stdio_client = None  # type: ignore[assignment]

log = logging.getLogger("zephyr.mcp")

T = TypeVar("T")


@dataclass(slots=True)
class _WorkerCommand:
    action: str
    tool_name: str = ""
    arguments: dict[str, Any] | None = None
    future: asyncio.Future[MCPToolResult | None] | None = None


def _sanitize_component(value: str, *, default: str) -> str:
    sanitized = re.sub(r"[^0-9A-Za-z_]+", "_", value).strip("_").lower()
    return sanitized or default


class MCPStdioClient:
    """Persistent stdio client for a single MCP server."""

    def __init__(self, settings: MCPServerSettings) -> None:
        self.settings = settings
        self._server_slug = _sanitize_component(settings.name, default="server")
        self._prefix = _sanitize_component(settings.tool_prefix, default="mcp") if settings.tool_prefix else ""
        self._worker_loop: asyncio.AbstractEventLoop | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._worker_queue: asyncio.Queue[_WorkerCommand] | None = None
        self._last_discovered_tools: list[str] = []
        self._last_remote_tools: list[str] = []
        self._last_error: str | None = None
        self._last_error_kind: MCPErrorKind | None = None
        self._last_error_tool_name: str | None = None
        self._last_discovered_at: str | None = None
        self._last_successful_connection_at: str | None = None

    @property
    def server_name(self) -> str:
        return self.settings.name

    @property
    def enabled(self) -> bool:
        return bool(self.settings.command)

    @property
    def connected(self) -> bool:
        return self._worker_task is not None and not self._worker_task.done()

    def get_status(self) -> MCPServerStatus:
        return MCPServerStatus(
            name=self.settings.name,
            tool_prefix=self.settings.tool_prefix,
            command=self.settings.command,
            args=list(self.settings.args),
            connected=self.connected,
            discovered_tools=list(self._last_discovered_tools),
            last_error=self._last_error,
            last_discovered_at=self._last_discovered_at,
            last_successful_connection_at=self._last_successful_connection_at,
            state=self._status_state(),
            last_error_kind=self._last_error_kind,
            last_error_tool_name=self._last_error_tool_name,
            degraded_reason=self._status_degraded_reason(),
        )

    @property
    def discovered_remote_tools(self) -> list[str]:
        return list(self._last_remote_tools)

    async def close(self) -> None:
        """Close the MCP worker session if it belongs to the current event loop."""
        if self._worker_task is None:
            self._reset_worker_state()
            return

        current_loop = asyncio.get_running_loop()
        if self._worker_loop is not current_loop:
            log.debug(
                "Skipping graceful shutdown for MCP server '%s' from a different event loop.",
                self.settings.name,
            )
            self._reset_worker_state()
            return

        if self._worker_task.done():
            try:
                await self._worker_task
            finally:
                self._reset_worker_state()
            return

        assert self._worker_queue is not None
        stop_future: asyncio.Future[MCPToolResult | None] = current_loop.create_future()
        await self._worker_queue.put(_WorkerCommand(action="stop", future=stop_future))
        await stop_future
        await self._worker_task
        self._reset_worker_state()

    def qualify_tool_name(self, remote_name: str) -> str:
        """Create a collision-resistant local tool name for a remote MCP tool."""
        tool_slug = _sanitize_component(remote_name, default="tool")
        parts = [part for part in (self._prefix, self._server_slug, tool_slug) if part]
        return "_".join(parts) if parts else tool_slug

    async def list_tools(self) -> list[MCPToolSpec]:
        """Fetch tool metadata from the connected MCP server."""
        async def discover_once() -> list[MCPToolSpec]:
            async with self._open_session(startup_timeout_seconds=self.settings.connect_timeout_seconds) as session:
                self._mark_successful_connection()
                tool_result = await asyncio.wait_for(
                    session.list_tools(),
                    timeout=self.settings.discovery_timeout_seconds,
                )

            tools: list[MCPToolSpec] = []
            for tool in tool_result.tools:
                tools.append(
                    MCPToolSpec(
                        local_name=self.qualify_tool_name(tool.name),
                        remote_name=tool.name,
                        description=tool.description or f"MCP tool '{tool.name}' from {self.settings.name}.",
                        parameters=tool.inputSchema,
                    )
                )
            self._last_discovered_tools = [tool.local_name for tool in tools]
            self._last_remote_tools = [tool.remote_name for tool in tools]
            self._last_discovered_at = _utc_now_iso()
            return tools

        tools = await self._run_with_retries(
            operation_name="tool discovery",
            attempt_factory=discover_once,
            default_kind=MCPErrorKind.CONNECTION,
            fallback_message=f"Could not list tools from MCP server '{self.settings.name}'.",
            timeout_message=(
                f"Could not list tools from MCP server '{self.settings.name}' within "
                f"{self.settings.discovery_timeout_seconds:.1f}s."
            ),
        )
        self._clear_last_error()
        return tools

    async def call_tool(self, remote_name: str, arguments: dict[str, Any] | None = None) -> str:
        """Invoke an MCP tool through a worker-owned session bound to the current loop."""
        result = await self.invoke_tool(remote_name, arguments)
        return result.display_text

    async def invoke_tool(self, remote_name: str, arguments: dict[str, Any] | None = None) -> MCPToolResult:
        """Invoke an MCP tool and return a structured result envelope."""
        async def invoke_once() -> MCPToolResult:
            await self._ensure_worker()
            current_loop = asyncio.get_running_loop()
            assert self._worker_queue is not None

            future: asyncio.Future[MCPToolResult | None] = current_loop.create_future()
            await self._worker_queue.put(
                _WorkerCommand(
                    action="call_tool",
                    tool_name=remote_name,
                    arguments=arguments or {},
                    future=future,
                )
            )
            result = await asyncio.wait_for(future, timeout=self.settings.tool_timeout_seconds)
            return result or MCPToolResult(tool_name=remote_name, rendered_content="")

        result = await self._run_with_retries(
            operation_name=f"tool '{remote_name}'",
            attempt_factory=invoke_once,
            default_kind=MCPErrorKind.EXECUTION,
            fallback_message=f"MCP tool '{remote_name}' failed.",
            timeout_message=f"MCP tool '{remote_name}' timed out after {self.settings.tool_timeout_seconds:.1f}s.",
            tool_name=remote_name,
            reset_worker_on_failure=True,
        )
        self._clear_last_error()
        return result

    async def _message_handler(self, message: Any) -> None:
        if isinstance(message, Exception):
            log.warning("MCP server '%s' emitted an error: %s", self.settings.name, message)

    async def _ensure_worker(self) -> None:
        if not self.enabled:
            raise MCPToolError(
                kind=MCPErrorKind.CONFIGURATION,
                server_name=self.settings.name,
                message="MCP server is not configured.",
            )
        if ClientSession is None or StdioServerParameters is None or stdio_client is None:
            raise MCPToolError(
                kind=MCPErrorKind.DEPENDENCY,
                server_name=self.settings.name,
                message="The 'mcp' package is required for MCP integration.",
            )

        current_loop = asyncio.get_running_loop()
        if self._worker_task is not None:
            if self._worker_loop is current_loop and not self._worker_task.done():
                return
            if self._worker_task.done() and self._worker_loop is current_loop:
                await self._worker_task
            else:
                log.debug(
                    "Discarding MCP worker state for server '%s' because the event loop changed.",
                    self.settings.name,
                )
            self._reset_worker_state()

        ready_future: asyncio.Future[None] = current_loop.create_future()
        worker_queue: asyncio.Queue[_WorkerCommand] = asyncio.Queue()
        self._worker_loop = current_loop
        self._worker_queue = worker_queue
        self._worker_task = current_loop.create_task(self._worker(worker_queue, ready_future))
        try:
            await asyncio.wait_for(ready_future, timeout=self.settings.connect_timeout_seconds)
        except Exception as exc:
            if isinstance(exc, asyncio.TimeoutError):
                typed_error = MCPToolError(
                    kind=MCPErrorKind.CONNECTION,
                    server_name=self.settings.name,
                    message=(
                        f"Could not connect to MCP server '{self.settings.name}' within "
                        f"{self.settings.connect_timeout_seconds:.1f}s."
                    ),
                    cause=exc,
                )
            else:
                typed_error = MCPToolError.from_exception(
                    exc,
                    kind=MCPErrorKind.CONNECTION,
                    server_name=self.settings.name,
                    fallback_message=f"Could not connect to MCP server '{self.settings.name}'.",
                )
            self._record_error(typed_error)
            await self._discard_worker_task()
            raise typed_error

    async def _worker(
        self,
        worker_queue: asyncio.Queue[_WorkerCommand],
        ready_future: asyncio.Future[None],
    ) -> None:
        try:
            async with self._open_session() as session:
                ready_future.set_result(None)
                self._mark_successful_connection()
                self._clear_last_error()
                log.info("Connected to MCP server '%s'.", self.settings.name)

                while True:
                    command = await worker_queue.get()
                    if command.action == "stop":
                        if command.future is not None and not command.future.done():
                            command.future.set_result(None)
                        return

                    try:
                        result = await session.call_tool(command.tool_name, arguments=command.arguments or {})
                        tool_result = self._coerce_tool_result(command.tool_name, result)
                        if tool_result.is_error:
                            raise MCPToolError(
                                kind=MCPErrorKind.REMOTE,
                                server_name=self.settings.name,
                                tool_name=command.tool_name,
                                message=tool_result.rendered_content or f"MCP tool '{command.tool_name}' reported an error.",
                            )
                        if command.future is not None and not command.future.done():
                            command.future.set_result(tool_result)
                    except Exception as exc:
                        typed_error = MCPToolError.from_exception(
                            exc,
                            kind=self._classify_error_kind(exc, default=MCPErrorKind.EXECUTION),
                            server_name=self.settings.name,
                            tool_name=command.tool_name,
                            fallback_message=f"MCP tool '{command.tool_name}' failed.",
                        )
                        self._record_error(typed_error)
                        if command.future is not None and not command.future.done():
                            command.future.set_exception(typed_error)
        except Exception as exc:
            typed_error = MCPToolError.from_exception(
                exc,
                kind=MCPErrorKind.CONNECTION,
                server_name=self.settings.name,
                fallback_message=f"Could not connect to MCP server '{self.settings.name}'.",
            )
            self._record_error(typed_error)
            if not ready_future.done():
                ready_future.set_exception(typed_error)
            raise typed_error

    @asynccontextmanager
    async def _open_session(self, *, startup_timeout_seconds: float | None = None) -> AsyncIterator[ClientSession]:
        exit_stack = AsyncExitStack()
        try:
            server_parameters = self._build_server_parameters()
            streams = await _await_with_timeout(
                exit_stack.enter_async_context(stdio_client(server_parameters)),
                timeout_seconds=startup_timeout_seconds,
            )
            session = await _await_with_timeout(
                exit_stack.enter_async_context(ClientSession(*streams, message_handler=self._message_handler)),
                timeout_seconds=startup_timeout_seconds,
            )
            await _await_with_timeout(session.initialize(), timeout_seconds=startup_timeout_seconds)
            yield session
        finally:
            await exit_stack.aclose()

    def _build_server_parameters(self) -> Any:
        if ClientSession is None or StdioServerParameters is None or stdio_client is None:
            raise RuntimeError("The 'mcp' package is required for MCP integration.")
        return StdioServerParameters(
            command=self.settings.command,
            args=list(self.settings.args),
            env=dict(self.settings.env),
            cwd=self.settings.cwd,
        )

    def _reset_worker_state(self) -> None:
        self._worker_loop = None
        self._worker_task = None
        self._worker_queue = None

    def _status_state(self) -> MCPServerState:
        if self._last_error:
            return MCPServerState.ERROR
        if self.connected:
            return MCPServerState.CONNECTED
        return MCPServerState.READY

    def _status_degraded_reason(self) -> str | None:
        return MCPServerStatus(
            name=self.settings.name,
            tool_prefix=self.settings.tool_prefix,
            command=self.settings.command,
            args=list(self.settings.args),
            connected=self.connected,
            discovered_tools=list(self._last_discovered_tools),
            last_error=self._last_error,
            last_discovered_at=self._last_discovered_at,
            last_successful_connection_at=self._last_successful_connection_at,
            state=self._status_state(),
            last_error_kind=self._last_error_kind,
            last_error_tool_name=self._last_error_tool_name,
            degraded_reason="",
        ).derive_degraded_reason()

    def _record_error(self, error: MCPToolError) -> None:
        self._last_error = str(error)
        self._last_error_kind = error.kind
        self._last_error_tool_name = error.tool_name

    def _clear_last_error(self) -> None:
        self._last_error = None
        self._last_error_kind = None
        self._last_error_tool_name = None

    def _mark_successful_connection(self) -> None:
        self._last_successful_connection_at = _utc_now_iso()

    async def _run_with_retries(
        self,
        *,
        operation_name: str,
        attempt_factory: Callable[[], Awaitable[T]],
        default_kind: MCPErrorKind,
        fallback_message: str,
        timeout_message: str,
        tool_name: str | None = None,
        reset_worker_on_failure: bool = False,
    ) -> T:
        total_attempts = max(self.settings.max_retries, 0) + 1
        for attempt_number in range(1, total_attempts + 1):
            try:
                return await attempt_factory()
            except asyncio.TimeoutError as exc:
                typed_error = MCPToolError(
                    kind=default_kind,
                    server_name=self.settings.name,
                    tool_name=tool_name,
                    message=timeout_message,
                    cause=exc,
                )
            except Exception as exc:
                typed_error = self._coerce_operation_error(
                    exc,
                    default_kind=default_kind,
                    fallback_message=fallback_message,
                    tool_name=tool_name,
                )

            self._record_error(typed_error)

            if reset_worker_on_failure and self._should_reset_worker_after_error(typed_error):
                await self._discard_worker_task()

            if attempt_number >= total_attempts or not self._should_retry_error(typed_error):
                raise typed_error

            retry_delay = self._retry_delay(attempt_number)
            log.warning(
                "Retrying MCP %s for '%s' after failure (%s/%s): %s",
                operation_name,
                self.settings.name,
                attempt_number,
                total_attempts,
                typed_error,
            )
            if retry_delay > 0:
                await asyncio.sleep(retry_delay)

        raise AssertionError("unreachable")

    @staticmethod
    def _classify_error_kind(exc: Exception, *, default: MCPErrorKind) -> MCPErrorKind:
        if isinstance(exc, MCPToolError):
            return exc.kind
        if isinstance(exc, (BrokenPipeError, ConnectionError, EOFError, OSError)):
            return MCPErrorKind.CONNECTION
        return default

    def _coerce_operation_error(
        self,
        exc: Exception,
        *,
        default_kind: MCPErrorKind,
        fallback_message: str,
        tool_name: str | None,
    ) -> MCPToolError:
        if isinstance(exc, MCPToolError):
            return exc
        return MCPToolError.from_exception(
            exc,
            kind=self._classify_error_kind(exc, default=default_kind),
            server_name=self.settings.name,
            tool_name=tool_name,
            fallback_message=fallback_message,
        )

    @staticmethod
    def _should_retry_error(error: MCPToolError) -> bool:
        return isinstance(error.cause, asyncio.TimeoutError) or error.kind == MCPErrorKind.CONNECTION

    @staticmethod
    def _should_reset_worker_after_error(error: MCPToolError) -> bool:
        return isinstance(error.cause, asyncio.TimeoutError) or error.kind == MCPErrorKind.CONNECTION

    def _retry_delay(self, attempt_number: int) -> float:
        return max(self.settings.retry_backoff_seconds, 0.0) * attempt_number

    async def _discard_worker_task(self) -> None:
        task = self._worker_task
        loop = self._worker_loop
        self._reset_worker_state()
        if task is None:
            return

        current_loop = asyncio.get_running_loop()
        if loop is not current_loop:
            return

        if not task.done():
            task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    def _coerce_tool_result(self, tool_name: str, result: Any) -> MCPToolResult:
        structured_content = getattr(result, "structuredContent", None)
        return MCPToolResult(
            tool_name=tool_name,
            rendered_content=self._render_result(result),
            structured_content=structured_content,
            is_error=bool(getattr(result, "isError", False)),
        )

    @staticmethod
    def _render_result(result: Any) -> str:
        text_parts: list[str] = []
        for block in getattr(result, "content", []) or []:
            if getattr(block, "type", None) == "text" and hasattr(block, "text"):
                text_parts.append(str(block.text))
            elif hasattr(block, "model_dump"):
                text_parts.append(json.dumps(block.model_dump(mode="json"), ensure_ascii=False))
            else:
                text_parts.append(str(block))

        if text_parts:
            return "\n".join(part for part in text_parts if part).strip()

        structured = getattr(result, "structuredContent", None)
        if structured is not None:
            return json.dumps(structured, ensure_ascii=False)

        return ""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


async def _await_with_timeout(awaitable: Awaitable[T], *, timeout_seconds: float | None) -> T:
    if timeout_seconds is None or timeout_seconds <= 0:
        return await awaitable
    async with asyncio.timeout(timeout_seconds):
        return await awaitable