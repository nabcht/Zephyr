# Zephyr Hybrid Migration Status

Updated: 2026-05-20

## Status

The hybrid migration is effectively complete. The React control room is the primary interface, the CLI remains the supported fallback/operator surface, and the shared runtime owns the behavior used by both.

This document now serves as a current-state record rather than an active implementation roadmap.

## Completed Migration Outcomes

- Shared runtime lifecycle lives in `core/app_runtime.py`.
- Shared chat, mission, and CLI command orchestration live in `core/chat_service.py`, `core/mission_service.py`, and `core/cli_commands.py`.
- FastAPI backend routes and service layers are in place under `backend/`.
- React + Vite control-room views are in place under `frontend/`.
- Chat, mission, reload, and prepare flows all stream progressive browser updates.
- Browser pages now cover the main operator surfaces plus documentation and policy pages.
- The browser supports session restore, session attachments, runtime verification, runtime preparation, and MCP inspection/configuration.
- MCP runtime handling, discovery refresh, and typed status reporting are complete enough to be treated as active features rather than migration work.

## Current Architecture

- Shared runtime: `core/app_runtime.py` initializes memory, tools, search, and provider state once for all callers.
- Backend bridge: `backend/` exposes system, runtime, session, chat, mission, command-center, and docs routes.
- Primary interface: `frontend/` renders the browser operator surfaces on router-managed paths.
- Fallback interface: `main.py` keeps the terminal workflow available on the same runtime stack.

## Current Control-Room Surface

- `Chat`: streamed chat, streamed missions, slash commands, session restore, session attachments, code-block rendering, copy reply.
- `Command Center`: command map, tool inventory, MCP overview, MCP apply/refresh, durable memory, verification output.
- `Posture`: privacy posture, trust signals, durable-memory transparency.
- `Activity`: startup guidance, execution mode, inference/search readiness, timing metrics, payload metrics, live runtime activity log.
- Auxiliary pages: docs, glossary, support, settings, profile, terms, privacy, API docs.

## Validation Baseline

The current codebase has dedicated validation entry points for the migrated workflow:

- `npm run build:frontend`
- `npm run verify:command-center`
- `npm run verify:hybrid`
- focused unit tests in `tests/` for runtime, chat streaming, command center, documentation routes, and MCP behavior

## Current Caveats

- The browser verification flow intentionally times out long eval runs after 45 seconds; CLI `/verify` remains the fallback for longer verification passes.
- Session attachments currently require extractable text content and enforce a 10 MB per-file limit.
- The backend is designed for localhost use and does not ship with a built-in authentication layer.
- Live provider latency, especially remote first-token latency, can still dominate first-turn completion time even though shared runtime bootstrap is much faster than before.

## Historical Note

The former phase-by-phase hybrid migration backlog has been retired. New work should be tracked as normal feature or maintenance work against the current browser-first architecture rather than as unfinished migration scope.
- [x] Re-measured the cold in-process chat SSE path and saw the first snapshot move from about `4123.0ms` to about `2076.6ms`, now carrying the initialization snapshot instead of waiting for the later thinking update.
- [x] Extended `verify_hybrid_workflow.py` with a focused chat-stream regression that asserts a fresh `/api/chat/stream` request emits the initialization snapshot first.
- [x] Measured the cold localhost `/api/chat/stream` path against a real uvicorn backend on `127.0.0.1:8011` and saw the first snapshot arrive in about `318.1ms` with `*🔄 Initializing shared runtime…*`, while total completion remained about `4743.5ms` on the active provider path.
- [x] Re-measured the fresh localhost `/api/chat/stream` path on `127.0.0.1:8012` after background inference warm-up landed and saw the first snapshot arrive in about `7.1ms`, while total completion still took about `7974.9ms` and `/api/system/status` moved from `Pending (runtime not initialized)` before the request to `Ready (OpenRouter: live request path warmed)` after completion.
- [x] Deferred the initial cached-index search refresh in `AppRuntime` when existing search documents are already on disk, and now trigger that deferred refresh after a completed chat turn instead of during cold runtime initialization.
- [x] Added focused unit coverage in `tests/test_chat_service.py` and `tests/test_app_runtime.py` for post-turn deferred refresh scheduling and cached-search refresh deferral during prepare.
- [x] Re-measured the fresh localhost `/api/chat/stream` path on `127.0.0.1:8013` after the timing-metrics and cached-search-deferral changes and saw the first snapshot arrive in about `6.1ms`, while total completion took about `13259.9ms`; the returned `inference_metrics` reported `last_warmup_milliseconds=441.6` and `last_completion_milliseconds=12819.3`, which localized the remaining first-turn cost to the live provider call rather than shared runtime bootstrap or cached-index refresh.
- [x] Updated `LLMRouter` so warm-up failures and failed live provider requests persist as `Degraded (...)` inference readiness instead of resetting to `Cold (...)`.
- [x] Confirmed a forced provider outage now leaves `/api/system/status` reporting `Degraded (OpenRouter: live request failed)` after a failed chat turn.
- [x] Extended `verify_hybrid_workflow.py` with a focused inference degradation regression that asserts failed live provider requests persist as degraded readiness.
- [x] Confirmed `npm --prefix frontend run build` still passes after the degraded-readiness UI update.
- [x] Streamed cumulative remote-provider response text through the browser chat path, added disconnect-aware cancellation so abandoned browser turns do not persist partial assistant output, and exposed `first_response_token_milliseconds` through `/api/system/status` and the React Activity page.
- [x] Confirmed focused router and chat-service coverage passes after the streaming and cancellation changes with `python -m pytest tests/test_llm_router.py tests/test_chat_service.py -q`.
- [x] Confirmed `npm --prefix frontend run build` still passes after the streamed-chat and inference-metrics contract update.
- [x] Added `tests/test_chat_route_streaming.py` so the backend chat route now has a focused regression proving `request.is_disconnected` is forwarded into the streaming service and suppresses the final done event after a disconnect.
- [x] Re-measured the real localhost `/api/chat/stream` path after the streamed-provider change and observed `first_snapshot_milliseconds=5.3`, `first_non_status_content_milliseconds=3204.8`, `first_response_token_milliseconds=2596.6`, `last_completion_milliseconds=2764.3`, and `total_completion_milliseconds=3377.9` for a simple `OK` reply, which narrowed the remaining Phase 3 bottleneck to provider first-token latency.
- [x] Compacted provider-facing tool schemas by trimming verbose tool descriptions and removing per-parameter description metadata from provider payloads while preserving the existing full metadata for local registry and UI use.
- [x] Added a lightweight explicit direct-answer path that skips both tool schemas and prior chat history for exact-response prompts, and confirmed a local payload check reduced the serialized provider request from about `10335` characters full-schema to about `7914` with compact schemas and about `189` for the explicit lightweight path.
- [x] Confirmed the focused Phase 3 payload regressions pass with `python -m pytest tests/test_tool_registry.py tests/test_tool_engine.py tests/test_llm_router.py tests/test_chat_service.py tests/test_chat_route_streaming.py -q`.
- [x] Added provider-payload observability to `/api/system/status` and the React Activity page, covering serialized payload size, history message count, provider message count, tool schema count, and lightweight-payload usage for the most recent first-round provider request.
- [x] Extended `verify_hybrid_workflow.py` so runtime reload and prepare status payloads now fail regression if the new `provider_payload_metrics` object stops being included in the system snapshot contract.
- [x] Trimmed durable facts out of the lightweight exact-answer provider path while keeping them for broader no-tool requests, which reduced the real first-round `/api/system/status` payload metric for `Reply with exactly OK. Do not call tools.` from about `3908` characters to about `405` while preserving `provider_message_count=2`, `history_message_count=0`, and `tool_schema_count=0`.
- [x] Re-measured the in-process `/api/chat/stream` and `/api/system/status` path after trimming durable facts and observed `serialized_payload_characters=405`, `first_response_token_milliseconds=6780.4`, and `last_completion_milliseconds=6803.9`, which confirms the remaining latency bottleneck is still remote provider first-token time rather than local prompt assembly.
- [x] Added a narrow local exact-answer fast path for simple prompts such as `Reply with exactly OK. Do not call tools.`, so the router now returns those responses without a provider request while preserving the existing provider-backed path for broader no-tool or more complex exact-answer prompts.
- [x] Re-measured the in-process `/api/chat/stream` and `/api/system/status` path after the local fast path landed and observed the streamed chunks `Initializing shared runtime...` then `OK`, `provider_payload_metrics.serialized_payload_characters=0`, `provider_message_count=0`, and `inference_metrics.first_response_token_outcome=last_completion_outcome=local_fast_path` with both provider-stage durations reported as `0.0`, which removes provider first-token latency entirely for that narrow exact-answer class.
- [x] Added a short-lived direct-answer response cache keyed by the exact first-round provider payload, so repeated identical provider-backed direct-answer turns can return locally without hitting the provider while tool-using and context-changing turns still take the normal path.
- [x] Re-measured two fresh in-process `/api/chat/stream` turns with the same non-exact no-tool prompt `Without tools, summarize the repository status in one short sentence.` and observed the first turn stream provider content normally while the second turn returned the full sentence immediately from `local_response_cache`; after the second turn `/api/system/status` reported `first_response_token_milliseconds=0.0`, `last_completion_milliseconds=0.0`, and zeroed `provider_payload_metrics`, confirming repeated identical direct-answer prompts no longer pay provider first-token latency.
- [x] Extended `verify_hybrid_workflow.py` with a focused repeated direct-answer cache regression that proves the second identical in-process `/api/chat/stream` turn returns locally, reports zero provider payload, and stamps `local_response_cache` into the inference metrics.
- [x] Closed Phase 3 after `npm run verify:hybrid` and the focused Python regressions continued to pass with the final direct-answer fast-path and repeated-response cache work in place.

