"""System and runtime inspection endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from backend.schemas.system import HealthResponse, SystemStatusResponse
from backend.services.runtime_service import RuntimeStatusService

router = APIRouter(prefix="/api/system", tags=["system"])
service = RuntimeStatusService()


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Return a lightweight backend health response."""
    return service.get_health()


@router.get("/status", response_model=SystemStatusResponse)
async def get_status() -> SystemStatusResponse:
    """Return a stable status snapshot for the frontend dashboard."""
    return await service.get_system_status()