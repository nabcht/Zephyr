# Zephyr Hybrid Migration Status

Updated: 2026-05-17

## What Was Done

- Extracted the shared runtime lifecycle into `core/app_runtime.py` and moved shared chat, mission, and CLI command orchestration into `core/chat_service.py`, `core/mission_service.py`, and `core/cli_commands.py`.
- Kept the CLI and hybrid web runtime on the same shared backend services instead of duplicating initialization and runtime state handling.
- Added the FastAPI backend under `backend/` with routes and services for system status, runtime actions, sessions, chat, mission execution, and command-center inspection.
- Added the React + Vite frontend under `frontend/` with the router-driven control room, typed API hooks, session restore/history loading, and SSE chat, mission, and runtime-action streaming.
- Migrated runtime actions into the web UI, including refresh, reload tools, prepare runtime, session creation, and streamed chat.
- Added a command-center web surface for former CLI-only inspection commands, including equivalents for `/skills`, `/memory`, `/mcp`, `/verify`, `/help`, and `/mission`.
- Added a root hybrid dev workflow so the FastAPI backend and Vite frontend can run together during development.
- Validated the backend changes with focused Python compile checks and validated the frontend with a successful production build.
- Browser-tested the hybrid UI for reload tools, streamed chat, session restore, prepare runtime, and mission execution.
- Cleaned the remaining tool-inventory import noise by fixing the optional DuckDuckGo search import path, removing the malformed `recursive_merge` self-import, and filtering imported helper functions out of skill registration.
- Audited the remaining legacy web header surface and migrated the web-mode execution banner into the React app.
- Added a repeatable in-process regression check for command-center inventory stability across runtime reloads and fresh session transitions.
- Added SSE mission progress streaming so the React mission workflow receives real agency milestone snapshots before the final persisted result.
- Added shared embedding-model cache preparation so `/prepare`, CLI `/prepare`, startup guidance, and the indexer all use the same app-managed local vector-model cache path.
- Deferred search runtime bootstrap and lazy embedding-model access so initial backend startup no longer waits on full semantic-search warmup.
- Declared the React hybrid app as the primary interface, with the CLI retained as the explicit fallback/operator surface.
- Added a repeatable hybrid regression suite that verifies the primary React launcher, the stable no-reload hybrid flow, command-center inventory, and mission SSE.
- Formally closed Phase 0 and Phase 1 after the regression, parity, and interface-strategy work landed.
- Added progressive runtime updates for reload and prepare, surfaced through a live runtime activity panel in the React control room.
- Formally closed Phase 2 after runtime progress streaming landed and the hybrid regression suite passed with the new runtime stream checks.
- Hardened the watcher-driven hybrid launcher so per-skill script edits no longer bounce the backend process during normal React development.
- Rebuilt the root `config.py` runtime module after placeholder drift blocked backend imports, and narrowed the watcher-driven backend reload scope to `backend/`, `core/`, `skills/`, and the root config file.
- Removed the disabled-mode Claude-Mem worker startup probe and deferred LLM HTTP client creation so cold runtime bootstrap no longer spends time on unused external integration checks or eager HTTP client setup.
- Added a rebuild path for the local semantic and keyword search stores, then refreshed the on-disk indexes so semantic search resumed using the current embedding dimension instead of falling back to grep.
- Settled deferred search warm-up during CLI `/prepare` and the web `Prepare runtime` action so explicit preparation now finishes with a ready-or-fallback search status instead of returning while search is still warming.
- Extended the hybrid runtime-action regression so `prepare` now fails validation if it completes without search-runtime details or while `search_status` is still `Warming`.
- Declared the `watchdog` Python dependency in the shared install path so incremental local-search auto-indexing no longer comes up disabled in standard setups.
- Extended the launcher regression to fail if `requirements.txt` drops the `watchdog` dependency again.
- Warmed the active inference provider during explicit prepare flows and tracked the initial background search refresh so prepare now returns only after provider warm-up and the first search refresh both settle.
- Measured the active-provider first-turn path and confirmed the remaining post-bootstrap penalty was the cold provider/search-prep path, not runtime initialization itself.
- Added a separate `inference_status` runtime snapshot field and surfaced it in the React control room so provider readiness is now visible alongside search readiness instead of being inferred indirectly.
- Extended the runtime-action regression to fail if reload or prepare status snapshots stop carrying the new inference readiness field.
- Started coordinated background inference warm-up during shared runtime initialization and reused the same warm-up task from explicit prepare flows so fresh runtime bootstrap no longer leaves provider warm-up entirely on the first live turn.
- Extended the hybrid regression to assert `/api/system/status` reports `Warming` while background provider warm-up is in flight and `Ready` after the shared warm-up task settles.
- Added provider-stage inference timing metrics to the backend system snapshot and React activity view so operator status now shows the latest warm-up time and last live provider-call time separately.
- Populated the remaining shell chrome navigation pages so `Docs`, `Support`, `Settings`, `Profile`, `Terms`, `Privacy`, and `API Docs` now render inside the control room with operator-facing content instead of acting as placeholders.
- Replaced hash-based view switching with router-managed browser paths so the control room now resolves as real URLs such as `/chat`, `/command-center`, `/posture`, and `/activity`.
- Added an immediate cold-path chat-stream initialization snapshot so streamed chat shows progress before shared runtime initialization finishes.
- Extended the hybrid regression to fail if a fresh `/api/chat/stream` request stops emitting the expected initialization snapshot first.
- Measured the real localhost chat-stream path against uvicorn and confirmed the first snapshot now arrives quickly over HTTP, not just through the in-process ASGI transport.
- Re-measured the fresh localhost `/api/chat/stream` path after background inference warm-up landed and saw the first snapshot arrive in about `7.1ms`, while total completion still took about `7974.9ms`, so active-provider latency remains the main Phase 3 first-turn bottleneck.
- Deferred the initial search refresh when a cached local search store is already present, then moved that refresh to the post-turn path so cached search availability stays immediate without re-indexing during cold runtime bootstrap.
- Re-measured the fresh localhost `/api/chat/stream` path after adding provider timing metrics and cached-index search-refresh deferral and saw the first snapshot still arrive in about `6.1ms`, while total completion took about `13259.9ms`; `inference_metrics` showed `last_warmup_ms=441.6` and `last_completion_ms=12819.3`, which confirmed the live provider call remained the dominant first-turn cost in that run.
- Added a persistent degraded inference state so failed live provider requests remain operator-visible in runtime readiness instead of reverting to generic cold status.
- Completed the separate MCP improvement backlog by modularizing MCP contracts/runtime/tool execution, surfacing typed MCP operator state and recent execution visibility, adding discovery-only refresh with cached-inventory fallback, and validating the path with fake-server integration tests plus operator documentation.

