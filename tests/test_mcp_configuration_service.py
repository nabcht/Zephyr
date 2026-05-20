from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import config
from backend.schemas.command_center import MCPConfigurationApplyRequest, MCPConfiguredServerRequest
from backend.services.mcp_configuration_service import MCPConfigurationService


class MCPConfigurationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.env_path = Path(self._tempdir.name) / ".env"
        self.service = MCPConfigurationService(env_path=self.env_path)

    def tearDown(self) -> None:
        self._tempdir.cleanup()

    def test_apply_replaces_previous_mcp_keys_with_indexed_servers(self) -> None:
        self.env_path.write_text(
            "LLM_PROVIDER=ollama\nMCP_SERVER_COMMAND=python\nMCP_SERVER_NAME=stale\nMCP_TOOL_PREFIX=mcp\n",
            encoding="utf-8",
        )
        payload = MCPConfigurationApplyRequest(
            format="indexed",
            servers=[
                MCPConfiguredServerRequest(
                    name="Remote",
                    command="npx",
                    args=["-y", "mcp-remote", "https://example.com/mcp"],
                    env={"API_KEY": "demo"},
                    tool_prefix="remote",
                ),
                MCPConfiguredServerRequest(
                    name="Archive",
                    command="python",
                    args=["-m", "archive_mcp"],
                    cwd="./tools/archive",
                ),
            ],
        )

        with patch.dict(os.environ, {"MCP_SERVER_COMMAND": "stale"}, clear=False), patch.object(config, "MCP_ENABLED", False), patch.object(
            config,
            "EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED",
            False,
        ):
            result = self.service.apply(payload)

            self.assertEqual(result.server_count, 2)
            self.assertEqual(os.environ["MCP_SERVER_1_NAME"], "Remote")
            self.assertEqual(os.environ["MCP_SERVER_2_COMMAND"], "python")
            self.assertNotIn("MCP_SERVER_COMMAND", os.environ)
            self.assertTrue(config.MCP_ENABLED)
            self.assertTrue(config.EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED)

        content = self.env_path.read_text(encoding="utf-8")
        self.assertIn("LLM_PROVIDER=ollama", content)
        self.assertIn("MCP_SERVER_1_NAME=Remote", content)
        self.assertIn("MCP_SERVER_1_ENV_JSON={\"API_KEY\":\"demo\"}", content)
        self.assertIn("MCP_SERVER_2_CWD=./tools/archive", content)
        self.assertNotIn("MCP_SERVER_COMMAND=python", content)

    def test_apply_json_format_writes_single_json_assignment(self) -> None:
        payload = MCPConfigurationApplyRequest(
            format="json",
            servers=[
                MCPConfiguredServerRequest(
                    name="Remote",
                    command="uvx",
                    args=["mcp-remote", "https://example.com/mcp"],
                    env={"TOKEN": "secret"},
                )
            ],
        )

        result = self.service.apply(payload)

        self.assertIn("MCP_SERVERS_JSON=[{\"name\":\"Remote\"", result.env_block)
        self.assertNotIn("MCP_SERVER_COMMAND", result.env_block)


if __name__ == "__main__":
    unittest.main()