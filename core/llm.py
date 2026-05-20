"""LLM provider router — Ollama (local), OpenRouter (cloud), and LlamaCPP (local GGUF)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, TYPE_CHECKING

import httpx
from rich.console import Console
from rich.text import Text

import config

if TYPE_CHECKING:
    from core.tool_engine import ToolEngine
    from core.memory import MemoryManager

log = logging.getLogger("uzephyr.llm")

# Maximum tool-call iterations per turn to prevent infinite loops
_MAX_TOOL_ROUNDS = 10

# ── Gemma-4 native tool-call parsing ─────────────────────────────────────────
# Gemma-4 emits tool calls as:  <|tool_call>call:func_name{key:val,...}<tool_call|>
_GEMMA4_TOOL_CALL_RE = re.compile(
    r'<\|tool_call>call:(\w+)\{(.*?)\}<tool_call\|>',
    re.DOTALL,
)
_DURABLE_FACTS_SECTION_MARKER = "\n\n## Durable Facts\n"
_EXPLICIT_NO_TOOL_PROMPT_RE = re.compile(
    r"\b(do not call tools|don't call tools|without tools|no tools|reply with exactly|respond with exactly|answer with exactly|say exactly)\b",
    re.IGNORECASE,
)
_EXACT_DIRECT_ANSWER_PROMPT_RE = re.compile(
    r"\b(reply with exactly|respond with exactly|answer with exactly|say exactly)\b",
    re.IGNORECASE,
)
_LOCAL_EXACT_DIRECT_ANSWER_RE = re.compile(
    r"^\s*(?:reply|respond|answer|say)\s+with\s+exactly\s+(?:(?P<quote>[\"'`])(?P<quoted_answer>.*?)(?P=quote)|(?P<bare_answer>[A-Za-z0-9_-]+))(?:\s*\.\s*(?:do not call tools|don't call tools|without tools|no tools)\.?)?\s*\.?\s*$",
    re.IGNORECASE | re.DOTALL,
)
_DIRECT_ANSWER_RESPONSE_CACHE_TIME_TO_LIVE_SECONDS = 120.0
_DIRECT_ANSWER_RESPONSE_CACHE_MAXIMUM_ENTRIES = 32


def _gemma4_args_to_dict(raw_args: str) -> dict[str, Any]:
    """Convert Gemma-4 native argument format to a Python dict."""
    if not raw_args.strip():
        return {}

    result: dict[str, Any] = {}

    # --- Pass 1: extract <|"|>-delimited string values ----------------------
    str_pattern = re.compile(r'(\w+):<\|"\|>(.*?)<\|"\|>', re.DOTALL)
    covered: list[tuple[int, int]] = []
    for m in str_pattern.finditer(raw_args):
        result[m.group(1)] = m.group(2)
        covered.append((m.start(), m.end()))

    # --- Pass 2: extract bare (unquoted) values from uncovered regions ------
    def _covered(start: int, end: int) -> bool:
        return any(s <= start and end <= e for s, e in covered)

    for m in re.finditer(r'(\w+):([\w.+-]+)', raw_args):
        if _covered(m.start(), m.end()):
            continue
        key, val = m.group(1), m.group(2)
        if key in result:
            continue
        if val.lower() == 'true':
            result[key] = True
        elif val.lower() == 'false':
            result[key] = False
        else:
            try:
                result[key] = int(val)
            except ValueError:
                try:
                    result[key] = float(val)
                except ValueError:
                    result[key] = val

    if result:
        return result

    # --- Pass 3: last-resort standard JSON ---------------------------------
    clean_args = raw_args.strip()
    if not clean_args.startswith('{'):
        clean_args = '{' + clean_args + '}'
        
    try:
        return json.loads(clean_args)
    except json.JSONDecodeError:
        try:
            # Attempt to fix missing quotes around keys
            s = re.sub(r'(?<=[{,])\s*(\w+)\s*:', r'"\1":', clean_args)
            return json.loads(s)
        except json.JSONDecodeError:
            log.warning("JSON parse failed. Returning error flag to LLM.")
            # Do NOT return {}. Return a flag so the tool engine can scold the LLM.
            return {"_json_parse_error": raw_args}


def _parse_gemma4_tool_calls(text: str) -> list[dict[str, Any]]:
    """Extract structured tool calls from Gemma-4 native text output."""
    calls: list[dict[str, Any]] = []
    for match in _GEMMA4_TOOL_CALL_RE.finditer(text):
        fn_name = match.group(1)
        raw_args = match.group(2)
        args = _gemma4_args_to_dict(raw_args)
        calls.append({
            "id": f"call_{uuid.uuid4().hex[:8]}",
            "type": "function",
            "function": {
                "name": fn_name,
                "arguments": json.dumps(args),
            },
        })
    return calls


def _strip_gemma4_tool_markers(text: str) -> str:
    """Remove tool-call markers from text to extract plain content."""
    return _GEMMA4_TOOL_CALL_RE.sub('', text).strip()


# ── Model file URLs ───────────────────────────────────────────────────────────
_HF_BASE = "https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main"
_MODEL_FILES: list[tuple[str, str]] = [
    (
        "gemma-4-E4B-it-UD-Q8_K_XL.gguf",
        f"{_HF_BASE}/gemma-4-E4B-it-UD-Q8_K_XL.gguf?download=true",
    ),
    (
        "mmproj-F32.gguf",
        f"{_HF_BASE}/mmproj-F32.gguf?download=true",
    ),
    (
        "config.json",
        f"{_HF_BASE}/config.json?download=true",
    ),
]

_console = Console()


@dataclass(frozen=True, slots=True)
class LlamaCppPreparation:
    """Preparation result for LlamaCPP model assets."""

    attempted: bool
    success: bool
    detail: str


@dataclass(frozen=True, slots=True)
class InferenceRuntimePreparation:
    """Preparation result for the active inference runtime."""

    attempted: bool
    success: bool
    detail: str


@dataclass(frozen=True, slots=True)
class InferenceRuntimeMetrics:
    """Latest provider-stage timing samples for operator visibility."""

    last_warmup_milliseconds: float | None = None
    last_warmup_outcome: str = "not_run"
    first_response_token_milliseconds: float | None = None
    first_response_token_outcome: str = "not_run"
    last_completion_milliseconds: float | None = None
    last_completion_outcome: str = "not_run"


@dataclass(frozen=True, slots=True)
class ProviderPayloadMetrics:
    """Latest first-round provider payload characteristics for operator visibility."""

    provider_message_count: int | None = None
    history_message_count: int | None = None
    tool_schema_count: int | None = None
    serialized_payload_characters: int | None = None
    used_lightweight_payload_strategy: bool | None = None


@dataclass(frozen=True, slots=True)
class _DirectAnswerResponseCacheEntry:
    """Cached direct-answer response for an identical first-round provider payload."""

    assistant_response: str
    recorded_at_monotonic_seconds: float
    used_lightweight_payload_strategy: bool


@dataclass(frozen=True, slots=True)
class _ToolInvocation:
    """Normalized function-call payload requested by the model."""

    call_id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _TurnEvent:
    """Internal event stream for a non-streaming chat turn."""

    kind: str
    content: str = ""
    tool_name: str = ""


@dataclass(frozen=True, slots=True)
class _ProviderCompletionEvent:
    """Intermediate or final output from a streamed provider completion round."""

    kind: str
    content: str = ""
    message: dict[str, Any] | None = None


class StreamedTurnCancelled(Exception):
    """Raised when a streamed browser turn ends before a final assistant reply exists."""


class _ClientDisconnectRequested(Exception):
    """Raised when the browser disconnects during a streamed provider request."""


def ensure_models() -> None:
    """Check that all Gemma-4 model files are present; download any that are missing.

    Files are resolved relative to the parent directory of
    ``config.LLAMACPP_MODEL_PATH`` (i.e. ``LLM/gemma-4/`` by default).
    Safe to call at startup — skips files that already exist.
    """
    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        TextColumn,
        TimeRemainingColumn,
        TransferSpeedColumn,
    )

    model_dir: Path = config.LLAMACPP_MODEL_PATH.parent
    model_dir.mkdir(parents=True, exist_ok=True)

    missing = [
        (name, url)
        for name, url in _MODEL_FILES
        if not (model_dir / name).is_file()
    ]

    if not missing:
        log.info("ensure_models: all model files present in %s", model_dir)
        return

    _console.print(
        f"[bold yellow]uZephyr:[/] {len(missing)} model file(s) missing — downloading now…"
    )

    with httpx.Client(timeout=httpx.Timeout(None, connect=30.0), follow_redirects=True) as client:
        for name, url in missing:
            dest = model_dir / name
            tmp = dest.with_suffix(dest.suffix + ".part")
            log.info("Downloading %s → %s", url, dest)
            _console.print(f"  [cyan]↓[/] [bold]{name}[/]")

            try:
                with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    total = int(resp.headers.get("content-length", 0)) or None

                    with Progress(
                        TextColumn("    [progress.description]{task.description}"),
                        BarColumn(),
                        DownloadColumn(),
                        TransferSpeedColumn(),
                        TimeRemainingColumn(),
                        console=_console,
                        transient=True,
                    ) as progress:
                        task = progress.add_task(name, total=total)
                        with tmp.open("wb") as fh:
                            for chunk in resp.iter_bytes(chunk_size=1 << 20):  # 1 MiB
                                fh.write(chunk)
                                progress.advance(task, len(chunk))

                tmp.replace(dest)
                _console.print(f"  [green]✓[/] {name} saved.")
                log.info("ensure_models: %s downloaded successfully.", name)

            except Exception as exc:
                if tmp.exists():
                    tmp.unlink(missing_ok=True)
                log.error("ensure_models: failed to download %s — %s", name, exc)
                _console.print(f"  [red]✗[/] Failed to download {name}: {exc}")
                raise RuntimeError(f"Could not download model file '{name}'") from exc


async def prepare_llamacpp_runtime() -> LlamaCppPreparation:
    """Prepare local LlamaCPP assets when the active provider requires them."""
    if config.LLM_PROVIDER != "llamacpp":
        return LlamaCppPreparation(
            attempted=False,
            success=True,
            detail="llamacpp provider is not active; model preparation skipped.",
        )

    if config.LLAMACPP_MODEL_PATH.is_file():
        return LlamaCppPreparation(
            attempted=False,
            success=True,
            detail=f"LlamaCPP model is already available at {config.LLAMACPP_MODEL_PATH}.",
        )

    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, ensure_models)
    except Exception as exc:
        return LlamaCppPreparation(
            attempted=True,
            success=False,
            detail=f"LlamaCPP model preparation failed: {exc}",
        )

    if config.LLAMACPP_MODEL_PATH.is_file():
        return LlamaCppPreparation(
            attempted=True,
            success=True,
            detail=f"LlamaCPP model prepared at {config.LLAMACPP_MODEL_PATH}.",
        )

    return LlamaCppPreparation(
        attempted=True,
        success=False,
        detail=f"Expected GGUF model at {config.LLAMACPP_MODEL_PATH}, but it is still missing after preparation.",
    )


def describe_llamacpp_preparation(preparation: LlamaCppPreparation) -> list[str]:
    """Render LlamaCPP preparation in a compact CLI-friendly format."""
    if preparation.success and preparation.attempted:
        status = "prepared"
    elif preparation.success:
        status = "ready"
    else:
        status = "failed"
    return [
        f"LlamaCPP preparation: {status}",
        f"LlamaCPP detail: {preparation.detail}",
    ]


def describe_inference_runtime_preparation(preparation: InferenceRuntimePreparation) -> list[str]:
    """Render active-provider warm-up details in a compact CLI-friendly format."""
    if preparation.success and preparation.attempted:
        status = "warmed"
    elif preparation.success:
        status = "ready"
    else:
        status = "failed"
    return [
        f"Inference runtime: {status}",
        f"Inference detail: {preparation.detail}",
    ]


class LLMRouter:
    """Thin async wrapper that routes chat completions to Ollama, OpenRouter, or LlamaCPP."""

    def __init__(self, tool_engine: ToolEngine, memory: MemoryManager) -> None:
        self.tool_engine = tool_engine
        self.memory = memory
        self._provider = config.LLM_PROVIDER
        self._client: httpx.AsyncClient | None = None
        # Lazy-loaded llama-cpp-python model (only when provider == "llamacpp")
        self._llama_model: Any | None = None
        self._inference_status = self._format_inference_status("yellow", "Cold", "provider runtime not warmed")
        self._inference_metrics = InferenceRuntimeMetrics()
        self._provider_payload_metrics = ProviderPayloadMetrics()
        self._direct_answer_response_cache: dict[str, _DirectAnswerResponseCacheEntry] = {}

    async def close(self) -> None:
        """Close the underlying HTTP client and free the LlamaCPP model."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        if self._llama_model is not None:
            del self._llama_model
            self._llama_model = None

    def _http_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
        return self._client

    # ── Provider-specific URL / headers ───────────────────────────────────
    def _base_url(self) -> str:
        if self._provider == "ollama":
            return f"{config.OLLAMA_BASE_URL}/v1"
        return "https://openrouter.ai/api/v1"

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._provider == "openrouter":
            headers["Authorization"] = f"Bearer {config.OPENROUTER_API_KEY}"
            headers["HTTP-Referer"] = "https://github.com/uzephyr"
            headers["X-Title"] = "uZephyr"
        return headers

    def _model(self) -> str:
        if self._provider == "ollama":
            return config.OLLAMA_MODEL
        return config.OPENROUTER_MODEL

    def describe_inference_status(self) -> str:
        """Return the current readiness summary for the active inference runtime."""
        return self._inference_status

    def describe_inference_metrics(self) -> dict[str, float | str | None]:
        """Return the latest provider-stage warm-up and completion timings."""
        metrics = self._inference_metrics
        return {
            "last_warmup_milliseconds": metrics.last_warmup_milliseconds,
            "last_warmup_outcome": metrics.last_warmup_outcome,
            "first_response_token_milliseconds": metrics.first_response_token_milliseconds,
            "first_response_token_outcome": metrics.first_response_token_outcome,
            "last_completion_milliseconds": metrics.last_completion_milliseconds,
            "last_completion_outcome": metrics.last_completion_outcome,
        }

    def describe_provider_payload_metrics(self) -> dict[str, int | bool | None]:
        """Return the most recent first-round provider payload characteristics."""
        payload_metrics = self._provider_payload_metrics
        return {
            "provider_message_count": payload_metrics.provider_message_count,
            "history_message_count": payload_metrics.history_message_count,
            "tool_schema_count": payload_metrics.tool_schema_count,
            "serialized_payload_characters": payload_metrics.serialized_payload_characters,
            "used_lightweight_payload_strategy": payload_metrics.used_lightweight_payload_strategy,
        }

    def _provider_label(self) -> str:
        if self._provider == "llamacpp":
            return "LlamaCPP"
        if self._provider == "openrouter":
            return "OpenRouter"
        return "Ollama"

    def _format_inference_status(self, color: str, label: str, detail: str) -> str:
        return f"[{color}]{label}[/] ({self._provider_label()}: {detail})"

    def _set_inference_status(self, color: str, label: str, detail: str) -> None:
        self._inference_status = self._format_inference_status(color, label, detail)

    def _mark_inference_ready(self, detail: str) -> None:
        self._set_inference_status("green", "Ready", detail)

    def mark_inference_warming(self, detail: str) -> None:
        self._set_inference_status("yellow", "Warming", detail)

    def _mark_inference_cold(self, detail: str) -> None:
        self._set_inference_status("yellow", "Cold", detail)

    def mark_inference_degraded(self, detail: str) -> None:
        self._mark_inference_degraded(detail)

    def _mark_inference_degraded(self, detail: str) -> None:
        self._set_inference_status("yellow", "Degraded", detail)

    def _record_inference_warmup(self, *, duration_milliseconds: float | None, outcome: str) -> None:
        self._inference_metrics = InferenceRuntimeMetrics(
            last_warmup_milliseconds=duration_milliseconds,
            last_warmup_outcome=outcome,
            first_response_token_milliseconds=self._inference_metrics.first_response_token_milliseconds,
            first_response_token_outcome=self._inference_metrics.first_response_token_outcome,
            last_completion_milliseconds=self._inference_metrics.last_completion_milliseconds,
            last_completion_outcome=self._inference_metrics.last_completion_outcome,
        )

    def _record_first_response_token(
        self,
        *,
        duration_milliseconds: float | None,
        outcome: str,
    ) -> None:
        self._inference_metrics = InferenceRuntimeMetrics(
            last_warmup_milliseconds=self._inference_metrics.last_warmup_milliseconds,
            last_warmup_outcome=self._inference_metrics.last_warmup_outcome,
            first_response_token_milliseconds=duration_milliseconds,
            first_response_token_outcome=outcome,
            last_completion_milliseconds=self._inference_metrics.last_completion_milliseconds,
            last_completion_outcome=self._inference_metrics.last_completion_outcome,
        )

    def _record_inference_completion(self, *, duration_milliseconds: float | None, outcome: str) -> None:
        self._inference_metrics = InferenceRuntimeMetrics(
            last_warmup_milliseconds=self._inference_metrics.last_warmup_milliseconds,
            last_warmup_outcome=self._inference_metrics.last_warmup_outcome,
            first_response_token_milliseconds=self._inference_metrics.first_response_token_milliseconds,
            first_response_token_outcome=self._inference_metrics.first_response_token_outcome,
            last_completion_milliseconds=duration_milliseconds,
            last_completion_outcome=outcome,
        )

    def _record_provider_payload_metrics(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        payload: dict[str, Any],
        *,
        history_message_count: int,
        used_lightweight_payload_strategy: bool,
    ) -> None:
        self._provider_payload_metrics = ProviderPayloadMetrics(
            provider_message_count=len(messages),
            history_message_count=history_message_count,
            tool_schema_count=len(tools),
            serialized_payload_characters=len(json.dumps(payload, ensure_ascii=True)),
            used_lightweight_payload_strategy=used_lightweight_payload_strategy,
        )

    async def prepare_inference_runtime(self) -> InferenceRuntimePreparation:
        """Warm the active provider runtime for a more predictable first live turn."""
        start = time.perf_counter()
        if self._provider == "llamacpp":
            if self._llama_model is not None:
                self._mark_inference_ready("provider runtime already warm")
                self._record_inference_warmup(
                    duration_milliseconds=round((time.perf_counter() - start) * 1000.0, 1),
                    outcome="already_warm",
                )
                return InferenceRuntimePreparation(
                    attempted=False,
                    success=True,
                    detail=f"LlamaCPP model is already loaded from {config.LLAMACPP_MODEL_PATH}.",
                )

            loop = asyncio.get_running_loop()
            try:
                await loop.run_in_executor(None, self._get_llama_model)
            except Exception as exc:
                self._mark_inference_degraded("warm-up failed")
                self._record_inference_warmup(
                    duration_milliseconds=round((time.perf_counter() - start) * 1000.0, 1),
                    outcome="failed",
                )
                return InferenceRuntimePreparation(
                    attempted=True,
                    success=False,
                    detail=f"LlamaCPP warm-up failed: {exc}",
                )

            self._mark_inference_ready("provider runtime warmed")
            self._record_inference_warmup(
                duration_milliseconds=round((time.perf_counter() - start) * 1000.0, 1),
                outcome="success",
            )
            return InferenceRuntimePreparation(
                attempted=True,
                success=True,
                detail=f"LlamaCPP model loaded into memory from {config.LLAMACPP_MODEL_PATH}.",
            )

        if self._provider == "ollama":
            warmup_url = f"{config.OLLAMA_BASE_URL}/api/tags"
            provider_name = "Ollama"
        else:
            warmup_url = f"{self._base_url()}/models"
            provider_name = "OpenRouter"

        try:
            response = await self._http_client().get(
                warmup_url,
                headers=self._headers(),
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self._mark_inference_degraded("warm-up failed")
            self._record_inference_warmup(
                duration_milliseconds=round((time.perf_counter() - start) * 1000.0, 1),
                outcome="http_error",
            )
            return InferenceRuntimePreparation(
                attempted=True,
                success=False,
                detail=f"{provider_name} warm-up failed ({exc.response.status_code}).",
            )
        except httpx.RequestError as exc:
            self._mark_inference_degraded("warm-up failed")
            self._record_inference_warmup(
                duration_milliseconds=round((time.perf_counter() - start) * 1000.0, 1),
                outcome="request_error",
            )
            return InferenceRuntimePreparation(
                attempted=True,
                success=False,
                detail=f"{provider_name} warm-up failed: {exc}",
            )

        self._mark_inference_ready("provider runtime warmed")
        self._record_inference_warmup(
            duration_milliseconds=round((time.perf_counter() - start) * 1000.0, 1),
            outcome="success",
        )
        return InferenceRuntimePreparation(
            attempted=True,
            success=True,
            detail=f"{provider_name} connection warmed via {warmup_url}.",
        )

    # ── LlamaCPP local model ──────────────────────────────────────────────
    def _get_llama_model(self) -> Any:
        """Lazy-load the llama-cpp-python model (heavy; only created once)."""
        if self._llama_model is not None:
            return self._llama_model

        # Close the zero-config gap for local inference: if the configured
        # GGUF assets are missing, fetch them before constructing LlamaCPP.
        ensure_models()

        from llama_cpp import Llama

        model_path = str(config.LLAMACPP_MODEL_PATH)
        kwargs: dict[str, Any] = {
            "model_path": model_path,
            "n_ctx": config.LLAMACPP_N_CTX,
            "n_gpu_layers": config.LLAMACPP_N_GPU_LAYERS,
            "flash_attn": True,  # <-- Add this line to fix the warning and boost speed
            "verbose": False,
        }

        # Optional vision support via mmproj
        # Gemma-4 extends the Gemma-3 vision architecture, so try handlers
        # in order of compatibility (newest → oldest fallback).
        mmproj = config.LLAMACPP_MMPROJ_PATH
        # Use is_file() to ensure we don't accidentally evaluate an empty Path(".")
        if mmproj and str(mmproj).strip() and mmproj.is_file():
            # VISION TEMPORARILY DISABLED PER USER REQUEST
            # To re-enable later, restore the handler logic here.
            log.info("LlamaCPP: mmproj path found, but vision is disabled. Running text-only.")

        # Explicit chat format override (leave empty to let the GGUF's
        # built-in Jinja2 chat template handle formatting automatically,
        # which is the recommended approach for Gemma-4).
        if config.LLAMACPP_CHAT_FORMAT and "chat_handler" not in kwargs:
            kwargs["chat_format"] = config.LLAMACPP_CHAT_FORMAT

        log.info("Loading LlamaCPP model: %s", model_path)
        self._llama_model = Llama(**kwargs)
        return self._llama_model

    async def _llamacpp_completion(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Run a chat completion through the local LlamaCPP model in a thread.

        Includes a fallback parser for Gemma-4's native ``<|tool_call>`` markers
        in case llama-cpp-python does not auto-detect them.
        """
        model = self._get_llama_model()
        kwargs: dict[str, Any] = {"messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, lambda: model.create_chat_completion(**kwargs)
        )

        # ── Gemma-4 fallback: parse native tool calls from raw content ────
        choice = result.get("choices", [{}])[0]
        message = choice.get("message", {})

        if not message.get("tool_calls") and tools:
            content = message.get("content", "")
            gemma4_calls = _parse_gemma4_tool_calls(content)
            if gemma4_calls:
                message["tool_calls"] = gemma4_calls
                message["content"] = _strip_gemma4_tool_markers(content)
                choice["message"] = message
                choice["finish_reason"] = "tool_calls"
                log.debug("Parsed %d Gemma-4 native tool call(s)", len(gemma4_calls))

        return result

    # ── Build OpenAI-style messages list ──────────────────────────────────
    @staticmethod
    def _build_messages(
        system_prompt: str,
        history: list[dict[str, str]],
        user_message: str,
        *,
        include_history: bool = True,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        if include_history:
            for entry in history:
                messages.append({"role": entry["role"], "content": entry["content"]})
        messages.append({"role": "user", "content": user_message})
        return messages

    # ── Tool definitions in OpenAI function-calling schema ────────────────
    @staticmethod
    def _message_explicitly_disables_tools(user_message: str) -> bool:
        return bool(_EXPLICIT_NO_TOOL_PROMPT_RE.search(user_message))

    @staticmethod
    def _message_requests_exact_direct_answer(user_message: str) -> bool:
        return bool(_EXACT_DIRECT_ANSWER_PROMPT_RE.search(user_message))

    def _message_prefers_lightweight_provider_payload(self, user_message: str) -> bool:
        return self._message_requests_exact_direct_answer(user_message)

    @staticmethod
    def _system_prompt_for_lightweight_provider_payload(system_prompt: str) -> str:
        compact_system_prompt, durable_facts_separator, _durable_facts = system_prompt.partition(
            _DURABLE_FACTS_SECTION_MARKER
        )
        if not durable_facts_separator:
            return system_prompt
        return compact_system_prompt.rstrip()

    @staticmethod
    def _extract_local_exact_direct_answer(user_message: str) -> str | None:
        direct_answer_match = _LOCAL_EXACT_DIRECT_ANSWER_RE.fullmatch(user_message)
        if direct_answer_match is None:
            return None

        quoted_answer = direct_answer_match.group("quoted_answer")
        if quoted_answer is not None:
            if "\n" in quoted_answer or "\r" in quoted_answer:
                return None
            return quoted_answer

        bare_answer = direct_answer_match.group("bare_answer")
        if bare_answer is None:
            return None
        return bare_answer

    def _record_local_exact_direct_answer_metrics(self) -> None:
        self._record_first_response_token(duration_milliseconds=0.0, outcome="local_fast_path")
        self._record_inference_completion(duration_milliseconds=0.0, outcome="local_fast_path")
        self._provider_payload_metrics = ProviderPayloadMetrics(
            provider_message_count=0,
            history_message_count=0,
            tool_schema_count=0,
            serialized_payload_characters=0,
            used_lightweight_payload_strategy=True,
        )

    def _record_local_response_cache_metrics(self, *, used_lightweight_payload_strategy: bool) -> None:
        self._record_first_response_token(duration_milliseconds=0.0, outcome="local_response_cache")
        self._record_inference_completion(duration_milliseconds=0.0, outcome="local_response_cache")
        self._provider_payload_metrics = ProviderPayloadMetrics(
            provider_message_count=0,
            history_message_count=0,
            tool_schema_count=0,
            serialized_payload_characters=0,
            used_lightweight_payload_strategy=used_lightweight_payload_strategy,
        )

    def _build_direct_answer_response_cache_key(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> str:
        return json.dumps(
            {
                "model": self._model(),
                "messages": messages,
                "tools": tools,
            },
            ensure_ascii=True,
            sort_keys=True,
        )

    def _cached_direct_answer_response(
        self,
        direct_answer_response_cache_key: str,
    ) -> _DirectAnswerResponseCacheEntry | None:
        cached_direct_answer_response = self._direct_answer_response_cache.get(direct_answer_response_cache_key)
        if cached_direct_answer_response is None:
            return None

        cache_entry_age_seconds = time.perf_counter() - cached_direct_answer_response.recorded_at_monotonic_seconds
        if cache_entry_age_seconds > _DIRECT_ANSWER_RESPONSE_CACHE_TIME_TO_LIVE_SECONDS:
            self._direct_answer_response_cache.pop(direct_answer_response_cache_key, None)
            return None

        self._direct_answer_response_cache.pop(direct_answer_response_cache_key, None)
        self._direct_answer_response_cache[direct_answer_response_cache_key] = cached_direct_answer_response
        return cached_direct_answer_response

    def _store_direct_answer_response_in_cache(
        self,
        direct_answer_response_cache_key: str,
        assistant_response: str,
        *,
        used_lightweight_payload_strategy: bool,
    ) -> None:
        if not assistant_response.strip():
            return

        self._direct_answer_response_cache.pop(direct_answer_response_cache_key, None)
        self._direct_answer_response_cache[direct_answer_response_cache_key] = _DirectAnswerResponseCacheEntry(
            assistant_response=assistant_response,
            recorded_at_monotonic_seconds=time.perf_counter(),
            used_lightweight_payload_strategy=used_lightweight_payload_strategy,
        )
        while len(self._direct_answer_response_cache) > _DIRECT_ANSWER_RESPONSE_CACHE_MAXIMUM_ENTRIES:
            oldest_direct_answer_response_cache_key = next(iter(self._direct_answer_response_cache))
            self._direct_answer_response_cache.pop(oldest_direct_answer_response_cache_key, None)

    def _tool_schemas(
        self,
        user_message: str,
        *,
        allowed_tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if self._message_explicitly_disables_tools(user_message):
            return []

        return self.tool_engine.get_openai_tool_schemas(
            allowed_tags=allowed_tags,
            compact_for_provider=True,
        )

    def _build_chat_completion_payload(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        stream: bool,
        capture_payload_metrics: bool = False,
        history_message_count: int = 0,
        used_lightweight_payload_strategy: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model(),
            "messages": messages,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        if capture_payload_metrics:
            self._record_provider_payload_metrics(
                messages,
                tools,
                payload,
                history_message_count=history_message_count,
                used_lightweight_payload_strategy=used_lightweight_payload_strategy,
            )
        return payload

    def _provider_supports_streamed_chat_completions(self) -> bool:
        return self._provider in {"ollama", "openrouter"}

    @staticmethod
    def _message_from_completion_payload(completion_payload: dict[str, Any] | None) -> dict[str, Any]:
        return (completion_payload or {}).get("choices", [{}])[0].get("message", {})

    @staticmethod
    def _accumulate_streamed_tool_calls(
        accumulated_tool_calls: list[dict[str, Any]],
        streamed_tool_calls: list[dict[str, Any]],
    ) -> None:
        for streamed_tool_call in streamed_tool_calls:
            raw_index = streamed_tool_call.get("index", len(accumulated_tool_calls))
            try:
                tool_call_index = int(raw_index)
            except (TypeError, ValueError):
                tool_call_index = len(accumulated_tool_calls)

            while len(accumulated_tool_calls) <= tool_call_index:
                accumulated_tool_calls.append(
                    {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    }
                )

            accumulated_tool_call = accumulated_tool_calls[tool_call_index]
            streamed_identifier = streamed_tool_call.get("id")
            if streamed_identifier:
                accumulated_tool_call["id"] = streamed_identifier

            streamed_type = streamed_tool_call.get("type")
            if streamed_type:
                accumulated_tool_call["type"] = streamed_type

            streamed_function = streamed_tool_call.get("function", {})
            accumulated_function = accumulated_tool_call.setdefault(
                "function",
                {"name": "", "arguments": ""},
            )
            streamed_function_name = streamed_function.get("name")
            if streamed_function_name:
                accumulated_function["name"] += streamed_function_name

            streamed_arguments = streamed_function.get("arguments")
            if streamed_arguments:
                accumulated_function["arguments"] += streamed_arguments

    @staticmethod
    def _build_streamed_completion_message(
        accumulated_content: list[str],
        accumulated_tool_calls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        message: dict[str, Any] = {"content": "".join(accumulated_content)}
        if accumulated_tool_calls:
            message["tool_calls"] = accumulated_tool_calls
        return message

    async def _read_provider_stream_line(
        self,
        line_iterator: AsyncIterator[str],
        client_disconnect_check: Callable[[], Awaitable[bool]] | None,
    ) -> str:
        pending_line_task = asyncio.create_task(line_iterator.__anext__())
        try:
            while True:
                completed_tasks, _ = await asyncio.wait({pending_line_task}, timeout=0.25)
                if completed_tasks:
                    return pending_line_task.result()

                if client_disconnect_check is not None and await client_disconnect_check():
                    pending_line_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await pending_line_task
                    raise _ClientDisconnectRequested()
        finally:
            if not pending_line_task.done():
                pending_line_task.cancel()
                with suppress(asyncio.CancelledError):
                    await pending_line_task

    async def _stream_chat_completion_events(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        client_disconnect_check: Callable[[], Awaitable[bool]] | None = None,
        capture_payload_metrics: bool = False,
        history_message_count: int = 0,
        used_lightweight_payload_strategy: bool = False,
    ) -> AsyncGenerator[_ProviderCompletionEvent, None]:
        if not self._provider_supports_streamed_chat_completions():
            completion_payload, error_message = await self._request_chat_completion(
                messages,
                tools,
                capture_payload_metrics=capture_payload_metrics,
                history_message_count=history_message_count,
                used_lightweight_payload_strategy=used_lightweight_payload_strategy,
            )
            if error_message is not None:
                yield _ProviderCompletionEvent(kind="error", content=error_message)
                return

            yield _ProviderCompletionEvent(
                kind="complete",
                message=self._message_from_completion_payload(completion_payload),
            )
            return

        start = time.perf_counter()
        first_response_token_recorded = False
        accumulated_content: list[str] = []
        accumulated_tool_calls: list[dict[str, Any]] = []
        payload = self._build_chat_completion_payload(
            messages,
            tools,
            stream=True,
            capture_payload_metrics=capture_payload_metrics,
            history_message_count=history_message_count,
            used_lightweight_payload_strategy=used_lightweight_payload_strategy,
        )

        try:
            async with self._http_client().stream(
                "POST",
                f"{self._base_url()}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                line_iterator = response.aiter_lines()

                while True:
                    try:
                        line = await self._read_provider_stream_line(line_iterator, client_disconnect_check)
                    except StopAsyncIteration:
                        break

                    if not line.startswith("data: "):
                        continue

                    streamed_payload = line[len("data: "):].strip()
                    if streamed_payload == "[DONE]":
                        break

                    try:
                        chunk = json.loads(streamed_payload)
                    except json.JSONDecodeError:
                        continue

                    choice = chunk.get("choices", [{}])[0]
                    delta = choice.get("delta", {})
                    content_fragment = delta.get("content")
                    streamed_tool_calls = delta.get("tool_calls") or []
                    if streamed_tool_calls:
                        self._accumulate_streamed_tool_calls(accumulated_tool_calls, streamed_tool_calls)

                    if not first_response_token_recorded and (content_fragment or streamed_tool_calls):
                        self._record_first_response_token(
                            duration_milliseconds=round((time.perf_counter() - start) * 1000.0, 1),
                            outcome="success",
                        )
                        first_response_token_recorded = True

                    if isinstance(content_fragment, str) and content_fragment:
                        accumulated_content.append(content_fragment)
                        yield _ProviderCompletionEvent(
                            kind="content_snapshot",
                            content="".join(accumulated_content),
                        )
        except _ClientDisconnectRequested:
            if not first_response_token_recorded:
                self._record_first_response_token(duration_milliseconds=None, outcome="cancelled")
            self._mark_inference_ready("live request path warmed")
            self._record_inference_completion(
                duration_milliseconds=round((time.perf_counter() - start) * 1000.0, 1),
                outcome="cancelled",
            )
            log.debug("Cancelled streamed provider request after browser disconnect.")
            yield _ProviderCompletionEvent(kind="cancelled")
            return
        except httpx.HTTPStatusError as exc:
            log.error("LLM HTTP error: %s – %s", exc.response.status_code, exc.response.text[:500])
            self._mark_inference_degraded("live request failed")
            self._record_first_response_token(duration_milliseconds=None, outcome="http_error")
            self._record_inference_completion(
                duration_milliseconds=round((time.perf_counter() - start) * 1000.0, 1),
                outcome="http_error",
            )
            yield _ProviderCompletionEvent(
                kind="error",
                content=f"⚠️ LLM request failed ({exc.response.status_code}). Check your provider settings.",
            )
            return
        except httpx.RequestError as exc:
            log.error("LLM connection error: %s", exc)
            self._mark_inference_degraded("live request failed")
            self._record_first_response_token(duration_milliseconds=None, outcome="request_error")
            self._record_inference_completion(
                duration_milliseconds=round((time.perf_counter() - start) * 1000.0, 1),
                outcome="request_error",
            )
            yield _ProviderCompletionEvent(
                kind="error",
                content="⚠️ Could not reach the LLM. Is Ollama running?",
            )
            return

        if not first_response_token_recorded:
            self._record_first_response_token(duration_milliseconds=None, outcome="empty")

        self._mark_inference_ready("live request path warmed")
        self._record_inference_completion(
            duration_milliseconds=round((time.perf_counter() - start) * 1000.0, 1),
            outcome="success",
        )
        yield _ProviderCompletionEvent(
            kind="complete",
            message=self._build_streamed_completion_message(accumulated_content, accumulated_tool_calls),
        )

    async def _request_chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        capture_payload_metrics: bool = False,
        history_message_count: int = 0,
        used_lightweight_payload_strategy: bool = False,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Request one completion round and normalize provider failures to user text."""
        start = time.perf_counter()
        if self._provider == "llamacpp":
            try:
                self._build_chat_completion_payload(
                    messages,
                    tools,
                    stream=False,
                    capture_payload_metrics=capture_payload_metrics,
                    history_message_count=history_message_count,
                    used_lightweight_payload_strategy=used_lightweight_payload_strategy,
                )
                data = await self._llamacpp_completion(messages, tools)
                self._record_first_response_token(duration_milliseconds=None, outcome="not_streamed")
                self._mark_inference_ready("live request path warmed")
                self._record_inference_completion(
                    duration_milliseconds=round((time.perf_counter() - start) * 1000.0, 1),
                    outcome="success",
                )
                return data, None
            except Exception as exc:
                log.error("LlamaCPP error: %s", exc)
                self._mark_inference_degraded("live request failed")
                self._record_first_response_token(duration_milliseconds=None, outcome="failed")
                self._record_inference_completion(
                    duration_milliseconds=round((time.perf_counter() - start) * 1000.0, 1),
                    outcome="failed",
                )
                return None, f"⚠️ LlamaCPP inference failed: {exc}"

        payload = self._build_chat_completion_payload(
            messages,
            tools,
            stream=False,
            capture_payload_metrics=capture_payload_metrics,
            history_message_count=history_message_count,
            used_lightweight_payload_strategy=used_lightweight_payload_strategy,
        )

        try:
            resp = await self._http_client().post(
                f"{self._base_url()}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            self._record_first_response_token(duration_milliseconds=None, outcome="not_streamed")
            self._mark_inference_ready("live request path warmed")
            self._record_inference_completion(
                duration_milliseconds=round((time.perf_counter() - start) * 1000.0, 1),
                outcome="success",
            )
        except httpx.HTTPStatusError as exc:
            log.error("LLM HTTP error: %s – %s", exc.response.status_code, exc.response.text[:500])
            self._mark_inference_degraded("live request failed")
            self._record_first_response_token(duration_milliseconds=None, outcome="http_error")
            self._record_inference_completion(
                duration_milliseconds=round((time.perf_counter() - start) * 1000.0, 1),
                outcome="http_error",
            )
            return None, f"⚠️ LLM request failed ({exc.response.status_code}). Check your provider settings."
        except httpx.RequestError as exc:
            log.error("LLM connection error: %s", exc)
            self._mark_inference_degraded("live request failed")
            self._record_first_response_token(duration_milliseconds=None, outcome="request_error")
            self._record_inference_completion(
                duration_milliseconds=round((time.perf_counter() - start) * 1000.0, 1),
                outcome="request_error",
            )
            return None, "⚠️ Could not reach the LLM. Is Ollama running?"

        return resp.json(), None

    @staticmethod
    def _parse_tool_invocation(tool_call: dict[str, Any]) -> _ToolInvocation:
        func = tool_call.get("function", {})
        fn_name = func.get("name", "")
        raw_args = func.get("arguments", "{}")
        call_id = tool_call.get("id", "")

        try:
            fn_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError:
            fn_args = {}

        return _ToolInvocation(
            call_id=call_id,
            name=fn_name,
            args=fn_args if isinstance(fn_args, dict) else {},
        )

    async def _chat_turn_events(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        allowed_tags: list[str] | None = None,
        console: Console | None = None,
        allow_sensitive_tools: bool | None = None,
        stream_provider_responses: bool = False,
        client_disconnect_check: Callable[[], Awaitable[bool]] | None = None,
        history_message_count: int = 0,
        used_lightweight_payload_strategy: bool = False,
    ) -> AsyncGenerator[_TurnEvent, None]:
        """Yield internal chat-turn events while handling tool-call rounds."""
        capture_payload_metrics_for_round = True
        for _round in range(_MAX_TOOL_ROUNDS):
            yield _TurnEvent(kind="thinking_start")
            if stream_provider_responses:
                message: dict[str, Any] = {}
                async for provider_completion_event in self._stream_chat_completion_events(
                    messages,
                    tools,
                    client_disconnect_check=client_disconnect_check,
                    capture_payload_metrics=capture_payload_metrics_for_round,
                    history_message_count=history_message_count,
                    used_lightweight_payload_strategy=used_lightweight_payload_strategy,
                ):
                    if provider_completion_event.kind == "content_snapshot":
                        yield _TurnEvent(kind="content_snapshot", content=provider_completion_event.content)
                        continue
                    if provider_completion_event.kind == "error":
                        yield _TurnEvent(kind="error", content=provider_completion_event.content)
                        return
                    if provider_completion_event.kind == "cancelled":
                        yield _TurnEvent(kind="cancelled")
                        return
                    if provider_completion_event.kind == "complete":
                        message = provider_completion_event.message or {}
            else:
                data, error_message = await self._request_chat_completion(
                    messages,
                    tools,
                    capture_payload_metrics=capture_payload_metrics_for_round,
                    history_message_count=history_message_count,
                    used_lightweight_payload_strategy=used_lightweight_payload_strategy,
                )
                if error_message is not None:
                    yield _TurnEvent(kind="error", content=error_message)
                    return

                message = self._message_from_completion_payload(data)

            capture_payload_metrics_for_round = False

            yield _TurnEvent(kind="thinking_end")

            tool_calls = message.get("tool_calls")
            if not tool_calls:
                yield _TurnEvent(kind="final", content=message.get("content", ""))
                return

            messages.append(message)
            for tool_call in tool_calls:
                invocation = self._parse_tool_invocation(tool_call)
                yield _TurnEvent(kind="tool_start", tool_name=invocation.name)
                result = await self.tool_engine.execute(
                    invocation.name,
                    invocation.args,
                    allowed_tags=allowed_tags,
                    console=console,
                    allow_sensitive_tools=allow_sensitive_tools,
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": invocation.call_id,
                    "content": str(result),
                })
                yield _TurnEvent(kind="tool_end", tool_name=invocation.name)

        yield _TurnEvent(kind="final", content="⚠️ Maximum tool-call depth reached. Please try again.")

    # ── Core chat method with streaming + tool-call loop ──────────────────
    async def chat(
        self,
        system_prompt: str,
        history: list[dict[str, str]],
        user_message: str,
        console: Console,
        live: Any | None = None,
        allowed_tags: list[str] | None = None,
        allow_sensitive_tools: bool | None = None,
    ) -> str:
        local_exact_direct_answer = self._extract_local_exact_direct_answer(user_message)
        if local_exact_direct_answer is not None:
            self._record_local_exact_direct_answer_metrics()
            return local_exact_direct_answer

        used_lightweight_payload_strategy = self._message_prefers_lightweight_provider_payload(user_message)
        system_prompt_for_provider_payload = (
            self._system_prompt_for_lightweight_provider_payload(system_prompt)
            if used_lightweight_payload_strategy
            else system_prompt
        )
        messages = self._build_messages(
            system_prompt_for_provider_payload,
            history,
            user_message,
            include_history=not used_lightweight_payload_strategy,
        )
        tools = self._tool_schemas(user_message, allowed_tags=allowed_tags)
        direct_answer_response_cache_key = self._build_direct_answer_response_cache_key(messages, tools)
        cached_direct_answer_response = self._cached_direct_answer_response(direct_answer_response_cache_key)
        if cached_direct_answer_response is not None:
            self._record_local_response_cache_metrics(
                used_lightweight_payload_strategy=cached_direct_answer_response.used_lightweight_payload_strategy,
            )
            return cached_direct_answer_response.assistant_response

        saw_tool_invocation = False

        async for event in self._chat_turn_events(
            messages,
            tools,
            allowed_tags=allowed_tags,
            console=console,
            allow_sensitive_tools=allow_sensitive_tools,
            history_message_count=len(history) if not used_lightweight_payload_strategy else 0,
            used_lightweight_payload_strategy=used_lightweight_payload_strategy,
        ):
            if event.kind == "tool_start":
                saw_tool_invocation = True
                if live:
                    live.stop()
                if console:
                    console.print(f"  [dim cyan]⚙ calling tool:[/] [bold]{event.tool_name}[/]", highlight=False)
                continue

            if event.kind == "tool_end":
                saw_tool_invocation = True
                if live:
                    live.start()
                continue

            if event.kind == "final":
                if not saw_tool_invocation:
                    self._store_direct_answer_response_in_cache(
                        direct_answer_response_cache_key,
                        event.content,
                        used_lightweight_payload_strategy=used_lightweight_payload_strategy,
                    )
                return event.content

            if event.kind == "error":
                return event.content

        return "⚠️ Maximum tool-call depth reached. Please try again."

    # ── Generator variant for the hybrid web interface ───────────────
    async def chat_stream_gui(
        self,
        system_prompt: str,
        history: list[dict[str, str]],
        user_message: str,
        *,
        allow_sensitive_tools: bool | None = None,
        client_disconnect_check: Callable[[], Awaitable[bool]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Async generator that yields status updates during tool calls, then the final answer."""
        local_exact_direct_answer = self._extract_local_exact_direct_answer(user_message)
        if local_exact_direct_answer is not None:
            self._record_local_exact_direct_answer_metrics()
            yield local_exact_direct_answer
            return

        used_lightweight_payload_strategy = self._message_prefers_lightweight_provider_payload(user_message)
        system_prompt_for_provider_payload = (
            self._system_prompt_for_lightweight_provider_payload(system_prompt)
            if used_lightweight_payload_strategy
            else system_prompt
        )
        messages = self._build_messages(
            system_prompt_for_provider_payload,
            history,
            user_message,
            include_history=not used_lightweight_payload_strategy,
        )
        tools = self._tool_schemas(user_message)
        direct_answer_response_cache_key = self._build_direct_answer_response_cache_key(messages, tools)
        cached_direct_answer_response = self._cached_direct_answer_response(direct_answer_response_cache_key)
        if cached_direct_answer_response is not None:
            self._record_local_response_cache_metrics(
                used_lightweight_payload_strategy=cached_direct_answer_response.used_lightweight_payload_strategy,
            )
            yield cached_direct_answer_response.assistant_response
            return

        status_lines: list[str] = []
        last_emitted_snapshot = ""
        saw_tool_invocation = False

        async for event in self._chat_turn_events(
            messages,
            tools,
            allow_sensitive_tools=allow_sensitive_tools,
            stream_provider_responses=True,
            client_disconnect_check=client_disconnect_check,
            history_message_count=len(history) if not used_lightweight_payload_strategy else 0,
            used_lightweight_payload_strategy=used_lightweight_payload_strategy,
        ):
            if event.kind == "thinking_start":
                status_lines.append("*🔄 Thinking…*")
                last_emitted_snapshot = "\n\n".join(status_lines)
                yield last_emitted_snapshot
                continue

            if event.kind == "thinking_end":
                if status_lines:
                    status_lines.pop()
                continue

            if event.kind == "content_snapshot":
                if status_lines and status_lines[-1] == "*🔄 Thinking…*":
                    status_lines.pop()

                if status_lines:
                    last_emitted_snapshot = "\n\n".join([*status_lines, event.content])
                else:
                    last_emitted_snapshot = event.content

                yield last_emitted_snapshot
                continue

            if event.kind == "tool_start":
                saw_tool_invocation = True
                status_lines.append(f"*⚙ Calling tool: **{event.tool_name}**…*")
                last_emitted_snapshot = "\n\n".join(status_lines)
                yield last_emitted_snapshot
                continue

            if event.kind == "tool_end":
                saw_tool_invocation = True
                if status_lines:
                    status_lines[-1] = f"*✅ {event.tool_name} — done*"
                last_emitted_snapshot = "\n\n".join(status_lines)
                yield last_emitted_snapshot
                continue

            if event.kind == "cancelled":
                raise StreamedTurnCancelled()

            if event.kind == "error":
                if event.content != last_emitted_snapshot:
                    yield event.content
                return

            if event.kind == "final":
                if not saw_tool_invocation:
                    self._store_direct_answer_response_in_cache(
                        direct_answer_response_cache_key,
                        event.content,
                        used_lightweight_payload_strategy=used_lightweight_payload_strategy,
                    )
                if event.content != last_emitted_snapshot:
                    yield event.content
                return

        yield "⚠️ Maximum tool-call depth reached. Please try again."

    # ── Streaming variant (for future use / providers that support it) ────
    async def chat_stream(
        self,
        system_prompt: str,
        history: list[dict[str, str]],
        user_message: str,
        console: Console,
    ) -> str:
        """Stream tokens to the console and return the full text."""
        messages = self._build_messages(system_prompt, history, user_message)
        payload: dict[str, Any] = {
            "model": self._model(),
            "messages": messages,
            "stream": True,
        }
        collected: list[str] = []
        try:
            async with self._http_client().stream(
                "POST",
                f"{self._base_url()}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    chunk_str = line[len("data: "):]
                    if chunk_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(chunk_str)
                    except json.JSONDecodeError:
                        continue
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        console.print(Text(token, end=""), end="")
                        collected.append(token)
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            log.error("Stream error: %s", exc)
            return "⚠️ Streaming failed."

        console.print()
        return "".join(collected)
