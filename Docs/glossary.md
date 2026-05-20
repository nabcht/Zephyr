# uZephyr Glossary

This glossary covers both project-specific terminology used inside **uZephyr** and the broader AI, runtime, and web terms that show up across the codebase, docs, and Control Room.

## uZephyr Product Terms

- **uZephyr:** A local-first AI sidekick built around a shared Python runtime and a browser-based operator surface.
- **Control Room:** The primary React web interface for chat, missions, runtime visibility, and operator workflows.
- **Command Center:** The Control Room view focused on tool inventory, MCP status, durable memory, and runtime verification.
- **Activity:** The operator page that surfaces runtime action progress, provider warm-up timings, and recent status changes.
- **Posture:** The page that summarizes privacy posture, trust visibility, and current runtime safeguards.
- **Mission:** A multi-step task run through the agency loop rather than a single chat response.
- **Mission Orchestrator / Agency Loop:** The execution path that plans, calls tools, and iterates toward a goal during mission runs.
- **Skills:** Python-based capability packages under `skills/` that expose tools to the runtime.
- **Tool Catalog:** The runtime-visible inventory of built-in, skill-based, manual, and MCP-backed tools.
- **Guided MCP Setup:** The browser walkthrough in Command Center that builds and applies `.env` configuration for one or more MCP servers.

## Runtime And Architecture Terms

- **AppRuntime (`core/app_runtime.py`):** The shared runtime that owns memory, tool loading, background warm-up, and LLM lifecycle.
- **Shared Runtime:** The design where the CLI, FastAPI backend, and browser flows all reuse the same underlying runtime state.
- **FastAPI Bridge:** The backend HTTP layer that exposes runtime snapshots, chat turns, mission flows, and command-center actions to the React UI.
- **Tool Engine:** The subsystem that registers tools, manages MCP-backed tools, and routes execution through the registry.
- **Tool Registry:** The lookup layer that stores the active set of callable tools by name, source, parameters, and tags.
- **Prepare Runtime:** A runtime action that settles local prerequisites such as provider warm-up, sandbox readiness, and search initialization.
- **Reload Tools:** A runtime action that reloads local skills and refreshes the visible tool surface without rebuilding the entire app.
- **Runtime Verification:** The browser-safe or CLI-heavy diagnostic pass that checks skill integrity and runtime readiness.
- **Durable Facts:** Long-lived memory facts retained beyond a single session so the runtime can remember stable context.
- **Startup Guidance:** Operator-facing advice generated from the current runtime state, feature flags, and degraded conditions.
- **Truth Synthesis:** The subsystem that summarizes grounded runtime facts and trust-related observations for operator review.
- **Archive Bridge:** The connection between the runtime memory/archive layer and archive-aware tools or retrieval flows.

## Data, Search, And Integration Terms

- **Hybrid Retriever:** The search path that combines semantic vector retrieval with keyword-based retrieval.
- **Keyword Index:** The on-disk search index used for exact or lexical matching across workspace content.
- **Vector Store:** The semantic index under `data/vector_store/`, used for meaning-based retrieval.
- **Embeddings / Vector Model:** Numerical representations of text that let the runtime search by semantic similarity instead of exact string matches.
- **RAG (Retrieval-Augmented Generation):** The pattern of retrieving local context first and then giving that context to the model before generation.
- **SQLite:** The local file-based database used for session history and other runtime-managed persisted state.
- **Sandbox:** The isolated execution surface used to run validation or code safely via Docker or process isolation.
- **Claude-Mem:** A memory-related integration or subprocess that follows Claude-style memory workflow patterns.
- **MCP (Model Context Protocol):** A standard for exposing external tools and data sources to language-model runtimes.
- **MCP Discovery:** The process of connecting to configured MCP servers and listing their available tools.
- **MCP Server:** A specific command-launched or bridge-launched MCP endpoint that exposes tools to the runtime.
- **Tool Prefix:** The MCP namespace prefix used to build collision-resistant local tool names for remote MCP tools.

## AI And Model Terms

- **LLM (Large Language Model):** The model that interprets prompts, reasons over context, and generates responses.
- **LLM Router:** The component that owns provider selection, readiness state, warm-up, and inference timing visibility.
- **Inference Backend:** The actual model-serving backend used by the runtime. uZephyr currently supports Ollama, LlamaCPP, and OpenRouter.
- **Ollama:** A local model-serving tool that makes local LLM execution straightforward on a developer workstation.
- **LlamaCPP:** A high-performance local inference backend designed for efficient CPU or GPU execution.
- **OpenRouter:** A hosted API layer that exposes remote model providers through a unified interface.
- **Warm-up:** The initial provider preparation step that makes the first real model call faster and exposes readiness state in the UI.
- **SSE (Server-Sent Events):** The streaming transport used for progressive browser updates such as chat snapshots, mission progress, and runtime actions.

## General Development Terms Used In uZephyr

- **API (Application Programming Interface):** The contract that lets the frontend, backend, and tools exchange structured data.
- **CLI (Command Line Interface):** The terminal-first operator surface used for chat, runtime actions, and fallback workflows.
- **Environment Variables (`.env`):** The config surface used to store provider settings, paths, feature flags, and integration values outside the code.
- **Hybrid Launcher:** A script such as `run-hybrid.bat` that starts the backend and frontend together.
- **React:** The UI library used to build the Control Room frontend.
- **FastAPI:** The Python framework used to expose the backend HTTP API.
- **Venv (Virtual Environment):** The isolated Python environment that keeps project dependencies separate from the global interpreter.