"""Session lifecycle and chat services for the hybrid backend."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import config

from backend.runtime_gateway import (
    ensure_memory_ready,
    ensure_runtime_ready,
    get_backend_console,
    get_chat_service,
    get_runtime,
    new_session_id,
)
from backend.schemas.chat import ChatTurnResponse, SessionHistoryResponse, SessionMessageResponse
from backend.schemas.session import SessionCreateResponse


class ChatSessionService:
    """Drive web sessions and chat turns through the shared runtime."""

    @staticmethod
    def _resolve_sensitive_tool_approval(allow_sensitive_tools: bool | None) -> bool | None:
        if allow_sensitive_tools is not None:
            return allow_sensitive_tools
        if config.REQUIRE_CONFIRMATION:
            return False
        return None

    async def create_session(self) -> SessionCreateResponse:
        return SessionCreateResponse(session_id=new_session_id())

    async def get_history(self, session_id: str, *, limit: int = 40) -> SessionHistoryResponse:
        runtime = await ensure_memory_ready()
        history = await runtime.memory.get_session_history(session_id, limit=limit)
        messages = [SessionMessageResponse.model_validate(item) for item in history]
        return SessionHistoryResponse(session_id=session_id, messages=messages)

    async def run_turn(
        self,
        session_id: str,
        message: str,
        *,
        allow_sensitive_tools: bool | None = None,
    ) -> ChatTurnResponse:
        await ensure_runtime_ready()
        response = await get_chat_service().run_turn(
            session_id,
            message,
            console=get_backend_console(),
            allow_sensitive_tools=self._resolve_sensitive_tool_approval(allow_sensitive_tools),
        )
        return ChatTurnResponse(session_id=session_id, response=response)

    async def stream_turn(
        self,
        session_id: str,
        message: str,
        *,
        allow_sensitive_tools: bool | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream one persisted chat turn for the provided session."""
        runtime = get_runtime()
        if runtime.llm is None or runtime.tool_engine is None:
            yield "*🔄 Initializing shared runtime…*"

        await ensure_runtime_ready()
        async for chunk in get_chat_service().stream_turn(
            session_id,
            message,
            allow_sensitive_tools=self._resolve_sensitive_tool_approval(allow_sensitive_tools),
        ):
            yield chunk