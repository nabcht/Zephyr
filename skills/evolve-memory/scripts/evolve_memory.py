"""μBrain Dream Cycle – synthesises the timeline into a compiled truth layer.

This skill is auto-discovered and registered by SkillLoader. When called, it:
  1. Reads the last N lines of timeline.log (the append-only evidence stream).
  2. Reads the current truth.md (the compiled executive summary).
  3. Sends a synthesis prompt to the configured LLM.
  4. Overwrites truth.md with the result.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

import httpx

import config
from core.truth_synthesis import (
    TruthSynthesisHealth,
    describe_truth_synthesis_health,
    extract_state_claim as _extract_state_claim,
    get_truth_synthesis_health,
    normalize_text as _normalize_text,
    recent_unique_facts as _recent_unique_facts,
    remove_recent_contradictions as _remove_recent_contradictions,
)

log = logging.getLogger("uzephyr.skills.evolve_memory")

_SYNTHESIS_TEMPLATE = """\
You are a memory synthesizer for a personal AI assistant.

## Recent Evidence Stream (last {count} entries from timeline.log):
{timeline_snippet}

## Current Executive Summary (truth.md):
{current_truth}

## Task:
Rewrite the executive summary by:
- Merging all new facts from the evidence stream into the existing summary.
- Resolving any contradictions (prefer the more recent timeline entry).
- Removing redundant or outdated information.
- Keeping the output concise and factual.

Output ONLY the new truth.md content — no preamble, no commentary.
"""


async def evolve_memory(lines: int = 40) -> str:
    """Synthesize the last N lines of the memory timeline into an updated truth summary.

    Reads timeline.log and the current truth.md, sends both to the configured LLM,
    and overwrites truth.md with a merged, contradiction-free executive summary.

    Args:
        lines: Number of recent timeline entries to consider (default 40).
    """
    # ── 1. Read timeline snippet ──────────────────────────────────────────
    if not config.TIMELINE_FILE.exists():
        return "No timeline.log found — call memory_durable_fact first to begin recording."

    all_lines = config.TIMELINE_FILE.read_text(encoding="utf-8").splitlines()
    recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
    if not recent:
        return "timeline.log is empty — nothing to synthesize."

    timeline_snippet = "\n".join(recent)

    # ── 2. Read current truth.md ──────────────────────────────────────────
    current_truth = ""
    if config.TRUTH_FILE.exists():
        current_truth = config.TRUTH_FILE.read_text(encoding="utf-8").strip()

    # ── 3. Build synthesis prompt ─────────────────────────────────────────
    prompt = _SYNTHESIS_TEMPLATE.format(
        count=len(recent),
        timeline_snippet=timeline_snippet,
        current_truth=current_truth or "(empty — first synthesis run)",
    )

    # ── 4. Route to configured LLM provider ──────────────────────────────
    new_truth = await _call_llm(prompt)
    stabilized_truth = _stabilize_truth_output(new_truth, current_truth, recent)

    # ── 5. Overwrite truth.md ─────────────────────────────────────────────
    config.BRAIN_DIR.mkdir(parents=True, exist_ok=True)
    config.TRUTH_FILE.write_text(stabilized_truth.strip() + "\n", encoding="utf-8")
    log.info("truth.md updated — processed %d timeline entries.", len(recent))

    return (
        f"truth.md updated. Synthesized {len(recent)} timeline entries "
        f"({'all' if len(all_lines) <= lines else f'latest {lines} of {len(all_lines)}'})."
    )


def _clean_truth_output(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    return cleaned


def _stabilize_truth_output(new_truth: str, current_truth: str, timeline_lines: list[str]) -> str:
    stabilized = _clean_truth_output(new_truth)
    if not stabilized:
        stabilized = current_truth.strip()
    stabilized = _remove_recent_contradictions(stabilized, timeline_lines)

    missing_recent_facts = []
    normalized_truth = _normalize_text(stabilized)
    for fact in _recent_unique_facts(timeline_lines):
        if _normalize_text(fact) not in normalized_truth:
            missing_recent_facts.append(fact)

    if not missing_recent_facts:
        return stabilized.strip()

    preserved_block = "\n".join(f"- {fact}" for fact in missing_recent_facts)
    if stabilized:
        return f"{stabilized.rstrip()}\n\nRecent verified facts:\n{preserved_block}".strip()
    return f"Recent verified facts:\n{preserved_block}".strip()


async def _call_llm(prompt: str) -> str:
    """Send *prompt* to the active LLM provider and return the response text."""
    provider = config.LLM_PROVIDER

    if provider == "llamacpp":
        return await _llamacpp_generate(prompt)

    # Ollama and OpenRouter both speak OpenAI-compatible /chat/completions
    return await _openai_compat_generate(prompt, provider)


async def _openai_compat_generate(prompt: str, provider: str) -> str:
    """POST to Ollama or OpenRouter /chat/completions and return the reply text."""
    if provider == "ollama":
        url = f"{config.OLLAMA_BASE_URL}/v1/chat/completions"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        model = config.OLLAMA_MODEL
    else:  # openrouter
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://github.com/uzephyr",
            "X-Title": "uZephyr",
        }
        model = config.OPENROUTER_MODEL

    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected LLM response shape: {data}") from exc


async def _llamacpp_generate(prompt: str) -> str:
    """Run a completion through the local llama-cpp-python model in a thread executor."""
    from llama_cpp import Llama

    model_path = str(config.LLAMACPP_MODEL_PATH)
    kwargs: dict[str, Any] = {
        "model_path": model_path,
        "n_ctx": config.LLAMACPP_N_CTX,
        "n_gpu_layers": config.LLAMACPP_N_GPU_LAYERS,
        "verbose": False,
    }
    if config.LLAMACPP_CHAT_FORMAT:
        kwargs["chat_format"] = config.LLAMACPP_CHAT_FORMAT

    messages = [{"role": "user", "content": prompt}]

    loop = asyncio.get_event_loop()
    result: dict[str, Any] = await loop.run_in_executor(
        None,
        lambda: Llama(**kwargs).create_chat_completion(messages=messages),
    )

    try:
        return result["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected LlamaCPP response shape: {result}") from exc
