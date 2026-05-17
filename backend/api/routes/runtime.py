"""Runtime action routes for the hybrid backend."""

from __future__ import annotations

from collections.abc import AsyncGenerator
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.schemas.system import RuntimeActionStreamResponse, RuntimePreparationResponse, SystemStatusResponse
from backend.services.runtime_service import RuntimeStatusService

router = APIRouter(prefix="/api/runtime", tags=["runtime"])
service = RuntimeStatusService()


def _format_sse(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"


@router.post("/reload", response_model=SystemStatusResponse)
async def reload_runtime() -> SystemStatusResponse:
    """Reload tool definitions and refresh the background search state."""
    return await service.reload_runtime()


@router.post("/reload/stream")
async def stream_reload_runtime(request: Request) -> StreamingResponse:
    """Stream progressive runtime reload updates over Server-Sent Events."""

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for update in service.stream_reload_runtime():
                if await request.is_disconnected():
                    break
                event_name = "done" if update.done else "snapshot"
                yield _format_sse(event_name, update.model_dump(mode="json"))
        except Exception as exc:
            error = RuntimeActionStreamResponse(
                action="reload",
                stage="error",
                message=str(exc),
                lines=[str(exc)],
                done=True,
                success=False,
            )
            yield _format_sse("error", error.model_dump(mode="json"))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/prepare", response_model=RuntimePreparationResponse)
async def prepare_runtime() -> RuntimePreparationResponse:
    """Prepare local runtime assets exposed by the current provider and sandbox."""
    return await service.prepare_runtime()


@router.post("/prepare/stream")
async def stream_prepare_runtime(request: Request) -> StreamingResponse:
    """Stream progressive runtime preparation updates over Server-Sent Events."""

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for update in service.stream_prepare_runtime():
                if await request.is_disconnected():
                    break
                event_name = "done" if update.done else "snapshot"
                yield _format_sse(event_name, update.model_dump(mode="json"))
        except Exception as exc:
            error = RuntimeActionStreamResponse(
                action="prepare",
                stage="error",
                message=str(exc),
                lines=[str(exc)],
                done=True,
                success=False,
            )
            yield _format_sse("error", error.model_dump(mode="json"))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )