# Zephyr AI Contributor Brief

This file describes the current state of the repository for coding agents and AI contributors. The hybrid migration is already complete; this is no longer a scaffolding brief.

## Current Project Shape

- `core/` is the shared runtime and remains the primary ownership layer for memory, tools, search, chat orchestration, and mission orchestration.
- `backend/` is the FastAPI bridge. Keep route handlers thin and prefer backend services for request/response assembly.
- `frontend/` is the primary interface. It uses React, TypeScript, typed API shapes, and route-managed pages.
- `Docs/` is the canonical documentation set for product, operator, and policy docs.

## Current Runtime Facts

- The browser UI is the default interface; the CLI is the fallback/operator surface.
- `core/app_runtime.py` owns subsystem lifecycle for both CLI and backend callers.
- `core/chat_service.py` and `core/mission_service.py` are the shared turn-orchestration layers.
- Search warm-up and inference warm-up are deliberately staged so passive status paths stay lightweight.
- Session attachments are now part of the live product and are indexed locally for session-scoped retrieval.

## Implementation Rules For AI Contributors

1. Prefer extending the shared runtime or backend services instead of duplicating logic between CLI and browser codepaths.
2. Keep `backend/api/routes/` focused on transport and schema concerns; move behavior into `backend/services/` or `core/`.
3. Keep `frontend/src/types/api.ts` aligned with backend schemas whenever API payloads change.
4. Check `frontend/design.md` before making visual changes; it is the current design-token source of truth.
5. Update `Docs/` when user-visible features, pages, routes, or workflows change.

## Current Browser Surfaces

- `Chat`: streaming chat, mission launch, slash commands, attachments.
- `Command Center`: tool inventory, MCP state, MCP configuration, verification.
- `Posture`: privacy and trust reporting.
- `Activity`: runtime metrics and live runtime-action streams.
- auxiliary pages: docs, glossary, support, settings, profile, privacy, terms, API docs.

## High-Value Validation Commands

- `npm run build:frontend`
- `npm run verify:command-center`
- `npm run verify:hybrid`
- focused `python -m unittest ...` runs in `tests/`

## Common Pitfalls

- Do not force heavy runtime bootstrap from passive status-style routes.
- Do not duplicate the active user message into history before building prompt context.
- Keep skill modules import-safe even when optional dependencies are missing.
- Preserve the browser disconnect behavior that avoids persisting partial streamed chat output.

## When Docs Must Change

Update the documentation set when any of the following changes:

- API routes or payloads
- browser page behavior
- slash-command behavior
- attachment handling
- MCP configuration workflow
- runtime preparation, verification, or operator visibility surfaces