from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.services.command_center_verification_service import CommandCenterVerificationService


class _FakeMissionService:
    async def run_mission(self, *_args: object, **_kwargs: object) -> str:
        return "done"


class CommandCenterVerificationServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_summarize_eval_run_handles_timeout(self) -> None:
        service = CommandCenterVerificationService()

        async def raise_timeout(*_args: object, **_kwargs: object) -> object:
            raise TimeoutError

        with patch(
            "backend.services.command_center_verification_service.run_eval_scenarios",
            side_effect=raise_timeout,
        ):
            summary = await service.summarize_eval_run(_FakeMissionService(), object())

        self.assertIn("Mission evals: timed out in web verification", summary)

    async def test_summarize_eval_run_handles_errors(self) -> None:
        service = CommandCenterVerificationService()

        async def raise_failure(*_args: object, **_kwargs: object) -> object:
            raise RuntimeError("boom")

        with patch(
            "backend.services.command_center_verification_service.run_eval_scenarios",
            side_effect=raise_failure,
        ):
            summary = await service.summarize_eval_run(_FakeMissionService(), object())

        self.assertEqual(summary, "Mission evals: unavailable in web verification (RuntimeError: boom).")

    async def test_build_response_assembles_status_lines(self) -> None:
        service = CommandCenterVerificationService()

        with (
            patch.object(service, "sandbox_lines", return_value=["sandbox ok"]),
            patch.object(service, "truth_lines", return_value=["truth ok"]),
            patch.object(service, "startup_guidance_lines", return_value=["guidance ok"]),
        ):
            response = service.build_response(
                valid_skills=["skill_a"],
                repaired_skills=["skill_b"],
                broken_skills=["skill_c"],
                eval_summary="Mission evals: ok",
            )

        self.assertEqual(response.valid_skills, ["skill_a"])
        self.assertEqual(response.repaired_skills, ["skill_b"])
        self.assertEqual(response.broken_skills, ["skill_c"])
        self.assertEqual(response.sandbox_readiness, ["sandbox ok"])
        self.assertEqual(response.truth_synthesis, ["truth ok"])
        self.assertEqual(response.startup_guidance, ["guidance ok"])
        self.assertEqual(response.eval_summary, "Mission evals: ok")


if __name__ == "__main__":
    unittest.main()