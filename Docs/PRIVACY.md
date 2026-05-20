# Privacy Policy

Last Updated: May 18, 2026

Zephyr is built with a local-first philosophy. Privacy is an operating assumption, not a marketing add-on.

## Data Residency

- Chat history, local search indexes, logs, and durable knowledge files are stored in workspace-controlled local paths by default.
- Session attachments are stored under `temp_core/attachments` unless `SESSION_ATTACHMENTS_DIR` overrides that path.
- Runtime state is persisted locally through paths such as `DB_PATH`, `VECTOR_STORE_DIR`, `KEYWORD_INDEX_DIR`, and the `knowledge/` directory.
- The current hybrid app does not include built-in telemetry or third-party analytics.

## Third-Party Providers

- `ollama` and `llamacpp` keep inference local to the machine.
- `openrouter` sends prompts and request context to a remote provider when that backend is selected.
- Optional MCP or subprocess-backed integrations can also extend the runtime beyond the local machine when explicitly enabled.

## Session Attachments

- Attachments uploaded from the browser are indexed locally for session-scoped retrieval.
- Only extractable text content is currently accepted.
- Deleting an attachment removes both its metadata and its indexed search content from the local runtime.

## Live Privacy Posture

The browser Posture and Activity views surface:

- the current inference backend,
- whether remote capabilities are active,
- whether sensitive tool approval is required.

The Command Center also surfaces whether MCP and other external subprocess integrations are enabled.

## Security Note

Zephyr includes sandbox-backed execution paths, but it is still a local operator tool with filesystem and command capabilities. Run it only in environments you trust.