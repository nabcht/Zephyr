"""Session lifecycle routes for the hybrid backend."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from backend.schemas.attachment import (
    SessionAttachmentDeleteResponse,
    SessionAttachmentListResponse,
    SessionAttachmentResponse,
)
from backend.schemas.chat import SessionHistoryResponse
from backend.schemas.session import SessionCreateResponse
from backend.services.chat_session_service import ChatSessionService
from backend.services.session_attachment_service import SessionAttachmentService

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
service = ChatSessionService()
attachment_service = SessionAttachmentService()


@router.post("", response_model=SessionCreateResponse)
async def create_session() -> SessionCreateResponse:
    """Create a new web chat session identifier."""
    return await service.create_session()


@router.get("/{session_id}/messages", response_model=SessionHistoryResponse)
async def get_session_history(session_id: str) -> SessionHistoryResponse:
    """Return recent persisted messages for a session."""
    return await service.get_history(session_id)


@router.get("/{session_id}/attachments", response_model=SessionAttachmentListResponse)
async def list_session_attachments(session_id: str) -> SessionAttachmentListResponse:
    """Return active attachment metadata for a session."""
    return await attachment_service.list_attachments(session_id)


@router.post("/{session_id}/attachments", response_model=SessionAttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_session_attachment(session_id: str, file: UploadFile = File(...)) -> SessionAttachmentResponse:
    """Upload and index one attachment for session-scoped retrieval."""
    try:
        return await attachment_service.upload_attachment(session_id, file)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.delete("/{session_id}/attachments/{attachment_id}", response_model=SessionAttachmentDeleteResponse)
async def delete_session_attachment(session_id: str, attachment_id: str) -> SessionAttachmentDeleteResponse:
    """Delete one session attachment and remove it from the local indexes."""
    try:
        return await attachment_service.delete_attachment(session_id, attachment_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found.") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc