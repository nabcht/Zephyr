# MCP Features Status

Updated: 2026-05-20

## Current Status

The current MCP backlog is complete and the integration is now part of the normal runtime surface.

## Current Operator Surface

- `Command Center` shows MCP enablement state, external-integration state, server configuration state, discovered tools, error metadata, degraded reasons, and recent MCP executions.
- `Guided MCP Setup` writes `.env` configuration in `single`, `indexed`, or `json` format and refreshes the live runtime configuration.
- `Refresh MCP` re-runs discovery without reloading the local skill catalog.
- Browser slash commands `/mcp` and `/mcp refresh` expose the same operational data from the chat surface.
- Mission progress snapshots can include the latest MCP execution summary.

## Implementation State

- Typed MCP contracts live in `core/mcp_contracts.py`.
- Runtime ownership for MCP lifecycle and discovery lives in `core/mcp_runtime.py`.
- Tool registration and execution are separated through `core/tool_registry.py` and `core/tool_executor.py`.
- Command-center payload assembly is split across dedicated backend services instead of being embedded in one large service object.

## Supported Configuration Formats

The current runtime accepts all of the following:

- `MCP_SERVERS_JSON`
- single-server variables such as `MCP_SERVER_COMMAND`
- indexed variables such as `MCP_SERVER_1_COMMAND`

The Command Center apply flow can generate all three formats.

## Behavior Notes

- MCP tools are only active when `MCP_ENABLED=true`, `EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED=true`, and at least one server resolves to a usable command.
- Discovery refresh keeps the last successful cached inventory visible if a later refresh fails, while still surfacing the current error metadata.
- Per-server state now carries error kind, failing tool name, last discovery timestamp, and last successful connection timestamp.
- The browser-safe verification flow covers runtime assembly and status reporting, while deeper integration regressions remain in the test suite and hybrid verification path.

## Validation Baseline

- `python -m unittest discover -s tests -p "test_mcp*.py"`
- `python -m unittest tests/test_command_center_runtime_service.py`
- `python -m unittest tests/test_command_center_verification_service.py`
- `npm run verify:command-center`
- `npm run verify:hybrid`

## Remaining Work

There is no committed MCP backlog at the moment. Future MCP work should preserve the current typed contracts, dedicated runtime ownership, cached-discovery fallback, and focused regression coverage.