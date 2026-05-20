# Zephyr Documentation: Features and Architecture

Zephyr is a local-first AI sidekick built for agency rather than one-shot chat. The current hybrid app combines a React control room, a FastAPI bridge, and a shared Python runtime that owns execution, memory, tools, search, and validation.

## What Ships Today

- The primary interface is the browser-first control room started by `run.bat` or `run-hybrid.bat`.
- The CLI in `main.py` remains available through `run-cli.bat` and uses the same runtime services as the backend.
- The shared runtime in `core/app_runtime.py` is the single owner of memory, tool loading, provider warm-up, and search warm-up.
- The FastAPI bridge under `backend/` exposes stable status, runtime-action, session, chat, mission, documentation, and command-center endpoints.
- The React frontend under `frontend/` renders the current operator surfaces: `Chat`, `Command Center`, `Posture`, `Activity`, and the auxiliary documentation pages.

## Runtime Architecture

### Shared Runtime

- `AppRuntime` initializes durable memory, tool inventory, the LLM router, and background search/inference preparation exactly once.
- `ChatService` and `MissionService` share turn orchestration between CLI and backend callers.
- Search warm-up is intentionally deferred so cached indexes can stay available without blocking first-load responsiveness.

### Backend Bridge

- The backend keeps passive routes lightweight. `GET /api/system/status` reads the current snapshot without forcing a full runtime bootstrap.
- Heavy paths such as chat turns, mission turns, and explicit runtime actions initialize the runtime only when they need it.
- Documentation content is served directly from the `Docs/` folder through `/api/docs/{slug}` for the docs pages that render in the browser shell.

### React Control Room

- The browser shell is route-driven and resolves real paths such as `/chat`, `/command-center`, `/posture`, and `/activity`.
- Chat and mission turns stream over Server-Sent Events.
- Runtime reload and prepare actions also stream progress so the UI stays informative during longer operations.

## Interaction Model

### Chat And Missions

- Normal chat runs through `/api/chat/stream` and persists user and assistant turns.
- Missions run through `/api/missions/stream` and emit structured progress snapshots before the final answer is stored.
- If the browser disconnects during streaming chat, partial assistant output is not persisted.

### Browser Slash Commands

- Read-only slash commands such as `/help`, `/skills`, `/memory`, and `/mcp` return inline chat-style summaries inside the browser workspace.
- Mutating slash commands such as `/prepare`, `/reload`, `/verify`, `/session`, and `/mcp refresh` reuse the existing runtime actions and then post a local summary message.
- `/mission <task>` launches the multi-agent mission flow; `/quit` remains terminal-only.

### Session Attachments

- The browser supports upload, list, and delete operations for session-scoped attachments.
- Attachments are stored under `temp_core/attachments`, indexed locally, and filtered by `session_id` during retrieval.
- Current attachment support requires extractable text content and enforces a 10 MB per-file limit.

### Memory And Search

- Session history lives in the local SQLite database.
- Durable facts live in the local memory layer and are added to the system prompt when available.
- Hybrid retrieval combines vector search and keyword search over the local workspace and active session attachments.

## Operator Visibility And Control

### Command Center

- Shows the command map between CLI behavior and browser actions.
- Lists loaded tools grouped by source label.
- Surfaces MCP state, discovered tools, degraded reasons, recent executions, and guided MCP setup.
- Runs a browser-safe verification workflow that reports skill integrity, sandbox readiness, truth-synthesis health, startup guidance, and a bounded eval summary.

### Posture And Activity

- `Posture` focuses on privacy posture, trust signals, and durable-memory transparency.
- `Activity` focuses on runtime metrics, startup guidance, execution mode, and live runtime-action logs.
- System status now separates `inference_status` from `search_status` and includes timing and payload metrics for operator debugging.

## Common Environment Settings

| Variable | Purpose | Default |
| --- | --- | --- |
| `LLM_PROVIDER` | Select `ollama`, `openrouter`, or `llamacpp`. | `ollama` |
| `OLLAMA_MODEL` | Active Ollama model name. | `llama3.1:8b` |
| `OPENROUTER_MODEL` | Active OpenRouter model identifier. | `openai/gpt-oss-120b:free` |
| `REQUIRE_CONFIRMATION` | Require per-request approval for sensitive browser actions. | `false` |
| `MCP_ENABLED` | Enable MCP server integration. | `false` |
| `EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED` | Allow subprocess-backed integrations such as MCP or Claude-Mem worker startup. | `false` |
| `DB_PATH` | Local SQLite runtime database path. | `./data/zephyr.db` |
| `VECTOR_STORE_DIR` | Local semantic index path. | `./data/vector_store` |
| `SESSION_ATTACHMENTS_DIR` | Local storage path for uploaded session attachments. | `./temp_core/attachments` |
| `SEARCH_DIR` | Root path indexed for workspace retrieval. | repository root |

## Development And Validation

- `npm run dev:hybrid` starts the watcher-driven backend plus the Vite frontend.
- `npm run dev:hybrid:stable` starts a stable no-reload backend plus the Vite frontend.
- `npm run build:frontend` validates the frontend production build.
- `npm run verify:command-center` checks command-center inventory stability across reloads and fresh sessions.
- `npm run verify:hybrid` runs the broader hybrid regression flow.

## Related Docs

- `Features.md` for the current user-facing feature inventory.
- `DASHBOARD.md` for the control-room page map.
- `API_DOCS.md` for endpoint details.
- `glossary.md` for shared terminology.

For shared terminology, see [glossary.md](./glossary.md). For endpoint details, see [API_DOCS.md](./API_DOCS.md).