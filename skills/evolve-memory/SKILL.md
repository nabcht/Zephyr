---
name: evolve-memory
description: Synthesize the memory timeline into an updated truth summary by merging recent timeline entries with the existing executive summary via the configured LLM. Use to consolidate long-term memory in μZephyr.
compatibility: Requires Python 3.10+ and a configured LLM provider (Ollama, OpenRouter, or LlamaCPP).
---

# evolve-memory

Implements the μBrain Dream Cycle:

1. Reads the last N lines of `knowledge/brain/timeline.log`.
2. Reads the current `knowledge/brain/truth.md`.
3. Sends a synthesis prompt to the configured LLM.
4. Overwrites `truth.md` with a merged, contradiction-free executive summary.

## Usage

Call `evolve_memory(lines=40)`.

## Implementation

Logic lives in `scripts/evolve_memory.py`.
