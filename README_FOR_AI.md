This is a comprehensive `README_FOR_AI.md` designed specifically to guide an AI agent (like GPT-4, Claude 3.5, or GitHub Copilot) through the process of transforming the **uZephyr** repository into a Python + React hybrid application integrated with **Google’s design.md**.

---

# README_FOR_AI.md

## 1. Project Overview
**Project Name:** uZephyr Hybrid (uZephyr-H)
**Core Objective:** Transform the existing `uZephyr` codebase into a full-stack hybrid application. The backend will be powered by **Python (FastAPI)**, the frontend by **React (Vite)**, and the UI/UX design system will be governed by **Google’s design.md** specifications.

## 2. Technology Stack
*   **Backend:** Python 3.10+ (FastAPI)
*   **Frontend:** React 18 (Vite, TypeScript)
*   **Design Framework:** Google Design.md (for component documentation and specs)
*   **Communication:** REST API / WebSockets (for real-time uZephyr data)
*   **Styling:** Tailwind CSS (mapped to Design.md tokens)
*   **Packaging:** Docker (optional) or Poetry (Python) + NPM (React)

## 3. Desired Folder Structure
```text
uZephyr/
├── backend/                # Python FastAPI logic
│   ├── main.py             # Entry point
│   ├── api/                # Endpoints
│   ├── core/               # uZephyr logic/bindings
│   └── requirements.txt
├── frontend/               # React application
│   ├── src/
│   │   ├── components/     # UI Components based on design.md
│   │   ├── hooks/          # API integration
│   │   └── App.tsx
│   ├── design.md           # Google Designer Integration File
│   └── package.json
├── docs/
│   └── design_system/      # Google Designer specific docs
└── README_FOR_AI.md        # This instruction file
```

## 4. Integration Roadmap

### Phase 1: Environment Setup
1.  Initialize a Python virtual environment in `/backend`.
2.  Initialize a Vite React (TypeScript) project in `/frontend`.
3.  Install `fastapi`, `uvicorn` in Python.
4.  Install `tailwindcss`, `lucide-react` (for icons) in React.

### Phase 2: Design.md Integration (Google Designer)
1.  **Ingestion:** Read the `design.md` file from the root/frontend.
2.  **Implementation:** AI must parse the `design.md` specs (colors, typography, spacing) and translate them into a `tailwind.config.js` file.
3.  **Component Mapping:** Every React component generated must reference a section in `design.md`.

### Phase 3: Backend Bridge (uZephyr to Python)
1.  Expose the existing `uZephyr` logic (C++/specific functionality) via Python bindings (using `ctypes`, `cffi`, or `pybind11`) if necessary.
2.  Create FastAPI routes to serve data from the uZephyr core to the frontend.

### Phase 4: Frontend Development
1.  Build a dashboard layout using React.
2.  Implement "Design-First" components:
    *   Create a `DesignWrapper` that follows Google’s layout specs.
    *   Use Tailwind classes that match the `design.md` tokens.

### Phase 5: Hybrid Connectivity
1.  Configure Vite Proxy to route `/api` calls to the FastAPI server (default: `localhost:8000`).
2.  Implement State Management (Zustand or React Context) to handle uZephyr's state.

---

## 5. AI Agent Instructions (Execution Rules)

When generating code for this project, follow these strict rules:

1.  **Design Compliance:** Before writing any React component, check `frontend/design.md`. If a component (e.g., "Button") is defined there, use the exact padding, color tokens, and border-radius specified.
2.  **Type Safety:** Always use TypeScript for the frontend. Define interfaces for all API responses coming from the Python backend.
3.  **Modular Python:** Keep FastAPI routes clean. Use a `services/` directory in the backend to handle the actual uZephyr logic, keeping `api/` only for request/response handling.
4.  **Component Documentation:** For every React component created, add a JSDoc comment linking it to the corresponding `design.md` section.
5.  **Hybrid Workflow:** 
    *   If the user asks for a feature, provide both the Python FastAPI endpoint and the React `fetch` logic/Component UI in the same response.
    *   Ensure the Python backend includes CORS middleware to allow the React frontend to communicate during development.

---

## 6. Implementation Step-by-Step for AI

### Step 1: Initialize Backend
```python
# Create backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="uZephyr Hybrid API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "uZephyr Online"}
```

### Step 2: Initialize Frontend with design.md
*   Create `frontend/design.md` based on [Google Labs design.md](https://github.com/google-labs-code/design.md).
*   Define a core theme in `design.md`.
*   Generate `tailwind.config.js` to match these definitions.

### Step 3: Link uZephyr Core
*   Identify the main entry point of the original uZephyr code.
*   Create a Python wrapper (`backend/core/zephyr_wrapper.py`) that executes or interacts with the original logic.

### Step 4: Final Assembly
*   Create a startup script `run_app.sh` that starts both the FastAPI server and the Vite dev server concurrently.

---

**Note to AI:** You are now the lead architect. Start by analyzing the current `uZephyr` files and suggest the first set of Python bindings needed to expose its functionality to a web interface.