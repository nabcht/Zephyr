"""Chat and session response schemas for the hybrid backend."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SessionMessageResponse(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: list[SessionMessageResponse] = Field(default_factory=list)


class ChatTurnRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    allow_sensitive_tools: bool | None = None


class ChatTurnResponse(BaseModel):
    session_id: str
    response: str