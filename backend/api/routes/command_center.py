"""Command-center routes for CLI-equivalent web controls."""

from __future__ import annotations

from fastapi import APIRouter

from backend.schemas.command_center import CommandCenterOverviewResponse, RuntimeVerificationResponse
from backend.services.command_center_service import CommandCenterService

router = APIRouter(prefix="/api/command-center", tags=["command-center"])
service = CommandCenterService()


@router.get("/overview", response_model=CommandCenterOverviewResponse)
async def get_command_center_overview() -> CommandCenterOverviewResponse:
    """Return the web-facing view of CLI inspection features."""
    return await service.get_overview()


@router.post("/mcp/refresh", response_model=CommandCenterOverviewResponse)
async def refresh_mcp_discovery() -> CommandCenterOverviewResponse:
    """Refresh cached MCP discovery inventory without reloading the full runtime."""
    return await service.refresh_mcp_discovery()


@router.post("/verify", response_model=RuntimeVerificationResponse)
async def verify_runtime() -> RuntimeVerificationResponse:
    """Run the CLI-style runtime verification workflow."""
    return await service.verify_runtime()