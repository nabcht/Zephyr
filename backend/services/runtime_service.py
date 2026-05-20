"""Service objects for backend runtime inspection."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from backend.core.zephyr_wrapper import ZephyrCoreWrapper
from backend.runtime_gateway import ensure_runtime_ready, get_runtime
from backend.schemas.system import (
    HealthResponse,
    RuntimeActionStreamResponse,
    RuntimePreparationResponse,
    SystemStatusResponse,
)
import config
from core.embedding_model import describe_embedding_model_preparation, prepare_embedding_model
from core.llm import (
    describe_inference_runtime_preparation,
    describe_llamacpp_preparation,
    prepare_llamacpp_runtime,
)
from skills.sandbox.scripts.sandbox import describe_sandbox_preparation, prepare_sandbox_backend


class RuntimeStatusService:
    """Provide stable backend responses from the existing Zephyr core."""

    def __init__(self, wrapper: ZephyrCoreWrapper | None = None) -> None:
        self.wrapper = wrapper or ZephyrCoreWrapper()

    def get_health(self) -> HealthResponse:
        return HealthResponse(status="ok", service="Zephyr Hybrid API")

    async def get_system_status(self) -> SystemStatusResponse:
        runtime = get_runtime()
        snapshot = self.wrapper.get_system_snapshot(runtime)
        return SystemStatusResponse.model_validate(snapshot)

    async def reload_runtime(self) -> SystemStatusResponse:
        runtime = await ensure_runtime_ready()
        if runtime.tool_engine is not None:
            await runtime.reload_skills()
        if runtime.indexer is not None:
            await runtime.refresh_search_index(wait_for_completion=False)
        snapshot = self.wrapper.get_system_snapshot(runtime)
        return SystemStatusResponse.model_validate(snapshot)

    async def stream_reload_runtime(self) -> AsyncGenerator[RuntimeActionStreamResponse, None]:
        lines: list[str] = []

        def update(stage: str, message: str, *, done: bool = False, status: SystemStatusResponse | None = None) -> RuntimeActionStreamResponse:
            lines.append(message)
            return RuntimeActionStreamResponse(
                action="reload",
                stage=stage,
                message=message,
                lines=list(lines),
                done=done,
                success=True if done else None,
                status=status,
            )

        yield update("starting", "Reload requested. Initializing the shared runtime...")
        runtime = await ensure_runtime_ready()

        yield update("skills", "Runtime ready. Reloading skill tools...")
        if runtime.tool_engine is not None:
            await runtime.reload_skills()
            yield update("skills-complete", "Skill tools reloaded.")
        else:
            yield update("skills-skipped", "Tool engine unavailable; skipped skill reload.")

        if runtime.indexer is not None:
            yield update("search", "Refreshing the search index in the background...")
            await runtime.refresh_search_index(wait_for_completion=False)
            yield update("search-complete", "Background search refresh requested.")
        else:
            yield update("search-skipped", "Search runtime unavailable; skipped search refresh.")

        snapshot = SystemStatusResponse.model_validate(self.wrapper.get_system_snapshot(runtime))
        yield update("completed", "Runtime reload completed.", done=True, status=snapshot)

    async def prepare_runtime(self) -> RuntimePreparationResponse:
        sandbox_preparation = await prepare_sandbox_backend()
        lines = describe_sandbox_preparation(sandbox_preparation)
        embedding_preparation = await prepare_embedding_model()
        lines.append("")
        lines.extend(describe_embedding_model_preparation(embedding_preparation))

        if config.LLM_PROVIDER == "llamacpp":
            llamacpp_preparation = await prepare_llamacpp_runtime()
            lines.append("")
            lines.extend(describe_llamacpp_preparation(llamacpp_preparation))
            success = sandbox_preparation.success and embedding_preparation.success and llamacpp_preparation.success
        else:
            success = sandbox_preparation.success and embedding_preparation.success

        runtime = await ensure_runtime_ready()
        inference_preparation = await runtime.prepare_inference_runtime()
        lines.append("")
        lines.extend(describe_inference_runtime_preparation(inference_preparation))

        await runtime.prepare_search_runtime()
        snapshot = self.wrapper.get_system_snapshot(runtime)
        lines.append("")
        lines.append(f"Search runtime status: {snapshot['search_status']}.")
        success = success and inference_preparation.success
        return RuntimePreparationResponse(
            success=success,
            lines=lines,
            status=SystemStatusResponse.model_validate(snapshot),
        )

    async def stream_prepare_runtime(self) -> AsyncGenerator[RuntimeActionStreamResponse, None]:
        lines: list[str] = []

        def update(
            stage: str,
            message: str,
            *,
            extra_lines: list[str] | None = None,
            done: bool = False,
            success: bool | None = None,
            status: SystemStatusResponse | None = None,
        ) -> RuntimeActionStreamResponse:
            lines.append(message)
            if extra_lines:
                lines.extend(extra_lines)
            return RuntimeActionStreamResponse(
                action="prepare",
                stage=stage,
                message=message,
                lines=list(lines),
                done=done,
                success=success,
                status=status,
            )

        yield update("starting", "Prepare requested. Inspecting local runtime assets...")

        yield update("sandbox", "Preparing sandbox backend...")
        sandbox_preparation = await prepare_sandbox_backend()
        sandbox_lines = describe_sandbox_preparation(sandbox_preparation)
        yield update("sandbox-complete", "Sandbox preparation finished.", extra_lines=sandbox_lines)

        yield update("embedding", "Preparing the local embedding-model cache...")
        embedding_preparation = await prepare_embedding_model()
        embedding_lines = describe_embedding_model_preparation(embedding_preparation)
        yield update("embedding-complete", "Embedding-model preparation finished.", extra_lines=embedding_lines)

        llamacpp_preparation = None
        if config.LLM_PROVIDER == "llamacpp":
            yield update("llamacpp", "Preparing local LlamaCPP assets...")
            llamacpp_preparation = await prepare_llamacpp_runtime()
            llamacpp_lines = describe_llamacpp_preparation(llamacpp_preparation)
            yield update("llamacpp-complete", "LlamaCPP preparation finished.", extra_lines=llamacpp_lines)

        runtime = await ensure_runtime_ready()
        yield update("inference", "Warming the active inference runtime for a more predictable first turn...")
        inference_preparation = await runtime.prepare_inference_runtime()
        inference_lines = describe_inference_runtime_preparation(inference_preparation)
        yield update("inference-complete", "Inference runtime warm-up finished.", extra_lines=inference_lines)

        yield update("search", "Settling the search runtime for predictable first search-backed use...")
        await runtime.prepare_search_runtime()
        snapshot = SystemStatusResponse.model_validate(self.wrapper.get_system_snapshot(runtime))
        yield update("search-complete", f"Search runtime settled: {snapshot.search_status}.")

        success = sandbox_preparation.success and embedding_preparation.success
        if llamacpp_preparation is not None:
            success = success and llamacpp_preparation.success
        success = success and inference_preparation.success

        yield update(
            "completed",
            "Runtime preparation completed.",
            done=True,
            success=success,
            status=snapshot,
        )