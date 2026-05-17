"""Response schemas for the hybrid command-center endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from core.mcp_contracts import MCPErrorKind, MCPServerState


class CommandReferenceResponse(BaseModel):
    command: str
    description: str
    web_available: bool
    web_label: str | None = None


class ToolCatalogEntryResponse(BaseModel):
    name: str
    description: str
    source: str
    source_label: str
    tags: list[str] = Field(default_factory=list)


class MCPServerStatusResponse(BaseModel):
    name: str
    tool_prefix: str
    command: str
    args: list[str] = Field(default_factory=list)
    connected: bool
    discovered_tools: list[str] = Field(default_factory=list)
    state: MCPServerState
    last_error: str | None = None
    last_discovered_at: str | None = None
    last_successful_connection_at: str | None = None
    last_error_kind: MCPErrorKind | None = None
    last_error_tool_name: str | None = None
    degraded_reason: str | None = None


class MCPToolExecutionResponse(BaseModel):
    tool_name: str
    executed_at: str
    display_text: str
    structured_content: Any | None = None
    structured_content_type: str | None = None
    structured_content_preview: str | None = None
    is_error: bool = False
    error_type: str | None = None


class MCPOverviewResponse(BaseModel):
    enabled: bool
    external_integrations_enabled: bool
    configured: bool
    message: str
    servers: list[MCPServerStatusResponse] = Field(default_factory=list)
    recent_executions: list[MCPToolExecutionResponse] = Field(default_factory=list)


class DurableMemoryResponse(BaseModel):
    facts: list[str] = Field(default_factory=list)


class CommandCenterOverviewResponse(BaseModel):
    runtime_initialized: bool
    commands: list[CommandReferenceResponse] = Field(default_factory=list)
    tools: list[ToolCatalogEntryResponse] = Field(default_factory=list)
    mcp: MCPOverviewResponse
    memory: DurableMemoryResponse


class RuntimeVerificationResponse(BaseModel):
    valid_skills: list[str] = Field(default_factory=list)
    repaired_skills: list[str] = Field(default_factory=list)
    broken_skills: list[str] = Field(default_factory=list)
    sandbox_readiness: list[str] = Field(default_factory=list)
    truth_synthesis: list[str] = Field(default_factory=list)
    startup_guidance: list[str] = Field(default_factory=list)
    eval_summary: str | None = None