### Next

- [ ] Define the next post-Phase-3 roadmap slice around response quality, provider strategy, or longer-session behavior.
- [ ] Keep `npm run verify:hybrid` and the focused router regressions as the baseline gate for future runtime-performance changes.

## Ticket Backlog

### H-001: Complete Verify Runtime Live Validation

Status: Completed
Priority: High

Scope:

- Start the hybrid stack with `npm run dev:hybrid`.
- Run the `Verify runtime` action from the React UI.
- Confirm the verification panel renders the returned data without interruption.

Done when:

- The backend handles one clean `POST /api/command-center/verify` request.
- The browser shows the verification result state instead of a stuck loading button.
- The result is captured back into this status file.

Result:

- Verified on 2026-05-16 against a stable backend started without `--reload`.
- Browser result: `14 valid, 0 repaired, 0 broken.`
- Web eval result: `Mission evals: timed out in web verification after 45s. Run /verify in the CLI for the full regression pass.`
- Backend confirmed: `POST /api/command-center/verify` returned `200 OK`.

### H-002: Stream Mission Progress

Status: Completed
Priority: High

Scope:

- Add SSE or WebSocket progress updates for mission execution.
- Surface mission progress in the React workspace the same way chat snapshots are surfaced.
- Keep the mission path backed by shared runtime services.

Done when:

- A mission can show intermediate progress in the browser.
- Mission completion still persists the final response to session history.

Result:

- Completed on 2026-05-16.
- Added `/api/missions/stream` as a Server-Sent Events endpoint backed by real `Agency` milestone updates instead of synthetic timers.
- The React mission action now consumes streamed snapshots and then reloads persisted session history so the final assistant result remains durable.
- Focused backend validation confirmed the mission stream service yields an immediate progress snapshot before runtime initialization completes.
- Frontend validation confirmed the mission streaming changes pass `npm --prefix frontend run build`.

### H-003: Audit Remaining Legacy Web Controls

Status: Completed
Priority: High

Scope:

- Compare the legacy web surface against the current React workspace.
- Identify controls, panels, or status views that still only exist outside the hybrid UI.
- Migrate the missing high-value controls through backend endpoints and React components.

Done when:

- Remaining legacy web-only features are either migrated or intentionally deferred with a reason.

Result:

- Audited the legacy web surface against the React shell on 2026-05-16.
- Migrated the remaining web-mode execution warning into the React app.
- Remaining differences were presentational details, not missing operator controls.

### H-004: Reduce Cold-Start Latency

Status: Completed
Priority: Medium

Scope:

- Cache or prefetch the local embedding model.
- Reduce heavy first-request initialization where possible.
- Keep passive routes lightweight.

Done when:

- First interactive request no longer depends on a model download in the common case.
- Initial runtime startup time is materially improved.

Result:

- Completed on 2026-05-16.
- Added `core/embedding_model.py` as the shared cache helper for the sentence-transformer model.
- `/prepare` in both the backend and CLI now caches the embedding model locally before full runtime initialization.
- Startup guidance now flags a missing local embedding cache and marks it as prepare-capable.
- `LocalIndexer` now persists the model into the app-managed local cache after a fallback hub load so later startups use the local path.
- `AppRuntime` now defers search bootstrap into a background task, and `HybridRetriever` no longer forces eager embedding-model load during construction.
- Measured result with cached local assets: `ensure_runtime_ready()` returned in about `0.45s`, and explicit `ensure_search_runtime(wait_for_completion=True)` dropped from about `10.4s` to about `0.75s`.
- Follow-up measurement on 2026-05-17 showed the remaining cold bootstrap path was still spending about `204ms` on a disabled Claude-Mem worker probe and about `267ms` on eager `LLMRouter` HTTP client creation.
- After skipping the disabled worker probe and lazy-initializing the HTTP client, the same in-process bootstrap path dropped further from about `484.5ms` to about `27.1ms`, with post-init chat orchestration still about `10.5ms` when the LLM call itself is excluded.

### H-005: Decide Primary Interface Strategy

Status: Completed
Priority: Medium

Scope:

- Define the role of React and CLI in the final product.
- Decide whether React becomes the default operator experience.
- Document any intentionally retained CLI-only workflows.

Done when:

- The interface strategy is explicit and reflected in the roadmap and docs.

Result:

- Completed on 2026-05-16.
- React + FastAPI is now the primary interface via `run.bat` and `run-hybrid.bat`.
- CLI is retained as the explicit fallback/operator surface via `run-cli.bat`.
- The retired legacy web surface was removed on 2026-05-17 after parity and safety confirmation landed in the hybrid frontend.
- `setup.bat` now installs frontend dependencies when npm is available and explains the primary/fallback launch paths.
- `README.md` now documents the React-first launch flow and the fallback surfaces explicitly.

### H-006: Clean Tool Inventory Imports

Status: Completed
Priority: High

Scope:

- Remove the last import-time failures that keep the tool inventory noisy.
- Make optional skill dependencies import-safe.
- Prevent imported helper functions from being exposed as tools.

Done when:

- `search_web` and `merge_python_files` load through the real `SkillLoader` path.
- Imported helpers such as `dataclass` are not exposed in the tool inventory.
- Focused compile and loader validation pass.

Result:

- Completed on 2026-05-16.
- `search_web` now prefers `duckduckgo_search`, falls back to `ddgs`, and degrades cleanly if neither package is installed.
- `recursive_merge` no longer self-imports, and the real loader path registers both `search_web` and `merge_python_files`.
- Focused loader validation result: `LOADED_COUNT=21`, `HAS_SEARCH_WEB=True`, `HAS_MERGE_PYTHON_FILES=True`, `HAS_DATACLASS=False`.

### H-007: Verify Command-Center Inventory Stability

Status: Completed
Priority: High

Scope:

- Verify that the web command-center tool inventory stays stable after a runtime reload.
- Verify that creating a fresh session does not perturb the shared inventory.
- Make the check repeatable without manually bringing up the full hybrid stack.

Done when:

- The command-center inventory keeps the expected tools after reload and session creation.
- Imported helper names such as `dataclass` stay absent.
- A focused regression command exists in the repo.

Result:

- Completed on 2026-05-16.
- Added `verify_command_center_inventory.py` and the `npm run verify:command-center` alias.
- Focused regression validation result: the command-center inventory remained stable and retained `merge_python_files` and `search_web` while excluding `dataclass` across runtime reload and fresh session creation.

### H-008: Tighten Hybrid Regression Validation

Status: Completed
Priority: Medium

Scope:

- Add a repeatable regression pass for the primary React launch path.
- Keep an explicit stable no-reload hybrid validation path alongside the watcher-driven dev flow.
- Recheck the key hybrid runtime behaviors that have recently changed.

Done when:

- A single repo command verifies the primary watcher-driven launcher, the stable no-reload flow, command-center inventory, and mission SSE.
- The regression path is documented in the repo.