## Current Architecture

- Shared runtime layer: `core/app_runtime.py` initializes memory, tools, LLM routing, and background search/inference warm-up once for both the CLI and backend callers.
- Shared runtime layer: `core/app_runtime.py` initializes memory, tools, LLM routing, and background search/inference warm-up once for both the CLI and backend callers, while deferring the heavy initial cached-index refresh until after the first completed turn.
- Backend bridge: FastAPI under `backend/` exposes system, runtime, session, chat, mission, and command-center routes over that shared runtime.
- Primary web interface: React + Vite under `frontend/`, with router-managed `/chat`, `/command-center`, `/posture`, and `/activity` paths.
- Fallback interface: `main.py` still provides the terminal CLI, backed by the same chat, mission, memory, and runtime services.

## Current Control Room Surface

- Chat: streamed chat turns, streamed mission progress, session restore, new-session creation, code-block rendering, and copy-reply actions.
- Chat: streamed chat turns with an immediate cold-start initialization snapshot, streamed mission progress, session restore, new-session creation, code-block rendering, and copy-reply actions.
- Command Center: command map, tool catalog, typed MCP overview with discovery freshness, degraded reasons, recent MCP execution results, MCP-only refresh, durable-memory visibility, and browser-side `/verify` output.
- Posture: runtime trust signals, privacy posture, and durable-memory transparency.
- Activity: execution mode banner, startup guidance, separate inference/search readiness, provider-stage timing metrics, live reload/prepare activity, and runtime preparation output.
- Shell pages: docs, support, settings, profile, terms, privacy, and API docs now live inside the same router-managed shell as the main operator views.

## Current API Surface

