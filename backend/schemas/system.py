"""Response schemas for backend system endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PrivacyStatusResponse(BaseModel):
    level: str
    badge: str
    title: str
    summary: str
    inference_backend: str
    remote_capabilities: list[str] = Field(default_factory=list)


class TrustSignalResponse(BaseModel):
    label: str
    level: str
    badge: str
    summary: str


class RuntimeTrustStatusResponse(BaseModel):
    level: str
    badge: str
    title: str
    signals: list[TrustSignalResponse] = Field(default_factory=list)


class ToolCountsResponse(BaseModel):
    total: int = 0
    skill_tools: int = 0
    builtins: int = 0
    mcp_tools: int = 0
    manual_tools: int = 0


class StartupActionResponse(BaseModel):
    level: str
    badge: str
    label: str
    summary: str
    command: str | None = None
    supports_prepare: bool = False


class StartupGuidanceResponse(BaseModel):
    level: str
    badge: str
    title: str
    actions: list[StartupActionResponse] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    service: str


class InferenceMetricsResponse(BaseModel):
    last_warmup_ms: float | None = None
    last_warmup_outcome: str = "not_run"
    last_completion_ms: float | None = None
    last_completion_outcome: str = "not_run"


class SystemStatusResponse(BaseModel):
    name: str
    version: str
    provider: str
    model: str
    interfaces: list[str] = Field(default_factory=list)
    runtime_initialized: bool
    inference_status: str
    inference_metrics: InferenceMetricsResponse = Field(default_factory=InferenceMetricsResponse)
    search_status: str
    external_integrations_enabled: bool
    safety_confirmation_required: bool
    design_system_path: str
    prepare_actions: list[str] = Field(default_factory=list)
    tool_counts: ToolCountsResponse
    privacy_status: PrivacyStatusResponse
    trust_status: RuntimeTrustStatusResponse
    startup_guidance: StartupGuidanceResponse


class RuntimePreparationResponse(BaseModel):
    success: bool
    lines: list[str] = Field(default_factory=list)
    status: SystemStatusResponse


class RuntimeActionStreamResponse(BaseModel):
    action: str
    stage: str
    message: str
    lines: list[str] = Field(default_factory=list)
    done: bool = False
    success: bool | None = None
    status: SystemStatusResponse | None = None