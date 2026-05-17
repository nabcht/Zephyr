# MCP Features Status

Updated: 2026-05-17

## Current Status

Overall status: The current MCP improvement backlog is complete.

- Core MCP config, contracts, client invocation, runtime ownership, tool execution, tool registry, and command-center runtime assembly are now split into dedicated modules.
- Command-center runtime verification and status-line assembly are now split out of the main command-center service.
- Command-center MCP status now exposes typed server state and error metadata instead of only a flattened error string.
- MCP operator status now exposes discovery freshness, last successful connection timestamps, and degraded reasons in both web and CLI surfaces.
- MCP client calls now enforce per-server connection, discovery, and tool timeouts with bounded retries and linear backoff.
- MCP discovery now has an explicit refresh path and cached-inventory fallback semantics in CLI and command-center surfaces.
- Typed MCP execution results now survive the `ToolEngine`/`ToolExecutor` layer and surface recent structured MCP execution metadata in mission snapshots and the web command-center.
- Fake-server MCP integration coverage now exercises cached discovery refresh fallback, execution failure recovery, reconnect-on-execute behavior, and duplicate discovered tool-name handling through the real runtime/tool-engine path.
- The hybrid workflow currently passes end to end after the latest MCP-related refactors and supporting hardening work.
- Mission-stream regression coverage now asserts sandbox and review status sections instead of only checking for a generic snapshot.
- The previously open operator documentation gap is now closed in `README.md` and `DASHBOARD.md`.

## What Was Done

- [x] Added typed MCP contracts in `core/mcp_contracts.py` for server settings, tool specs, server status, tool results, and typed errors.
- [x] Normalized environment-driven MCP config so `config.get_mcp_server_configs()` returns typed `MCPServerSettings` values.
- [x] Updated `core/mcp_client.py` to use structured invocation results and typed MCP failures while preserving string-return compatibility for current callers.
- [x] Added `core/mcp_runtime.py` so MCP client lifecycle, discovery, status reporting, and memory/archive client propagation are owned outside `ToolEngine`.
- [x] Split tool execution and approval policy into `core/tool_executor.py`.
- [x] Split tool registration and schema generation into `core/tool_registry.py`.
- [x] Reduced `core/tool_engine.py` to composition of registry, executor, and MCP runtime concerns.
- [x] De-duplicated the non-streaming tool-call loop in `core/llm.py` across CLI and GUI chat paths.
- [x] Extracted command-center tool and MCP runtime assembly into `backend/services/command_center_runtime_service.py`.
- [x] Extracted command-center verification response assembly and eval/status helpers into `backend/services/command_center_verification_service.py`.
- [x] Surfaced typed MCP operator metadata in the command-center MCP view, including server state, error kind, and failing tool name.
- [x] Surfaced MCP discovery freshness, last successful connection timestamps, and degraded reasons through MCP status contracts, CLI status output, and the command-center view.
- [x] Added per-server MCP connection, discovery, and tool timeouts plus bounded retries and linear backoff in `core/mcp_client.py` and `core/mcp_contracts.py`.
- [x] Added explicit MCP discovery refresh controls plus cached-inventory fallback semantics in `core/mcp_runtime.py`, `core/tool_engine.py`, CLI commands, command-center routes, and the React command-center panel.
- [x] Preserved typed MCP tool results through `core/tool_engine.py` / `core/tool_executor.py` and surfaced recent MCP execution metadata in command-center payloads, the React operator view, and mission progress snapshots.
- [x] Added fake-server MCP integration tests that cover discovery refresh fallback, execution failure recovery, reconnect behavior, and duplicate tool-name handling end to end.
- [x] Added operator documentation for MCP configuration, refresh behavior, cached-inventory fallback, and troubleshooting in `README.md` and `DASHBOARD.md`.
- [x] Hardened `run_test_in_sandbox` so missing `code` and stray model-supplied kwargs such as `description` and `skill_name` no longer crash sandbox verification.
- [x] Hardened `core/indexer.py` against Whoosh writer lock contention during watcher delete processing.
- [x] Expanded mission-stream regression coverage for initial snapshot structure and sandbox pass/fail snapshot rendering.
- [x] Added focused tests for MCP contracts, runtime, tool execution, tool registry, shared LLM loop, sandbox tool handling, command-center runtime assembly, command-center verification assembly, mission-stream snapshots, and indexer lock handling.
- [x] Revalidated command-center inventory and the full hybrid workflow after the refactors.

## Plan

### Milestone 1: Typed MCP Foundation

Status: Completed

Goals:

- Introduce typed MCP config and runtime contracts.
- Preserve current behavior while removing dict-only MCP state flow.
- Lock the new contract behavior behind focused regression tests.

Exit criteria:

- `config.get_mcp_server_configs()` returns typed values.
- MCP contract and invocation tests pass.

### Milestone 2: MCP Runtime Ownership

Status: Completed

Goals:

- Remove MCP lifecycle and discovery ownership from `ToolEngine`.
- Centralize discovery, status reporting, and shutdown behind a dedicated runtime manager.

Exit criteria:

- `core/mcp_runtime.py` owns configured client lifecycle.
- Command-center inventory regression remains stable.

### Milestone 3: Tooling Modularization Around MCP

Status: Completed

Goals:

- Separate tool registry and tool execution/policy from MCP runtime concerns.
- Make tool registration, schema generation, execution, and approval independently testable.

Exit criteria:

- `ToolExecutor` owns execution and approval behavior.
- `ToolRegistry` owns tool storage and schema generation.
- Focused tool-engine and tool-registry tests pass.

### Milestone 4: Shared LLM Tool-Call Orchestration

Status: Completed

Goals:

- Unify the non-streaming tool loop used by CLI and GUI chat flows.
- Preserve current user-facing behavior while removing duplicated control flow.

Exit criteria:

- Focused LLM router tests pass.
- Hybrid workflow regression still passes.

### Milestone 5: Runtime Hardening Around Mission, Sandbox, and Search

Status: Completed

Goals:

- Stop model-generated tool argument drift from surfacing as raw `TypeError`s.
- Prevent watcher delete processing from crashing on transient Whoosh lock contention.

Exit criteria:

- Sandbox tool tests pass.
- Indexer locking tests pass.
- Hybrid workflow regression passes after the fixes.

### Milestone 6: Remaining MCP Feature Hardening

Status: Completed

Goals:

- Improve resilience and observability for MCP discovery and tool execution.
- Surface richer MCP state to operator-facing views.
- Expand integration coverage beyond the current focused unit slices.

Exit criteria:

- Typed MCP failure and state information is surfaced beyond string normalization.
- Per-server timeout, retry, and degraded-state policy exists.
- Discovery freshness and degraded reason are visible in operator surfaces.
- Fake-server integration tests cover discovery, failure, and recovery paths.

## What Remains

- No open items remain in the current MCP backlog.

## Recent Validation

- `./venv/Scripts/python.exe -m unittest discover -s tests -p "test_mcp*.py"`
- `./venv/Scripts/python.exe -m unittest discover -s tests -p "test_tool_engine.py"`
- `./venv/Scripts/python.exe -m unittest discover -s tests -p "test_tool_registry.py"`
- `./venv/Scripts/python.exe -m unittest discover -s tests -p "test_llm_router.py"`
- `./venv/Scripts/python.exe -m unittest discover -s tests -p "test_sandbox_tool.py"`
- `./venv/Scripts/python.exe -m unittest tests/test_indexer_locking.py`
- `./venv/Scripts/python.exe -m unittest discover -s tests -p "test_command_center_runtime_service.py"`
- `./venv/Scripts/python.exe -m unittest discover -s tests -p "test_command_center_verification_service.py"`
- `./venv/Scripts/python.exe -m unittest discover -s tests -p "test_mission_stream_snapshots.py"`
- `./venv/Scripts/python.exe -m unittest tests.test_command_center_runtime_service tests.test_mission_stream_snapshots`
- `./venv/Scripts/python.exe -m unittest discover -s tests -p "test_mcp_contracts.py"`
- `./venv/Scripts/python.exe -m unittest tests.test_mcp_runtime tests.test_tool_engine tests.test_mcp_integration`
- `npm --prefix frontend run build`
- `./venv/Scripts/python.exe verify_command_center_inventory.py`
- `./venv/Scripts/python.exe verify_hybrid_workflow.py`

## Current Notes

- The MCP foundation is now modular enough to iterate safely without coupling every change back through `ToolEngine`.
- The current baseline is stable, with configuration, resilience, operator visibility, integration coverage, and operator documentation all landed.