- `GET /api/system/health`
- `GET /api/system/status`
- `POST /api/runtime/reload` and `POST /api/runtime/reload/stream`
- `POST /api/runtime/prepare` and `POST /api/runtime/prepare/stream`
- `POST /api/sessions` and `GET /api/sessions/{session_id}/messages`
- `POST /api/chat/turn` and `POST /api/chat/stream`
- `POST /api/missions/turn` and `POST /api/missions/stream`
- `GET /api/command-center/overview`, `POST /api/command-center/mcp/refresh`, and `POST /api/command-center/verify`

## Phase Roadmap

### Phase 0: Stabilize The Current Hybrid Foundation

Status: Completed

Goals:

- Keep the current backend and frontend contracts stable.
- Finish the last interrupted live validation path.
- Make the dev workflow predictable while the codebase is still moving.

Exit criteria:

- `npm --prefix frontend run build` passes.
- Focused backend validation passes.
- `Verify runtime` completes cleanly in the browser without a WatchFiles interruption.

### Phase 1: Reach Functional CLI Parity In The Web App

Status: Completed

Goals:

- Ensure every meaningful CLI command has a web equivalent unless it is intentionally terminal-only.
- Keep all web actions backed by shared runtime services, not duplicate frontend-only logic.
- Close any remaining legacy web-only control gaps that should exist in the React interface.

Exit criteria:

- React covers chat, missions, memory, skills, MCP status, verification, runtime actions, and session management.
- Remaining exceptions are explicitly documented, such as `/quit`.
- No critical user-facing workflow requires the CLI unless it is intentionally operator-only.

### Phase 2: Improve The Two-Brain Experience

Status: Completed

Goals:

- Make the Python brain responsible for execution, orchestration, memory, tools, and validation.
- Make the React brain responsible for visibility, control, progressive feedback, and operator workflow.
- Stream long-running actions so the web UI feels as responsive as the CLI.

Exit criteria:

- Mission execution has progressive feedback similar to chat SSE.
- The React interface exposes runtime progress instead of waiting on full request completion.
- The web UI is credible as the primary operator surface.

### Phase 3: Performance And Operational Readiness

Status: In progress

Goals:

- Reduce cold-start latency.
- Make model and search initialization more predictable.
- Prepare the hybrid app for longer-running everyday use.

Exit criteria:

- Local embedding assets are cached or prefetched.
- First interaction latency is materially lower.
- Development and validation flows are less sensitive to incidental file changes.

## Implementation Checklist

### Completed

- [x] Extract shared runtime lifecycle.
- [x] Share chat orchestration across CLI and backend.
- [x] Share mission orchestration across CLI and backend.
- [x] Add FastAPI backend routes and service layers.
- [x] Add React frontend with typed API hooks.
- [x] Add session restore and persisted session history.
- [x] Add SSE streaming chat in the React workspace.
- [x] Add runtime controls in the web UI.
- [x] Add command-center endpoints and UI for CLI-equivalent inspection features.
- [x] Add web-triggered mission execution.
- [x] Add a unified hybrid dev run command.
- [x] Clean the remaining skill import failures and tool-inventory pollution.
- [x] Audit the remaining legacy web header controls and migrate the last missing web-mode banner.
- [x] Add and pass a repeatable command-center inventory regression check.
- [x] Stream mission progress over SSE in the React workspace.
- [x] Add shared embedding-model cache preparation and persist indexer fallback downloads locally.
- [x] Reduce search warmup on the critical startup path.
- [x] Make React the primary interface and document the CLI as the fallback surface.
- [x] Add and pass a repeatable hybrid regression suite.
- [x] Narrow the watcher-driven backend reload scope to backend-relevant paths and restore the shared runtime config module.
- [x] Add a self-healing rebuild path for the local search indexes and refresh the current vector store.
- [x] Make explicit prepare flows settle deferred search warm-up before returning their final status.
- [x] Restore incremental auto-indexing in standard installs by declaring the missing `watchdog` dependency.
- [x] Warm the active inference provider and finish the initial search refresh during explicit prepare flows.
- [x] Surface inference-runtime readiness separately from search-runtime readiness in the control room.
- [x] Reduce cold streamed-chat first-snapshot latency with an immediate runtime-initialization snapshot.
- [x] Persist failed live provider requests as degraded inference readiness for operator visibility.
- [x] Start background inference warm-up during shared runtime initialization and reuse that warm-up task from explicit prepare flows.

### In Progress

