"""Schemas for documentation endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class MarkdownDocumentResponse(BaseModel):
    slug: str
    title: str
    content: str
    source_path: str