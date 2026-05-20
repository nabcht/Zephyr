# uZephyr API Reference

The local FastAPI backend runs on `http://127.0.0.1:8000` by default.

## System Endpoints

### `GET /api/system/health`

Returns a lightweight backend health response.

### `GET /api/system/status`

Returns the current runtime snapshot, including provider readiness, inference timing metrics, startup guidance, privacy posture, trust signals, and tool counts.

## Runtime Endpoints

### `POST /api/runtime/reload`

Reloads tool definitions and refreshes background search state.

### `POST /api/runtime/reload/stream`

Streams runtime reload progress over Server-Sent Events.

### `POST /api/runtime/prepare`

Prepares local runtime assets exposed by the current provider and sandbox.

### `POST /api/runtime/prepare/stream`

Streams runtime preparation progress over Server-Sent Events.

## Sessions, Chat, and Missions

### `POST /api/sessions`

Creates a new web session identifier.

### `GET /api/sessions/{session_id}/messages`

Returns recent persisted messages for the session.

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

### `POST /api/chat/stream`

Accepts the same request body and streams snapshot and done events over SSE.

### `POST /api/missions/turn`

Accepts the same request body shape as chat and returns one persisted mission response.

### `POST /api/missions/stream`

Accepts the same request body shape and streams mission progress snapshots over SSE.

## Command Center Endpoints

### `GET /api/command-center/overview`

Returns CLI-equivalent web inspection data for tools, MCP state, memory, and commands.

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

## Authentication

The current backend is designed for local-host access and does not ship with a global auth layer. If you expose it beyond the local machine, add your own reverse proxy, VPN, or equivalent access control.