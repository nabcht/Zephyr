from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from skills.sandbox.scripts.sandbox import run_test_in_sandbox


class SandboxToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_test_in_sandbox_requires_code(self) -> None:
        result = await run_test_in_sandbox(description="verify this function")

        self.assertEqual(
            result,
            "❌ ERROR: Sandbox verification requires executable Python in the 'code' field, not only a description.",
        )

    async def test_run_test_in_sandbox_accepts_optional_description(self) -> None:
        completed = subprocess.CompletedProcess(args=["python"], returncode=0, stdout="ok\n", stderr="")

        with patch("skills.sandbox.scripts.sandbox._requested_backend", return_value="process"), patch(
            "skills.sandbox.scripts.sandbox._run_process_backend",
            return_value=completed,
        ):
            result = await run_test_in_sandbox(
                code="print('ok')",
                description="simple smoke test",
                skill_name="demo-skill",
            )

        self.assertIn("✅ TEST PASSED", result)
        self.assertIn("BACKEND: process", result)


if __name__ == "__main__":
    unittest.main()