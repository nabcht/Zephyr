"""Chat routes for the hybrid backend."""

from __future__ import annotations

from collections.abc import AsyncGenerator
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.schemas.chat import ChatTurnRequest, ChatTurnResponse
from backend.services.chat_session_service import ChatSessionService

router = APIRouter(prefix="/api/chat", tags=["chat"])
service = ChatSessionService()


@router.post("/turn", response_model=ChatTurnResponse)
async def run_chat_turn(payload: ChatTurnRequest) -> ChatTurnResponse:
    """Run one persisted chat turn for the provided session."""
    return await service.run_turn(
        payload.session_id,
        payload.message,
        allow_sensitive_tools=payload.allow_sensitive_tools,
    )


def _format_sse(event: str, payload: dict[str, str | bool]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"


@router.post("/stream")
async def stream_chat_turn(payload: ChatTurnRequest, request: Request) -> StreamingResponse:
    """Stream progressive chat snapshots over Server-Sent Events."""

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for chunk in service.stream_turn(
                payload.session_id,
                payload.message,
                allow_sensitive_tools=payload.allow_sensitive_tools,
            ):
                if await request.is_disconnected():
                    break
                yield _format_sse("snapshot", {"content": chunk, "done": False})

            if not await request.is_disconnected():
                yield _format_sse("done", {"content": "", "done": True})
        except Exception as exc:
            yield _format_sse("error", {"content": str(exc), "done": True})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )