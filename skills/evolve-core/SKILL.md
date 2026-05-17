---
name: evolve-core
description: Validate, back up, and stage proposed changes to core μZephyr files (main.py, config.py, core/). Use when proposing or applying modifications to the μZephyr core codebase.
compatibility: Requires Python 3.10+. Must be run from the project root directory.
tags: [coder]
---

# evolve-core

Provides a safe two-step workflow for modifying core project files:

1. **`propose_core_change(file_path, new_code, reasoning)`** — validates Python
   syntax, creates a dated backup, stages the new code in `temp_core/`, and
   logs the action to `knowledge/memories.md`.
2. **`apply_core_change(file_path)`** — promotes the staged file to its live
   path after manual review.

Only files under `main.py`, `config.py`, and `core/` are allowed.

## Implementation

Logic lives in `scripts/evolve_core.py`.
