"""Backend services for the CLI-to-web command center."""

from __future__ import annotations

from backend.runtime_gateway import ensure_memory_ready, ensure_runtime_ready, get_backend_console, get_runtime
from backend.schemas.command_center import (
    CommandCenterOverviewResponse,
    CommandReferenceResponse,
    DurableMemoryResponse,
    MCPConfigurationApplyRequest,
    MCPConfigurationApplyResponse,
    RuntimeVerificationResponse,
)
from backend.services.mcp_configuration_service import MCPConfigurationService
from backend.services.command_center_runtime_service import CommandCenterRuntimeService
from backend.services.command_center_verification_service import CommandCenterVerificationService
from core.mission_service import MissionService
from skills.skill_loader import SkillLoader


class CommandCenterService:
    """Expose CLI inspection and verification features to the React frontend."""

    def __init__(self) -> None:
        self._runtime_service = CommandCenterRuntimeService()
        self._verification_service = CommandCenterVerificationService()
        self._mcp_configuration_service = MCPConfigurationService()

    async def get_overview(self) -> CommandCenterOverviewResponse:
        runtime = await ensure_memory_ready()
        return await self._build_overview(runtime)

    async def refresh_mcp_discovery(self) -> CommandCenterOverviewResponse:
        runtime = await ensure_runtime_ready()
        if runtime.tool_engine is not None:
            await runtime.tool_engine.refresh_mcp_tools()
        return await self._build_overview(runtime)

    async def apply_mcp_configuration(self, payload: MCPConfigurationApplyRequest) -> MCPConfigurationApplyResponse:
        applied = self._mcp_configuration_service.apply(payload)

        existing_runtime = get_runtime()
        runtime_was_initialized = existing_runtime.tool_engine is not None and existing_runtime.llm is not None
        runtime = await ensure_runtime_ready()
        if runtime_was_initialized and runtime.tool_engine is not None:
            await runtime.tool_engine.reload_mcp_runtime()

        server_count = applied.server_count
        server_label = "server" if server_count == 1 else "servers"
        return MCPConfigurationApplyResponse(
            message=(
                f"Saved {server_count} MCP {server_label} to {applied.env_path.name} using {applied.format} format "
                "and refreshed the live runtime configuration."
            ),
            env_path=str(applied.env_path),
            env_block=applied.env_block,
            format=payload.format,
            server_count=server_count,
            overview=await self._build_overview(runtime),
        )

    async def _build_overview(self, runtime: object) -> CommandCenterOverviewResponse:
        facts_blob = await runtime.memory.get_durable_facts()
        tool_engine = runtime.tool_engine
        return CommandCenterOverviewResponse(
            runtime_initialized=runtime.llm is not None and tool_engine is not None,
            commands=self._command_references(),
            tools=self._runtime_service.build_tool_entries(tool_engine),
            mcp=self._runtime_service.build_mcp_overview(tool_engine),
            memory=DurableMemoryResponse(
                facts=[line.strip() for line in facts_blob.splitlines() if line.strip()],
            ),
        )

    async def verify_runtime(self) -> RuntimeVerificationResponse:
        runtime = await ensure_runtime_ready()
        tool_engine = runtime.tool_engine
        if tool_engine is None:
            return self._verification_service.build_response(
                broken_skills=["Tool engine is not initialised."],
                eval_summary="Mission evals: skipped (tool engine is not initialised).",
            )

        if tool_engine.skill_loader is None:
            tool_engine.skill_loader = SkillLoader(tool_engine)

        results = await tool_engine.skill_loader.verify_skill_integrity(auto_repair=True)
        mission_service = MissionService(runtime, get_backend_console())
        eval_summary = await self._verification_service.summarize_eval_run(mission_service, tool_engine)

        return self._verification_service.build_response(
            valid_skills=list(results.get("valid", [])),
            repaired_skills=list(results.get("repaired", [])),
            broken_skills=list(results.get("broken", [])),
            eval_summary=eval_summary,
        )

    @staticmethod
    def _command_references() -> list[CommandReferenceResponse]:
        return [
            CommandReferenceResponse(
                command="/mission <task>",
                description="Run the multi-agent agency loop.",
                web_available=True,
                web_label="Run mission",
            ),
            CommandReferenceResponse(
                command="/skills",
                description="Show loaded tools grouped by source.",
                web_available=True,
                web_label="Command center",
            ),
            CommandReferenceResponse(
                command="/memory",
                description="Show durable memory facts.",
                web_available=True,
                web_label="Command center",
            ),
            CommandReferenceResponse(
                command="/mcp",
                description="Show MCP server status and discovered tools.",
                web_available=True,
                web_label="Command center",
            ),
            CommandReferenceResponse(
                command="/mcp refresh",
                description="Refresh MCP discovery and reuse cached inventory if a server refresh fails.",
                web_available=True,
                web_label="Refresh MCP discovery",
            ),
            CommandReferenceResponse(
                command="/prepare",
                description="Prepare sandbox image and local model assets.",
                web_available=True,
                web_label="Prepare runtime",
            ),
            CommandReferenceResponse(
                command="/session",
                description="Create a fresh session id.",
                web_available=True,
                web_label="New session",
            ),
            CommandReferenceResponse(
                command="/reload",
                description="Reload skills and refresh the search index.",
                web_available=True,
                web_label="Reload tools",
            ),
            CommandReferenceResponse(
                command="/verify",
                description="Run skill integrity checks and runtime verification.",
                web_available=True,
                web_label="Verify runtime",
            ),
            CommandReferenceResponse(
                command="/help",
                description="Show the slash command reference.",
                web_available=True,
                web_label="Command map",
            ),
            CommandReferenceResponse(
                command="/quit | /exit | /q",
                description="Exit the terminal interface.",
                web_available=False,
                web_label=None,
            ),
        ]
