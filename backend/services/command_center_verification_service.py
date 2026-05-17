"""Verification and status-line assembly for the command-center runtime view."""

from __future__ import annotations

import asyncio

from backend.schemas.command_center import RuntimeVerificationResponse
from core.evals import run_eval_scenarios, summarize_eval_results
from core.startup_guidance import format_startup_guidance_lines, get_startup_guidance
from core.truth_synthesis import describe_truth_synthesis_health


_WEB_VERIFY_EVAL_TIMEOUT_SECONDS = 45


class CommandCenterVerificationService:
    """Build command-center verification payloads from runtime state."""

    def build_response(
        self,
        *,
        valid_skills: list[str] | None = None,
        repaired_skills: list[str] | None = None,
        broken_skills: list[str] | None = None,
        eval_summary: str | None = None,
    ) -> RuntimeVerificationResponse:
        return RuntimeVerificationResponse(
            valid_skills=list(valid_skills or []),
            repaired_skills=list(repaired_skills or []),
            broken_skills=list(broken_skills or []),
            sandbox_readiness=self.sandbox_lines(),
            truth_synthesis=self.truth_lines(),
            startup_guidance=self.startup_guidance_lines(),
            eval_summary=eval_summary,
        )

    async def summarize_eval_run(self, mission_service: object, tool_engine: object) -> str:
        try:
            eval_results = await asyncio.wait_for(
                run_eval_scenarios(mission_service.run_mission, tool_engine),
                timeout=_WEB_VERIFY_EVAL_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            return (
                "Mission evals: timed out in web verification after "
                f"{_WEB_VERIFY_EVAL_TIMEOUT_SECONDS}s. Run /verify in the CLI for the full regression pass."
            )
        except Exception as exc:
            return f"Mission evals: unavailable in web verification ({type(exc).__name__}: {exc})."

        return summarize_eval_results(eval_results)

    @staticmethod
    def sandbox_lines() -> list[str]:
        from skills.sandbox.scripts.sandbox import describe_sandbox_readiness

        return list(describe_sandbox_readiness())

    @staticmethod
    def truth_lines() -> list[str]:
        try:
            return list(describe_truth_synthesis_health())
        except Exception as exc:
            return [
                "Truth synthesis health: unavailable",
                f"Reason: {exc}",
            ]

    @staticmethod
    def startup_guidance_lines() -> list[str]:
        guidance = get_startup_guidance()
        if not guidance.actions:
            return []
        return list(format_startup_guidance_lines(guidance))