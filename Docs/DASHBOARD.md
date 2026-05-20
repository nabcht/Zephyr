# Zephyr Dashboard

This document describes the current React control room shipped in `frontend/` and backed by the FastAPI bridge in `backend/`.

## Entry Point

- Launch with `run.bat` or `run-hybrid.bat`.
- Backend default address: `http://127.0.0.1:8000`
- Frontend default address: `http://127.0.0.1:5173`
- Primary control-room paths: `/chat`, `/command-center`, `/posture`, `/activity`
- Auxiliary shell paths: `/docs`, `/glossary`, `/support`, `/settings`, `/profile`, `/terms`, `/privacy`, `/api-docs`

## Global Shell

The shared shell in `frontend/src/components/AppShell.tsx` provides:

- Left runtime snapshot with provider, inference status, search status, model, and current session id
- Top navigation for `Chat`, `Command Center`, `Posture`, and `Activity`
- Global actions for `Refresh Snapshot`, `Reload tools`, and `Verify Runtime`
- Footer status showing version and whether the runtime is initialized
- Footer links into the documentation and policy pages that render inside the same shell

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
- Streams normal chat replies into the transcript, including cumulative provider-response text when the active remote provider supports streaming
- Streams mission progress snapshots into the same transcript
- Persists completed assistant output and reloads stored history after each streamed run
- Cancels abandoned browser chat turns before partial assistant output is persisted
- Supports browser slash commands directly in the composer. `/help`, `/skills`, `/memory`, and `/mcp` return inline chat replies; mutating commands reuse the existing runtime callbacks
- Stores session attachments locally, indexes them for retrieval, and shows the active attachment list in the composer
- Uses a lighter provider payload for explicit exact-answer prompts, skipping tool schemas, prior chat history, and appended durable-facts context for that specific request shape while keeping the fuller prompt context for broader no-tool requests
- Short-circuits very simple exact-answer prompts locally so the Activity view can show `local_fast_path` inference outcomes and zero provider payload for that narrow request class
- Reuses a short-lived cached direct answer for repeated identical provider-backed direct-answer requests, so the Activity view can show `local_response_cache` outcomes and zero provider payload on the repeated turn
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
- `POST /api/command-center/mcp/apply`
- `POST /api/command-center/mcp/refresh`
- `POST /api/command-center/verify`

Current behavior:

- Shows the web-to-CLI command map
- Lists the visible tool catalog grouped by source label
- Shows MCP server status, cached discovered tools, discovery freshness, last successful connection time, degraded reason, and connection errors when present
- Shows recent MCP execution results, including structured-result previews and typed error labels when available
- Exposes the Guided MCP Setup workflow, which writes `.env` configuration in `single`, `indexed`, or `json` format and refreshes the live runtime
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
- Shows runtime metrics such as tool counts, remote capabilities, exposed interfaces, provider warm-up time, first-response-token time, full provider-call time, and the latest first-round provider payload size and composition
- Streams live progress for runtime reload and runtime preparation
- Shows the last verification summary and the latest preparation output
- Exposes the page-level `Prepare Runtime` action

### Support, Settings, And Profile

Primary files:

- `frontend/src/views/NavigationPages.tsx`

Current behavior:

- `Support` provides operator recovery guidance and links back into the main surfaces
- `Settings` is a read-only view of environment-driven runtime configuration such as provider choice, interfaces, and prepare-capable actions
- `Profile` summarizes the active local operator session rather than a network-authenticated account

### Docs Landing

Current behavior:

- The generic `Docs` entry in the shell now lands on `/features`, which acts as the documentation home for product capabilities.
- The architecture reference remains available at `/docs` and is linked explicitly from the feature and glossary pages.

### Docs And Policy Pages

Primary files:

- `frontend/src/components/MarkdownDocumentPage.tsx`
- `frontend/src/views/NavigationPages.tsx`
- `GET /api/docs/{slug}`

Current behavior:

- `Docs`, `Glossary`, `Privacy`, `Terms`, and `API Docs` load markdown directly from the centralized `Docs/` folder through the backend documentation route
- The backend strips the top-level markdown title from the API payload so the page shell can render its own heading cleanly

## API To UI Mapping

- `GET /api/system/status`: shell snapshot, posture view, activity view
- `GET /api/command-center/overview`: command center data and durable memory facts for posture
- `POST /api/command-center/mcp/apply`: guided MCP setup apply flow and runtime refresh
- `POST /api/command-center/mcp/refresh`: discovery-only MCP refresh and cached-inventory update
- `POST /api/command-center/verify`: command center verification panel and activity verification summary
- `POST /api/chat/stream`: streamed chat in `Chat`
- `POST /api/missions/stream`: streamed mission progress in `Chat`
- `GET /api/sessions/{session_id}/attachments`: attachment list for `Chat`
- `POST /api/sessions/{session_id}/attachments`: attachment upload for `Chat`
- `DELETE /api/sessions/{session_id}/attachments/{attachment_id}`: attachment removal for `Chat`
- `POST /api/runtime/reload/stream`: live runtime activity log after `Reload tools`
- `POST /api/runtime/prepare/stream`: live runtime activity log and final prepare result after `Prepare Runtime`
- `GET /api/docs/{slug}`: markdown-backed docs and policy pages

## Operational Notes

- `Reload tools` refreshes the shared runtime skill inventory and requests a background search refresh.
- `Refresh MCP` re-runs only MCP discovery. If a server refresh fails after an earlier success, the command-center keeps the last successful inventory visible while surfacing the current error metadata.
- Browser slash commands are intentionally split between inline local summaries and real mutating runtime actions, so command responses stay fast without losing parity for actions that change state.
- `Prepare Runtime` prepares sandbox assets, embedding-model cache, and LlamaCPP assets when that provider is active.
- Attachment uploads are text-first today. Unsupported or empty files are rejected, and indexing depends on the search runtime being available.
- `POST /api/chat/stream` now polls for browser disconnects during remote-provider streaming and skips persisting partial assistant output if the browser drops the request before completion.
- Web verification intentionally caps mission eval time at 45 seconds. Use CLI `/verify` for the full regression-oriented pass.
- The watcher-driven development backend excludes `skills/*/scripts/*.py` from process reload; use `Reload tools` to pick up those edits without bouncing the API.