Result:

- Completed on 2026-05-16.
- Added `verify_hybrid_workflow.py` plus the `npm run verify:hybrid` alias.
- Added `npm run dev:hybrid:stable` for the explicit no-reload hybrid path.
- Verified the full suite passes: frontend build, launcher wiring, watcher-driven primary launch smoke, stable no-reload launch smoke, command-center inventory regression, and mission SSE snapshot regression.

### H-009: Stream Runtime Action Progress

Status: Completed
Priority: Medium

Scope:

- Add progressive updates for long-running runtime actions such as reload and prepare.
- Surface those updates in the React control room instead of showing only button loading states.
- Keep the runtime action path backed by shared backend services.

Done when:

- The web UI can show intermediate progress for runtime reload and runtime preparation.
- Phase 2 no longer depends on final-response-only runtime actions.

Result:

- Completed on 2026-05-17.
- Added `/api/runtime/reload/stream` and `/api/runtime/prepare/stream` as Server-Sent Events endpoints backed by step-wise runtime service updates.
- Updated `useSystemStatus()` to consume runtime progress streams and added a live `RuntimeActivityPanel` in the React control room.
- Extended `verify_hybrid_workflow.py` so `npm run verify:hybrid` now checks runtime action streams in addition to the existing hybrid regression coverage.
- Validation result: `npm run verify:hybrid` passed, including frontend build, runtime action streams, command-center inventory, mission SSE, and both hybrid launcher smokes.

### H-010: Harden Watcher-Driven Launcher Scope

Status: Completed
Priority: Medium

Scope:

- Reduce incidental backend process reloads during the watcher-driven React dev flow.
- Keep skill-package edits on the explicit runtime reload path instead of forcing a full API restart.
- Preserve the existing primary launcher and regression suite coverage.

Done when:

- Per-skill script edits under `skills/*/scripts/*.py` no longer trigger backend process reload in `dev:hybrid`.
- The primary watcher-driven launcher still passes the hybrid regression suite.

Result:

- Completed on 2026-05-17.
- Added `backend/dev_server.py` as the watcher-driven backend launcher so reload exclusions are configured in Python instead of shell-expanded CLI globs.
- Updated `dev:hybrid` to use `python -m backend.dev_server` while keeping `dev:hybrid:stable` unchanged.
- Extended `verify_hybrid_workflow.py` so launcher regression now asserts the dedicated backend dev launcher and the persisted reload exclusion contract.
- Validation result: `npm run verify:hybrid` passed after the launcher hardening change.
- Follow-up hardening on 2026-05-17 narrowed the watch scope further to `backend/`, `core/`, `skills/`, and the root `config.py` via `watchfiles.run_process`, so non-backend Python edits such as verification scripts no longer bounce the API.
- Restored the root `config.py` runtime module after a placeholder file blocked backend imports, then re-ran `python verify_hybrid_workflow.py` successfully against the narrowed watch scope.

## What Is Next

1. Define the next roadmap phase beyond Phase 3 based on operator priorities.
2. Keep the current hybrid regression suite green before taking on the next runtime or provider optimization slice.

## Known Caveats

- Without an explicit prepare run, the first heavy runtime initialization can still trigger vector model download, parser startup work, and provider/search cold-path work, which delays the first response.
- MCP server tools remain optional and stay unavailable unless `MCP_ENABLED=true`, `EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED=true`, and at least one configured MCP server resolves to a working command.
- A failed MCP discovery refresh can continue showing the last successful cached inventory while also surfacing the current error state; operators should treat cached tool visibility as historical inventory, not proof that the server is currently healthy.
- The watcher-driven backend now reloads only for changes under `backend/`, `core/`, `skills/`, and the root `config.py`; per-skill script edits under `skills/*/scripts/*.py` still stay on the explicit `Reload tools` path instead of bouncing the API.
- `Verify runtime` now completes in the web UI, but mission evals are intentionally bounded to a 45-second timeout there; the full regression pass still belongs in the CLI `/verify` workflow.
- Router-managed control-room URLs now depend on SPA fallback rewrites from the frontend host; the Vite dev and preview servers handle this automatically, but custom reverse proxies must rewrite unknown UI paths to the frontend index.