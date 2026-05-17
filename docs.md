# uZephyr Documentation: Features and Architecture

uZephyr is a local-first AI sidekick built for agency rather than one-shot chat. The current hybrid app combines a React control room, a FastAPI bridge, and a shared Python runtime that owns execution, memory, tools, and validation.

## Core Feature Set

### Hybrid Memory

- Session history is stored in the local runtime database so CLI and web turns can restore recent context.
- Semantic and keyword retrieval use the local vector store and keyword index under `data/` for search-backed answers.
- Durable workspace knowledge lives under `knowledge/brain` and related local knowledge files.

### Autonomous Missions

- Mission turns run through the same shared runtime as normal chat.
- The hybrid UI streams intermediate mission progress before the final persisted answer is written.
- The browser verification flow is intentionally lighter than the CLI fallback for long-running regression work.

### Skills and MCP

- Native Python skills live under `skills/` and can be reloaded without restarting the full stack.
- MCP discovery, degraded state, and recent execution visibility are surfaced in the command center.
- Shared runtime reload keeps the browser and CLI on the same tool inventory instead of maintaining separate web-only logic.

### Privacy and Safety

- Ollama and LlamaCPP keep inference local to the machine.
- OpenRouter is supported as a remote provider and is surfaced clearly in the runtime privacy posture.
- Sensitive tool approval can remain human-in-the-loop when `REQUIRE_CONFIRMATION` is enabled.

## Technical Architecture

### Control Room

- React + Vite frontend.
- Hash-routed operator surface for Chat, Command Center, Posture, Activity, and documentation pages.
- Uses REST for snapshots and SSE for chat, mission, reload, and prepare streams.

### Bridge

- FastAPI backend under `backend/`.
- Exposes system, runtime, sessions, chat, missions, and command-center endpoints.
- Keeps passive status paths lightweight and delegates heavy runtime ownership to the shared Python layer.

### Core Runtime

- Shared lifecycle under `core/app_runtime.py`.
- Owns memory, tool loading, LLM routing, warm-up scheduling, and search refresh behavior.
- Keeps chat and mission orchestration shared across CLI and web callers.

## Advanced Workflows

### Create a Custom Skill

1. Add a Python skill module under `skills/`.
2. Keep imports optional-safe so missing dependencies degrade cleanly.
3. Use the runtime reload flow to register the new tool without restarting the backend.

### Prepare and Search

1. Use `Prepare Runtime` when local model assets or runtime readiness still need to settle.
2. The local search runtime uses both semantic and keyword indexes under `data/`.
3. Existing cached indexes can stay available immediately while the heavier refresh work is deferred until after a completed turn.

## Common Environment Settings

| Variable | Purpose | Default |
| --- | --- | --- |
| `LLM_PROVIDER` | Select `ollama`, `openrouter`, or `llamacpp`. | `ollama` |
| `REQUIRE_CONFIRMATION` | Require manual approval for sensitive tool execution. | `false` |
| `MCP_ENABLED` | Enable MCP server configuration and discovery. | `false` |
| `EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED` | Allow optional subprocess-backed integrations. | `false` |
| `DB_PATH` | Local SQLite runtime database path. | `./data/zephyr.db` |
| `VECTOR_STORE_DIR` | Local semantic vector store path. | `./data/vector_store` |

## System Requirements

- Python 3.10+
- Node.js 18+
- Enough local RAM and storage for the chosen inference provider and local indexes

For endpoint details, see [API_DOCS.md](./API_DOCS.md).To help you finalize **uZephyr**, I have drafted the four missing documents (React control room, FastAPI bridge, and local-first AI runtime).

### 1. Docs (`DOCS.md`)
This document provides a deeper dive into the system beyond the Quick Start.

