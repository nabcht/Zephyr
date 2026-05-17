"""Session lifecycle routes for the hybrid backend."""

from __future__ import annotations

from fastapi import APIRouter

from backend.schemas.chat import SessionHistoryResponse
from backend.schemas.session import SessionCreateResponse
from backend.services.chat_session_service import ChatSessionService

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
service = ChatSessionService()


@router.post("", response_model=SessionCreateResponse)
async def create_session() -> SessionCreateResponse:
    """Create a new web chat session identifier."""
    return await service.create_session()


@router.get("/{session_id}/messages", response_model=SessionHistoryResponse)
async def get_session_history(session_id: str) -> SessionHistoryResponse:
    """Return recent persisted messages for a session."""
    return await service.get_history(session_id)