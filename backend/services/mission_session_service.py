"""Session-aware mission execution for the hybrid backend."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import config

from backend.runtime_gateway import ensure_runtime_ready, get_backend_console
from backend.schemas.chat import ChatTurnResponse
from core.mission_service import MissionService


class MissionSessionService:
    """Drive multi-agent mission turns through the shared runtime."""

    @staticmethod
    def _resolve_sensitive_tool_approval(allow_sensitive_tools: bool | None) -> bool | None:
        if allow_sensitive_tools is not None:
            return allow_sensitive_tools
        if config.REQUIRE_CONFIRMATION:
            return False
        return None

    async def run_turn(
        self,
        session_id: str,
        message: str,
        *,
        allow_sensitive_tools: bool | None = None,
    ) -> ChatTurnResponse:
        runtime = await ensure_runtime_ready()
        attachment_context = await runtime.build_session_attachment_context(session_id, message)
        mission_service = MissionService(runtime, get_backend_console())
        response = await mission_service.run_turn(
            session_id,
            message,
            allow_sensitive_tools=self._resolve_sensitive_tool_approval(allow_sensitive_tools),
            session_attachment_context=attachment_context,
        )
        return ChatTurnResponse(session_id=session_id, response=response)

    async def stream_turn(
        self,
        session_id: str,
        message: str,
        *,
        allow_sensitive_tools: bool | None = None,
    ) -> AsyncGenerator[str, None]:
        yield self._initial_progress_snapshot(message)

        runtime = await ensure_runtime_ready()
        attachment_context = await runtime.build_session_attachment_context(session_id, message)
        mission_service = MissionService(runtime, get_backend_console())
        async for chunk in mission_service.stream_turn(
            session_id,
            message,
            allow_sensitive_tools=self._resolve_sensitive_tool_approval(allow_sensitive_tools),
            session_attachment_context=attachment_context,
        ):
            yield chunk

    @staticmethod
    def _initial_progress_snapshot(message: str) -> str:
        return "\n".join([
            "Mission in progress",
            f"Goal: {message}",
            "Status: Preparing runtime for mission execution.",
            "Round: 0",
            "Current agent: Supervisor",
            "Agent turns: No turns recorded yet.",
            "Findings: 0 | Requests: 0 | Code revisions: 0",
            "Sandbox: No code proposed yet",
            "Review: No review completed yet",
            "MCP: No MCP tool results recorded yet",
            "Recent milestones:",
            "- Preparing runtime for mission execution.",
        ])