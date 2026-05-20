# Zephyr Features

Zephyr is a local-first AI sidekick built around a shared Python runtime, a FastAPI bridge, and a primary React control room. The browser UI is the default interface; the CLI remains available as an operator fallback on the same runtime stack.

## Primary User Features

- Streaming chat through `/api/chat/stream`, with progressive assistant output in the browser.
- Multi-agent mission execution through `/api/missions/stream`, including live progress snapshots before the final answer is persisted.
- Browser-native slash commands for `/help`, `/skills`, `/memory`, `/mcp`, `/mcp refresh`, `/prepare`, `/session`, `/reload`, `/verify`, and `/mission <task>`.
- Session restore in the browser through `sessionStorage`, plus persisted message history in the local runtime database.
- Assistant reply rendering with fenced code-block formatting and `Copy Reply` support.

## Knowledge, Memory, And Retrieval

- Durable memory facts stored locally and reused across turns.
- Hybrid retrieval that combines semantic search and keyword search over local project content.
- Session-scoped attachments that can be uploaded, listed, removed, and retrieved as contextual excerpts during chat or mission turns.
- Attachment indexing that stays local to the active session and filters retrieval by `session_id`.
- Deferred background search refresh so cached indexes remain usable immediately while heavier refresh work happens later.

## Runtime And Operator Features

- Shared runtime lifecycle in `core/app_runtime.py` for CLI, backend services, and verification flows.
- Lightweight passive status inspection through `/api/system/status` without forcing a full heavy bootstrap path.
- Runtime `Reload tools` and `Prepare runtime` actions, both available as JSON and Server-Sent Event streams.
- Startup guidance, privacy posture, trust signals, inference readiness, search readiness, and tool counts surfaced in the UI.
- Provider timing visibility, including warm-up timing, first-token timing, and full completion timing.
- Provider payload visibility in the Activity view, including message counts, tool-schema counts, and lightweight-payload usage.

## Tooling And Automation

- Dynamic local skills loaded from `skills/` without requiring a full process restart.
- Tool inventory grouped by source: skill, built-in, MCP, and manual tools.
- Guided MCP setup in the Command Center that can write `.env` settings in `single`, `indexed`, or `json` formats.
- MCP discovery refresh without full runtime reload, with cached inventory fallback if a refresh fails after a prior successful discovery.
- Recent MCP execution summaries surfaced in both the Command Center and mission progress snapshots.

## Safety And Privacy

- Local inference support through `ollama` and `llamacpp`.
- Remote inference support through `openrouter`, surfaced explicitly in privacy posture and runtime status.
- Per-request sensitive-tool approval in the browser when `REQUIRE_CONFIRMATION=true`.
- Optional external subprocess integrations that stay disabled unless explicitly enabled.
- Sandbox-backed validation and runtime preparation flows for safer code execution and verification.

## Current Browser Surfaces

- `Chat`: conversation, mission launch, attachments, slash commands, and reply rendering.
- `Command Center`: command map, tool inventory, MCP status, durable memory, MCP configuration, and runtime verification.
- `Posture`: privacy posture, trust signals, and durable-memory transparency.
- `Activity`: startup guidance, runtime metrics, execution mode, reload/prepare activity streams, and preparation output.
- `Docs`, `Glossary`, `Support`, `Settings`, `Profile`, `Terms`, `Privacy`, and `API Docs`: in-shell operator and reference pages.

## Developer Workflow Features

- `run.bat` and `run-hybrid.bat` for the primary browser-first workflow.
- `run-cli.bat` for the CLI fallback workflow.
- `npm run dev:hybrid` for watcher-driven development and `npm run dev:hybrid:stable` for a stable no-reload backend.
- `npm run verify:command-center` for command-center inventory regression checks.
- `npm run verify:hybrid` for the broader hybrid regression flow.

For the architecture behind these features, see `docs.md`. For operator workflows, see `DASHBOARD.md`. For endpoint details, see `API_DOCS.md`.
