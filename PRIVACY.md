# Privacy Policy

Last Updated: May 18, 2026

uZephyr is built with a local-first philosophy. Privacy is an operating assumption, not a marketing add-on.

## Data Residency

- Chat history, local search indexes, logs, and durable knowledge files are stored in workspace-controlled local paths by default.
- The current hybrid app does not include built-in telemetry or third-party analytics.

## Third-Party Providers

- `ollama` and `llamacpp` keep inference local to the machine.
- `openrouter` sends prompts and request context to a remote provider when that backend is selected.
- Optional MCP or subprocess-backed integrations can also extend the runtime beyond the local machine when explicitly enabled.

## Live Privacy Posture

The browser Posture and Activity views surface:

- the current inference backend,
- whether remote capabilities are active,
- whether sensitive tool approval is required.

## Security Note

uZephyr includes sandbox-backed execution paths, but it is still a local operator tool with filesystem and command capabilities. Run it only in environments you trust.