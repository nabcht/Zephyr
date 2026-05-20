# Contributing to μZephyr

Thank you for your interest in Zephyr. Contributions are welcome across the shared runtime, FastAPI bridge, React control room, skills, and documentation.

## Table of Contents

1. [Development Setup](#development-setup)
2. [Project Architecture](#project-architecture)
3. [Adding New Skills](#adding-new-skills)
4. [Testing & Validation](#testing--validation)
5. [Pull Request Process](#pull-request-process)

## Development Setup

1. Fork and clone the repository.
2. Install Python 3.11+ and Node.js 18+.
3. Create and activate a virtual environment.
4. Install backend dependencies from the repository root.
5. Install frontend dependencies before using the primary browser workflow.

Recommended commands:

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
npm run install:frontend
```

If you prefer the guided setup, run `setup.bat`.

## Project Architecture

The current codebase is organized around one shared runtime stack:

- `core/` owns shared runtime lifecycle, memory, LLM routing, search, tools, and mission orchestration.
- `backend/` exposes FastAPI routes, schemas, and services over the shared runtime.
- `frontend/` contains the React control room, typed API hooks, and operator views.
- `skills/` contains local skill packages that are loaded into the shared tool inventory.
- `Docs/` contains the user, operator, and contributor documentation set.

When adding behavior, prefer extending the existing shared runtime or service layers rather than duplicating logic in separate CLI-only or web-only paths.

## Adding New Skills

Skills are modular and loaded dynamically from the `skills/` directory.

To create a new skill:
1. Create a directory such as `skills/your-skill-name/`.
2. Provide a Python module that exposes the intended tool entry points.
3. Keep imports optional-safe so missing third-party packages do not crash the entire skill loader.
4. Write clear docstrings and descriptions so the runtime can explain the tool surface correctly.
5. Reload the tool inventory with `Reload tools` in the browser or `/reload` in the CLI.

## Testing & Validation

Use the narrowest validation that matches your change:

- `python -m unittest` for focused backend and runtime tests.
- `npm run build:frontend` for frontend type/build validation.
- `npm run verify:command-center` when you touch command-center, MCP discovery, or tool inventory behavior.
- `npm run verify:hybrid` when you touch the broader hybrid workflow, runtime streaming, or launcher behavior.

When code execution behavior changes, keep sandbox-backed validation in mind and avoid bypassing existing approval or runtime-safety gates.

## Pull Request Process

1. Keep changes focused and scoped to a specific runtime, UI, or documentation need.
2. Update `Docs/` when user-visible behavior, routes, or workflows change.
3. Avoid committing runtime-generated files such as `.env`, local indexes, logs, or attachment artifacts.
4. Include the validation commands you ran in the pull request description.
