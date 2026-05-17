# uZephyr Dashboard

This document describes the current React control room shipped in `frontend/` and backed by the FastAPI bridge in `backend/`.

## Entry Point

- Launch with `run.bat` or `run-hybrid.bat`.
- Backend default address: `http://127.0.0.1:8000`
- Frontend default address: `http://127.0.0.1:5173`
- Primary control-room paths: `/chat`, `/command-center`, `/posture`, `/activity`

## Global Shell

The shared shell in `frontend/src/components/AppShell.tsx` provides:

- Left runtime snapshot with provider, search status, model, and current session id
- Top navigation for `Chat`, `Command Center`, `Posture`, and `Activity`
- Global actions for `Refresh Snapshot`, `Reload tools`, and `Verify Runtime`
- Footer status showing version and whether the runtime is initialized

Current shell caveats:

- The top action buttons are desktop-first and hidden on smaller breakpoints.
- Router-managed control-room paths depend on SPA fallback rewrites from the frontend host; the Vite dev server handles this automatically.

## View Map

### Chat

Primary file: `frontend/src/views/ChatPage.tsx`

Backed by:

- `frontend/src/components/ChatWorkspace.tsx`
- `frontend/src/hooks/useChatSession.ts`
- `POST /api/sessions`
- `GET /api/sessions/{session_id}/messages`
- `POST /api/chat/stream`
- `POST /api/missions/stream`

Current behavior:

- Restores the active session id from browser `sessionStorage`
- Falls back to creating a new session when none exists or restore fails
- Streams normal chat replies into the transcript
- Streams mission progress snapshots into the same transcript
- Persists completed assistant output and reloads stored history after each streamed run
- Renders fenced code blocks separately from prose and offers `Copy Reply` for assistant messages
- Exposes `Send Chat` and `Run Mission` actions from the same draft box

Sensitive-tool approval:

- When `REQUIRE_CONFIRMATION=true`, the browser prompts before each chat or mission turn.
- Cancel keeps sensitive tools blocked for that specific request.

### Command Center

Primary file: `frontend/src/views/CommandCenterPage.tsx`

Backed by:

- `frontend/src/components/CommandCenterPanel.tsx`
- `GET /api/command-center/overview`
- `POST /api/command-center/mcp/refresh`
- `POST /api/command-center/verify`

Current behavior:

- Shows the web-to-CLI command map
- Lists the visible tool catalog grouped by source label
- Shows MCP server status, cached discovered tools, discovery freshness, last successful connection time, degraded reason, and connection errors when present
- Shows recent MCP execution results, including structured-result previews and typed error labels when available
- Exposes `Refresh MCP` for discovery-only refresh without a full runtime reload
- Shows durable memory facts through the command-center overview payload
- Renders browser-side verification output, including skill integrity, sandbox readiness, truth synthesis, startup guidance, and a bounded eval summary

Intentional gap:

- `/quit` remains terminal-only and has no browser equivalent.

### Posture

Primary file: `frontend/src/views/PosturePage.tsx`

Backed by:

- `frontend/src/components/RuntimeSignalsPanel.tsx`
- `GET /api/system/status`
- command-center durable-memory facts already fetched in the app shell

Current behavior:

- Shows runtime trust signals from the backend trust-status snapshot
- Shows privacy posture, active inference backend, and detected remote-capable tools
- Lists durable memory facts in a transparency table

### Activity

Primary file: `frontend/src/views/ActivityPage.tsx`

Backed by:

- `frontend/src/components/ExecutionModeBanner.tsx`
- `frontend/src/components/RuntimeActivityPanel.tsx`
- `frontend/src/hooks/useSystemStatus.ts`
- `GET /api/system/status`
- `POST /api/runtime/reload/stream`
- `POST /api/runtime/prepare/stream`

Current behavior:

- Shows whether web execution is auto-approved or confirmation-gated
- Surfaces the first startup-guidance warning prominently
- Lists all startup-guidance actions from the backend status snapshot
- Shows runtime metrics such as tool counts, remote capabilities, and exposed interfaces
- Streams live progress for runtime reload and runtime preparation
- Shows the last verification summary and the latest preparation output
- Exposes the page-level `Prepare Runtime` action

## API To UI Mapping

- `GET /api/system/status`: shell snapshot, posture view, activity view
- `GET /api/command-center/overview`: command center data and durable memory facts for posture
- `POST /api/command-center/mcp/refresh`: discovery-only MCP refresh and cached-inventory update
- `POST /api/command-center/verify`: command center verification panel and activity verification summary
- `POST /api/chat/stream`: streamed chat in `Chat`
- `POST /api/missions/stream`: streamed mission progress in `Chat`
- `POST /api/runtime/reload/stream`: live runtime activity log after `Reload tools`
- `POST /api/runtime/prepare/stream`: live runtime activity log and final prepare result after `Prepare Runtime`

## Operational Notes

- `Reload tools` refreshes the shared runtime skill inventory and requests a background search refresh.
- `Refresh MCP` re-runs only MCP discovery. If a server refresh fails after an earlier success, the command-center keeps the last successful inventory visible while surfacing the current error metadata.
- `Prepare Runtime` prepares sandbox assets, embedding-model cache, and LlamaCPP assets when that provider is active.
- Web verification intentionally caps mission eval time at 45 seconds. Use CLI `/verify` for the full regression-oriented pass.
- The watcher-driven development backend excludes `skills/*/scripts/*.py` from process reload; use `Reload tools` to pick up those edits without bouncing the API.