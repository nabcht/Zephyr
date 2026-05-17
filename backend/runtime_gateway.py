"""Backend-owned runtime gateway for the hybrid HTTP API."""

from __future__ import annotations

import asyncio
from io import StringIO
import uuid

from rich.console import Console

import config
from core.app_runtime import AppRuntime
from core.chat_service import ChatService

_runtime = AppRuntime()
_chat_service = ChatService(_runtime)
_init_lock = asyncio.Lock()
_backend_console = Console(file=StringIO(), force_terminal=False, color_system=None, width=120)


async def ensure_runtime_ready() -> AppRuntime:
    """Initialize the shared backend runtime once and return it."""
    if _runtime.llm is not None and _runtime.tool_engine is not None:
        return _runtime

    async with _init_lock:
        if _runtime.llm is None or _runtime.tool_engine is None:
            await _runtime.initialize()
    return _runtime


async def ensure_memory_ready() -> AppRuntime:
    """Initialize only the session/durable storage layer when possible."""
    await _runtime.ensure_memory_ready()
    return _runtime


async def shutdown_runtime() -> None:
    """Tear down the shared backend runtime."""
    await _runtime.shutdown()


def get_runtime() -> AppRuntime:
    """Return the shared backend runtime instance."""
    return _runtime


def get_chat_service() -> ChatService:
    """Return the shared backend chat orchestration service."""
    return _chat_service


def get_backend_console() -> Console:
    """Return the silent console used for non-interactive backend turns."""
    return _backend_console


def new_session_id() -> str:
    """Create a short session identifier for web conversations."""
    return uuid.uuid4().hex[:8]