```markdown
# uZephyr Documentation: Features & Architecture

uZephyr is a high-performance, local-first AI sidekick that bridges the gap between Large Language Models and your local operating system. Unlike standard chatbots, uZephyr is designed for **agency**—the ability to plan, execute, and remember tasks across sessions.

---

## 1. Core Feature Set

### 🧠 Hybrid Memory System
uZephyr doesn't just "forget" when the window closes. It uses a three-tier memory architecture:
*   **Episodic Memory (SQLite):** Stores every message and tool output within a session, allowing for immediate conversational context.
*   **Semantic Memory (Vector DB):** Uses ChromaDB/FAISS to index your local documents and past mission logs. This enables **RAG (Retrieval-Augmented Generation)** so the AI can reference your specific data.
*   **The "Knowledge Brain":** A dedicated directory (`/knowledge/brain`) where you can place markdown files that define the AI’s core personality, rules of engagement, and essential project facts.

### 🚀 Autonomous Missions
Missions represent uZephyr’s ability to act as an Agent rather than a Chatbot. 
*   **Objective Driven:** Instead of a single prompt, you give a high-level goal (e.g., "Research this repo and write a summary").
*   **Self-Correction:** uZephyr breaks goals into sub-tasks. If a tool execution fails, the agent analyzes the error and tries a different approach.
*   **Activity Stream:** Real-time updates in the UI show you exactly what the "internal monologue" of the AI is thinking during a mission.

### 🛠️ Skills & MCP (Model Context Protocol)
uZephyr’s capabilities are modular:
*   **Native Skills:** Python-based functions located in `/skills`. These allow the AI to interact with your local file system, run shell commands, or scrape the web.
*   **MCP Integration:** Support for Anthropic’s Model Context Protocol. This allows uZephyr to connect to a growing ecosystem of external tools (Google Drive, Slack, GitHub, etc.) using a standardized interface.
*   **Hot-Reloading:** You can add a new `.py` skill to the directory and use the "Reload Runtime" command to make it available to the AI instantly without restarting the server.

### 🛡️ Privacy & Safety Posture
Security is baked into the "Posture" monitoring system:
*   **Local-First:** Preference for local LLMs (Ollama/Llama-CPP) to ensure data never leaves your machine.
*   **Human-in-the-Loop:** A configurable "Confirmation" gate. You can set the system to require a manual click before the AI executes "Dangerous" skills (like `rm -rf` or sending an email).

---

## 2. Technical Architecture

The system is split into three distinct layers:

### The Control Room (Frontend)
*   **Tech:** React + Vite + Tailwind CSS.
*   **Purpose:** A low-latency interface for real-time interaction. It handles Markdown rendering, code highlighting, and the "Mission Control" dashboard.
*   **Communication:** Connects to the Bridge via REST for commands and **Server-Sent Events (SSE)** for streaming AI responses.

### The Bridge (Middleware)
*   **Tech:** FastAPI (Python).
*   **Purpose:** Acts as the traffic controller. It manages session persistence, handles file uploads to the vector store, and provides the API layer for the UI.
*   **Security:** Handles environment variable sanitization and tool permissioning.

### The Core Runtime (Engine)
*   **Tech:** Python (LangChain/LangGraph inspired).
*   **Purpose:** The "Brain" of the operation. It manages the LLM provider rotation, the Tool Registry, and the recursive loop that powers autonomous missions.

---

## 3. Advanced Workflows

### Creating a Custom Skill
To extend uZephyr, create a file in `backend/skills/my_skill.py`:
```python
def weather_lookup(location: str):
    """Fetches weather for a given city."""
    # Your logic here
    return f"The weather in {location} is sunny."
```
uZephyr automatically parses the docstring to explain the tool to the LLM.

### Knowledge Ingestion
1.  Drop `.pdf` or `.md` files into the `data/ingest` folder.
2.  Use the UI to trigger "Rebuild Index."
3.  The AI can now answer questions about those specific documents using the `search_knowledge` tool.

---

## 4. Configuration Reference (`.env`)

| Variable | Description | Default |
|:--- |:--- |:--- |
| `LLM_PROVIDER` | `ollama`, `openrouter`, `openai`, or `llamacpp` | `ollama` |
| `CONFIRM_SENSITIVE_TOOLS` | Requires user click for file/shell actions | `true` |
| `MEMORY_RETENTION` | How many previous turns to keep in active context | `10` |
| `VECTOR_DB_PATH` | Path to store your embeddings | `./data/vector_store` |

---

## 5. System Requirements
- **Python**: 3.10+ (for async/await support).
- **Node.js**: 18+ (for the React Control Room).
- **RAM**: 8GB minimum (16GB+ recommended for local LLM inference).
- **Storage**: ~2GB for base dependencies + model size.

---

*For API-specific implementation details, please refer to [API_DOCS.md](./API_DOCS.md).*
```

