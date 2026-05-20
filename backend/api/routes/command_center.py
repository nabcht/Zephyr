"""Command-center routes for CLI-equivalent web controls."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.schemas.command_center import (
    CommandCenterOverviewResponse,
    MCPConfigurationApplyRequest,
    MCPConfigurationApplyResponse,
    MemoryBrainRepairResponse,
    RuntimeVerificationResponse,
)
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


@router.post("/mcp/apply", response_model=MCPConfigurationApplyResponse)
async def apply_mcp_configuration(payload: MCPConfigurationApplyRequest) -> MCPConfigurationApplyResponse:
    """Persist walkthrough-generated MCP settings and refresh the live runtime."""
    try:
        return await service.apply_mcp_configuration(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/memory/repair", response_model=MemoryBrainRepairResponse)
async def repair_memory_brain() -> MemoryBrainRepairResponse:
    """Rebuild timeline.log, truth.md, and entity backlinks from durable memories."""
    try:
        return await service.repair_memory_brain()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/verify", response_model=RuntimeVerificationResponse)
async def verify_runtime() -> RuntimeVerificationResponse:
    """Run the CLI-style runtime verification workflow."""
    return await service.verify_runtime()