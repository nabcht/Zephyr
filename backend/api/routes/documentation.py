"""Documentation routes backed by the centralized Docs folder."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.schemas.documentation import MarkdownDocumentResponse
from backend.services.documentation_service import DocumentationService

router = APIRouter(prefix="/api/docs", tags=["docs"])
service = DocumentationService()


@router.get("/{slug}", response_model=MarkdownDocumentResponse)
async def get_document(slug: str) -> MarkdownDocumentResponse:
    """Return a markdown document that should be rendered directly by the frontend."""
    try:
        return MarkdownDocumentResponse(**service.get_document(slug))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown documentation slug: {slug}") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Documentation file not found: {exc.filename}") from exc