- [ ] Continue tightening cold-start and first-interaction latency for longer-running daily use.

### Recently Completed

- [x] Landed the MCP hardening and modularization backlog tracked in `MCP_features_status.md`, including typed MCP contracts, dedicated runtime ownership, tool-execution separation, and typed MCP result preservation through `ToolEngine`.
- [x] Expanded command-center MCP visibility with typed server state, error kind, failing tool name, discovery freshness, degraded reason, recent MCP execution results, and a discovery-only `Refresh MCP` control.
- [x] Added fake-server MCP integration coverage for cached discovery refresh fallback, execution failure recovery, reconnect-on-execute behavior, and duplicate discovered tool-name handling.
- [x] Added operator-facing MCP documentation in `README.md` and `DASHBOARD.md`, covering configuration, cached-inventory fallback behavior, refresh usage, and troubleshooting.
- [x] Added `LocalIndexer.rebuild_indexes()` plus dimension-drift detection so stale Chroma collections can be recreated instead of staying stuck on grep fallback.
- [x] Rebuilt the local search stores from scratch and indexed `117` current files into a `373`-document semantic collection.
- [x] Confirmed the runtime-bound `search_personal_data` tool returns hybrid semantic results again for `runtime bootstrap` instead of grep-only fallback formatting.
- [x] Measured the current hybrid first-interaction path in-process and confirmed cold bootstrap, not post-init chat bookkeeping, was the remaining local latency bottleneck.
- [x] Skipped the Claude-Mem worker socket probe when external subprocess integrations are disabled.
- [x] Deferred `LLMRouter` HTTP client creation until the first actual HTTP-backed inference call.
- [x] Confirmed the measured cold runtime bootstrap dropped from about `484.5ms` to about `27.1ms`, while post-init chat orchestration stayed about `10.5ms`.
- [x] Re-ran `python verify_hybrid_workflow.py` successfully after the latency changes.
- [x] Rebuilt `config.py` from the current runtime surface after a placeholder file blocked backend imports and the shared hybrid validation path.
- [x] Switched the watcher-driven backend launcher from broad repo watching to a `watchfiles` path set covering `backend/`, `core/`, `skills/`, and the root `config.py`.
- [x] Confirmed `python verify_hybrid_workflow.py` passes again after the config recovery and narrowed backend watch scope.
- [x] Re-ran the browser path for `Verify runtime` in a stable no-reload setup.
- [x] Confirmed `POST /api/command-center/verify` returns `200 OK` from the backend.
- [x] Confirmed the React verification panel renders a completed result state instead of hanging.
- [x] Confirmed the real `SkillLoader.load()` path registers `search_web` and `merge_python_files` without import-time failures.
- [x] Confirmed imported helpers such as `dataclass` no longer leak into the tool inventory.
- [x] Migrated the remaining web-mode execution warning into the React shell.
- [x] Added `python verify_command_center_inventory.py` and verified the command-center inventory stayed stable across reload and fresh-session transitions.
- [x] Added `/api/missions/stream` and wired the React mission action to progressive SSE snapshots.
- [x] Confirmed the mission stream service yields an immediate progress snapshot before runtime initialization completes.
- [x] Confirmed the mission streaming frontend changes pass `npm --prefix frontend run build`.
- [x] Added startup guidance and `/prepare` support for the local embedding-model cache.
- [x] Confirmed the embedding cache helper flips startup guidance off once the local model marker exists.
- [x] Deferred `AppRuntime` search bootstrap so `ensure_runtime_ready()` returns before semantic search finishes warming.
- [x] Lazy-loaded the retriever embedding-model path so `ensure_search_runtime()` dropped from about `10.4s` to about `0.75s` in real measurement.
- [x] Switched `run.bat` to the hybrid React launcher and added `run-cli.bat` as the explicit CLI fallback surface.
- [x] Updated setup and README so the primary interface expects Node/npm and installs frontend dependencies.
- [x] Added `verify_hybrid_workflow.py`, `npm run verify:hybrid`, and `npm run dev:hybrid:stable`.
- [x] Confirmed the regression suite passes for frontend build, primary watcher-driven launch, stable no-reload launch, command-center inventory, and mission SSE.
- [x] Closed Phase 0 based on passing frontend build, focused backend validation, and stable browser verification of `Verify runtime`.
- [x] Closed Phase 1 based on React coverage for chat, missions, memory, skills, MCP status, verification, runtime actions, and session management, with `/quit` retained as an intentional terminal-only exception.
- [x] Added `/api/runtime/reload/stream` and `/api/runtime/prepare/stream` so runtime actions emit progressive updates instead of final-response-only JSON in the React path.
- [x] Updated the React runtime controls to show a live runtime activity log for reload and prepare.
- [x] Extended `verify_hybrid_workflow.py` so the hybrid regression suite now checks runtime action streams as well as mission SSE.
- [x] Closed Phase 2 based on mission SSE, runtime progress streaming, and a passing hybrid regression suite that now covers both stream classes.
- [x] Added `backend/dev_server.py` so the watcher-driven backend keeps its reload exclusions without relying on shell-expanded glob arguments.
- [x] Confirmed `npm run verify:hybrid` still passes with the primary watcher-driven launcher after excluding per-skill script edits from backend process reload.
- [x] Removed the retired legacy web surface so the hybrid web app is the only browser UI and the CLI is the only fallback path.
- [x] Added browser-mediated approval for sensitive tools when safety confirmation is enabled in the hybrid frontend.
- [x] Reorganized the React control room into the current Chat, Command Center, Posture, and Activity views behind router-managed navigation.
- [x] Fixed the chat textarea input and placeholder contrast in the hybrid frontend.
- [x] Updated CLI `/prepare` and the web `Prepare runtime` flow to wait for deferred search warm-up before returning the final status snapshot.
- [x] Confirmed the focused prepare probe now returns `Ready (background re-index)` instead of `Warming (search runtime loading in background)`.
- [x] Extended `verify_hybrid_workflow.py` so the runtime-action regression now asserts prepare reports search-runtime details and does not complete while `search_status` is still `Warming`.
- [x] Added `watchdog` to `requirements.txt` so `setup.bat` and manual `pip install -r requirements.txt` flows install the filesystem watcher dependency used by `LocalIndexer`.
- [x] Installed `watchdog` in the current venv and confirmed `from core.indexer import WATCHDOG_AVAILABLE` now returns `True`.
- [x] Extended `verify_hybrid_workflow.py` so the launcher regression now asserts the root requirements file still declares `watchdog`.
- [x] Measured the active OpenRouter path in-process and confirmed cold runtime init stayed about `45.8ms`, while the first real turn was about `2315.8ms` and a second warm turn was about `1511.6ms`.
- [x] Confirmed a manual provider prewarm on a fresh runtime cut the first real turn to about `1557.1ms`, which isolated the remaining penalty to provider/search preparation rather than shared runtime bootstrap.
- [x] Added active-provider warm-up through `LLMRouter.prepare_inference_runtime()` and exposed it through shared explicit prepare flows.
- [x] Tracked the pending background search refresh in `AppRuntime` so explicit prepare now waits for the first refresh to finish instead of returning while indexing still competes with the first live turn.
- [x] Re-ran the explicit CLI `/prepare` probe and measured about `11177.6ms` for the full prepare path, followed by a first live turn of about `1708.4ms` with `search_status` settled to `Ready (1 file(s) refreshed)`.
- [x] Re-ran the focused runtime-action regression successfully after the prepare-path changes.
- [x] Added `inference_status` to the backend system snapshot so runtime status now distinguishes provider readiness from search readiness.
- [x] Confirmed the backend status snapshot moves from `Cold (OpenRouter: provider runtime not warmed)` after init to `Ready (OpenRouter: provider runtime warmed)` after explicit inference warm-up.
- [x] Updated the React sidebar snapshot and Activity page to show separate inference and search readiness states.
- [x] Confirmed `npm --prefix frontend run build` passes after the readiness-surface changes.
- [x] Extended `verify_hybrid_workflow.py` so the focused runtime-action regression now asserts reload and prepare status payloads include `inference_status`.
- [x] Added coordinated background inference warm-up ownership to `AppRuntime`, so shared runtime initialization starts provider warm-up immediately and explicit prepare now reuses the in-flight task instead of duplicating it.
- [x] Added focused unit coverage in `tests/test_app_runtime.py` to assert runtime init starts inference warm-up and explicit prepare reuses the same task.
- [x] Extended `verify_hybrid_workflow.py` with a focused inference warm-up regression that asserts `/api/system/status` reports `Warming` during background provider warm-up and `Ready` after the shared task completes.
- [x] Added `inference_metrics` to the backend system snapshot and surfaced the latest warm-up and live provider-call timings in the React Activity page.
- [x] Updated the cold `/api/chat/stream` path to yield `*🔄 Initializing shared runtime…*` before awaiting runtime readiness.
- [x] Confirmed the first yielded chunk from `ChatSessionService.stream_turn()` now arrives immediately in-process (`~0.0ms`) with the new initialization snapshot content.
- [x] Re-measured the cold in-process chat SSE path and saw the first snapshot move from about `4123.0ms` to about `2076.6ms`, now carrying the initialization snapshot instead of waiting for the later thinking update.
- [x] Extended `verify_hybrid_workflow.py` with a focused chat-stream regression that asserts a fresh `/api/chat/stream` request emits the initialization snapshot first.
- [x] Measured the cold localhost `/api/chat/stream` path against a real uvicorn backend on `127.0.0.1:8011` and saw the first snapshot arrive in about `318.1ms` with `*🔄 Initializing shared runtime…*`, while total completion remained about `4743.5ms` on the active provider path.
- [x] Re-measured the fresh localhost `/api/chat/stream` path on `127.0.0.1:8012` after background inference warm-up landed and saw the first snapshot arrive in about `7.1ms`, while total completion still took about `7974.9ms` and `/api/system/status` moved from `Pending (runtime not initialized)` before the request to `Ready (OpenRouter: live request path warmed)` after completion.
- [x] Deferred the initial cached-index search refresh in `AppRuntime` when existing search documents are already on disk, and now trigger that deferred refresh after a completed chat turn instead of during cold runtime initialization.
- [x] Added focused unit coverage in `tests/test_chat_service.py` and `tests/test_app_runtime.py` for post-turn deferred refresh scheduling and cached-search refresh deferral during prepare.
- [x] Re-measured the fresh localhost `/api/chat/stream` path on `127.0.0.1:8013` after the timing-metrics and cached-search-deferral changes and saw the first snapshot arrive in about `6.1ms`, while total completion took about `13259.9ms`; the returned `inference_metrics` reported `last_warmup_ms=441.6` and `last_completion_ms=12819.3`, which localized the remaining first-turn cost to the live provider call rather than shared runtime bootstrap or cached-index refresh.
- [x] Updated `LLMRouter` so warm-up failures and failed live provider requests persist as `Degraded (...)` inference readiness instead of resetting to `Cold (...)`.
- [x] Confirmed a forced provider outage now leaves `/api/system/status` reporting `Degraded (OpenRouter: live request failed)` after a failed chat turn.
- [x] Extended `verify_hybrid_workflow.py` with a focused inference degradation regression that asserts failed live provider requests persist as degraded readiness.
- [x] Confirmed `npm --prefix frontend run build` still passes after the degraded-readiness UI update.