---

### 2. Terms (`TERMS.md`)
Since this is a self-hosted tool, the terms focus on user responsibility and the "as-is" nature of open-source.

```markdown
# Terms of Service

**Last Updated: May 17, 2026**

By using uZephyr, you agree to the following terms:

### 1. Use of Software
uZephyr is provided as an open-source tool for personal and professional use. You are responsible for the environment in which it is deployed.

### 2. AI Output Disclaimer
uZephyr interfaces with Large Language Models (LLMs). We do not guarantee the accuracy, safety, or reliability of the content generated by these models. Users should exercise caution, especially when enabling autonomous "Missions."

### 3. Responsibility for Actions
If you disable `REQUIRE_CONFIRMATION`, the AI may execute scripts or modify files on your local system autonomously. You accept full responsibility for any data loss or system damage resulting from such actions.

### 4. Limitation of Liability
The software is provided "as-is," without warranty of any kind. In no event shall the authors (kohenmaasai) be liable for any claim, damages, or other liability.

### 5. License
Usage is governed by the MIT License included in the repository.
```

---

### 3. Privacy (`PRIVACY.md`)
This highlights the "local-first" promise which is a core selling point of your project.

```markdown
# Privacy Policy

uZephyr is built with a **local-first** philosophy. Your privacy is a priority, not an afterthought.

### 1. Data Residency
- **Local Storage**: All chat histories, vector embeddings, and session data are stored locally on your machine in the `/data` and `/knowledge` directories.
- **No Analytics**: uZephyr does not include telemetry, tracking pixels, or third-party analytics.

### 2. Third-Party LLM Providers
While uZephyr runs locally, it may communicate with external LLM providers depending on your configuration:
- **Ollama / LlamaCPP**: 100% local. No data leaves your machine.
- **OpenRouter / Anthropic**: If configured, your prompts are sent to these providers. Check their respective privacy policies for data handling.

### 3. Privacy Posture
The "Posture" view in the React Control Room provides real-time visibility into:
- Whether your current LLM provider is local or cloud-based.
- Whether sensitive tool execution requires your manual confirmation.

### 4. Security
uZephyr includes a sandbox backend for tool execution. However, as a local tool with file-system access, you should only run uZephyr in trusted environments.
```

---

### 4. API Docs (`API_DOCS.md`)
A reference for anyone wanting to build their own frontend or integrations for your bridge.

```markdown
# uZephyr API Reference

The uZephyr backend runs on FastAPI (default: `http://127.0.0.1:8000`).

## System Endpoints

### `GET /api/system/status`
Returns the current health and configuration of the runtime.

### `POST /api/runtime/reload/stream`
Triggers a hot-reload of all skills and MCP tools.
- **Returns**: A Server-Sent Event (SSE) stream of the reload progress.

## Chat & Missions

### `POST /api/chat/stream`
The primary endpoint for interacting with the AI.
- **Body**: `{ "message": "string", "session_id": "string" }`
- **Returns**: SSE stream of the AI's response.

### `POST /api/missions/turn`
Starts an autonomous mission based on a prompt.
- **Body**: `{ "objective": "string" }`

### `GET /api/sessions/{session_id}/messages`
Retrieves the history for a specific chat session.

## Command Center

### `GET /api/command-center/overview`
Provides an inventory of all active Skills, MCP tools, and Memory modules.

### `POST /api/command-center/verify`
Runs a suite of diagnostic tests to ensure the local environment (Python, Node, Vector DB) is correctly configured.

## Authentication
By default, uZephyr is designed for local-host access and does not implement a global auth layer. If exposing the backend to a network, it is recommended to use a reverse proxy with Basic Auth or a VPN.
```