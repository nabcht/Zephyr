# Zephyr API Reference

The local FastAPI backend runs on `http://127.0.0.1:8000` by default.

## Response Conventions

- Snapshot endpoints return JSON.
- Streaming endpoints use Server-Sent Events with `snapshot`, `done`, and `error` events.
- Browser chat and mission flows use the same request body shape:

```json
{
  "session_id": "string",
  "message": "string",
  "allow_sensitive_tools": false
}
```

## System Endpoints

### `GET /api/system/health`

Returns a lightweight backend health response.

### `GET /api/system/status`

Returns the current runtime snapshot, including provider readiness, inference timing metrics, startup guidance, privacy posture, trust signals, and tool counts.

Key fields include:

- `provider`
- `model`
- `runtime_initialized`
- `inference_status`
- `inference_metrics`
- `provider_payload_metrics`
- `search_status`
- `tool_counts`
- `privacy_status`
- `trust_status`
- `startup_guidance`

## Runtime Endpoints

### `POST /api/runtime/reload`

Reloads tool definitions and refreshes background search state.

Returns the same `SystemStatusResponse` shape as `/api/system/status`.

### `POST /api/runtime/reload/stream`

Streams runtime reload progress over Server-Sent Events.

The final `done` event includes the refreshed system snapshot.

### `POST /api/runtime/prepare`

Prepares local runtime assets exposed by the current provider and sandbox.

This includes sandbox preparation, embedding-model preparation, provider warm-up, and search-runtime settling.

### `POST /api/runtime/prepare/stream`

Streams runtime preparation progress over Server-Sent Events.

The final `done` event includes `success`, accumulated log lines, and the final system snapshot.

## Sessions, Chat, and Missions

### `POST /api/sessions`

Creates a new web session identifier.

### `GET /api/sessions/{session_id}/messages`

Returns recent persisted messages for the session.

Response shape:

```json
{
  "session_id": "string",
  "messages": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

### `GET /api/sessions/{session_id}/attachments`

Returns metadata for the active session attachments.

### `POST /api/sessions/{session_id}/attachments`

Uploads and indexes one attachment for session-scoped retrieval.

- Request type: `multipart/form-data`
- Field name: `file`
- Status code: `201 Created`

Current attachment rules:

- files must contain extractable text,
- each file is capped at 10 MB,
- indexing requires the local search runtime to be available.

### `DELETE /api/sessions/{session_id}/attachments/{attachment_id}`

Removes one attachment from both session metadata and the local indexes.

### `POST /api/chat/turn`

Accepts:

```json
{
  "session_id": "string",
  "message": "string",
  "allow_sensitive_tools": false
}
```

Returns one persisted assistant response.

If `allow_sensitive_tools` is omitted and `REQUIRE_CONFIRMATION=true`, the backend defaults sensitive-tool execution to blocked for that request.

### `POST /api/chat/stream`

Accepts the same request body and streams snapshot and done events over SSE.

Notes:

- cold requests emit an initialization snapshot before runtime bootstrap completes,
- disconnect-aware cancellation prevents partial browser output from being persisted.

### `POST /api/missions/turn`

Accepts the same request body shape as chat and returns one persisted mission response.

Mission turns automatically include relevant session-attachment retrieval context when available.

### `POST /api/missions/stream`

Accepts the same request body shape and streams mission progress snapshots over SSE.

The first snapshot is an immediate mission-progress status block even before the full runtime is ready.

## Command Center Endpoints

### `GET /api/command-center/overview`

Returns CLI-equivalent web inspection data for tools, MCP state, memory, and commands.

The payload includes:

- `commands`
- `tools`
- `mcp`
- `memory`

### `POST /api/command-center/mcp/apply`

Persists walkthrough-generated MCP settings into the repo `.env`, updates the live backend process, and returns the refreshed Command Center overview.

Accepts:

```json
{
  "format": "single",
  "enable_mcp": true,
  "enable_external_integrations": true,
  "servers": [
    {
      "name": "archive",
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://example.com/mcp"],
      "env": {
        "API_KEY": "demo-token"
      },
      "cwd": null,
      "tool_prefix": "mcp"
    }
  ]
}
```

Use `format: "single"` for one server, `format: "indexed"` for `MCP_SERVER_1_*` style output, or `format: "json"` for `MCP_SERVERS_JSON`.

### `POST /api/command-center/mcp/refresh`

Refreshes cached MCP discovery without reloading the full runtime.

### `POST /api/command-center/verify`

Runs the browser-facing runtime verification workflow.

The response reports:

- valid, repaired, and broken skills,
- sandbox readiness,
- truth-synthesis health,
- startup guidance lines,
- a bounded mission-eval summary.

## Documentation Endpoints

### `GET /api/docs/{slug}`

Returns markdown content from the centralized `Docs/` folder for the browser documentation pages.

Current slugs:

- `docs`
- `features`
- `glossary`
- `api-docs`
- `privacy`
- `terms`

Response shape:

```json
{
  "slug": "docs",
  "title": "Zephyr Documentation: Features and Architecture",
  "content": "...markdown body without the top-level title...",
  "source_path": "Docs/docs.md"
}
```

## Authentication

The current backend is designed for local-host access and does not ship with a global auth layer. If you expose it beyond the local machine, add your own reverse proxy, VPN, or equivalent access control.