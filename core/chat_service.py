"""Shared chat-turn orchestration for CLI and GUI frontends."""

from __future__ import annotations

from collections.abc import AsyncGenerator
import logging
from typing import Any

from rich.console import Console

from core.app_runtime import AppRuntime

log = logging.getLogger("uzephyr.chat_service")


class ChatService:
    """Coordinates chat history, inference, and persistence for one runtime."""

    def __init__(self, runtime: AppRuntime, *, history_limit: int = 20) -> None:
        self.runtime = runtime
        self.history_limit = history_limit

    async def run_turn(
        self,
        session_id: str,
        user_message: str,
        *,
        console: Console,
        live: Any | None = None,
        allow_sensitive_tools: bool | None = None,
    ) -> str:
        """Run a single non-streaming chat turn and persist the final response."""
        context = await self.runtime.build_chat_context(session_id, history_limit=self.history_limit)
        await self.runtime.memory.add_message(session_id, "user", user_message)

        response = await self.runtime.require_llm().chat(
            system_prompt=context.system_prompt,
            history=context.history,
            user_message=user_message,
            console=console,
            live=live,
            allow_sensitive_tools=allow_sensitive_tools,
        )

        await self._finalize_turn(session_id, response)
        return response

    async def stream_turn(
        self,
        session_id: str,
        user_message: str,
        *,
        allow_sensitive_tools: bool | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream one chat turn and persist the final response when complete."""
        context = await self.runtime.build_chat_context(session_id, history_limit=self.history_limit)
        await self.runtime.memory.add_message(session_id, "user", user_message)

        final_response = ""
        async for chunk in self.runtime.require_llm().chat_stream_gui(
            context.system_prompt,
            context.history,
            user_message,
            allow_sensitive_tools=allow_sensitive_tools,
        ):
            final_response = chunk
            yield chunk

        await self._finalize_turn(session_id, final_response)

    async def _finalize_turn(self, session_id: str, response: str) -> None:
        await self._persist_assistant_message(session_id, response)
        self.runtime.start_deferred_search_refresh()

    async def _persist_assistant_message(self, session_id: str, response: str) -> None:
        if not response.strip():
            return

        try:
            await self.runtime.memory.add_message(session_id, "assistant", response)
        except Exception as exc:
            log.warning("Failed to persist assistant response for session %s: %s", session_id, exc)