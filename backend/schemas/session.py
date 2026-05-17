"""Session lifecycle response schemas for the hybrid backend."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SessionCreateResponse(BaseModel):
    session_id: str = Field(min_length=1)