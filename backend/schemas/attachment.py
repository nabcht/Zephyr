"""Schemas for session-scoped attachment APIs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SessionAttachmentResponse(BaseModel):
    attachment_id: str
    session_id: str
    name: str
    media_type: str
    size_bytes: int
    created_at: str


class SessionAttachmentListResponse(BaseModel):
    session_id: str
    attachments: list[SessionAttachmentResponse] = Field(default_factory=list)


class SessionAttachmentDeleteResponse(BaseModel):
    session_id: str
    attachment_id: str
    deleted: bool