### Next

- [ ] Continue Phase 3 operational hardening for longer-running everyday use.
- [ ] Continue tightening cold-start and first-interaction latency for longer-running daily use.

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

1. Continue Phase 3 operational hardening for longer-running everyday use.
2. Continue tightening cold-start and first-interaction latency for longer-running daily use.

## Known Caveats

- Without an explicit prepare run, the first heavy runtime initialization can still trigger vector model download, parser startup work, and provider/search cold-path work, which delays the first response.
- MCP server tools remain optional and stay unavailable unless `MCP_ENABLED=true`, `EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED=true`, and at least one configured MCP server resolves to a working command.
- A failed MCP discovery refresh can continue showing the last successful cached inventory while also surfacing the current error state; operators should treat cached tool visibility as historical inventory, not proof that the server is currently healthy.
- The watcher-driven backend now reloads only for changes under `backend/`, `core/`, `skills/`, and the root `config.py`; per-skill script edits under `skills/*/scripts/*.py` still stay on the explicit `Reload tools` path instead of bouncing the API.
- `Verify runtime` now completes in the web UI, but mission evals are intentionally bounded to a 45-second timeout there; the full regression pass still belongs in the CLI `/verify` workflow.
- Router-managed control-room URLs now depend on SPA fallback rewrites from the frontend host; the Vite dev and preview servers handle this automatically, but custom reverse proxies must rewrite unknown UI paths to the frontend index.