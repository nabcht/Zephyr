"""LLM provider router — Ollama (local), OpenRouter (cloud), and LlamaCPP (local GGUF)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, TYPE_CHECKING

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

    last_warmup_ms: float | None = None
    last_warmup_outcome: str = "not_run"
    last_completion_ms: float | None = None
    last_completion_outcome: str = "not_run"


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
            "last_warmup_ms": metrics.last_warmup_ms,
            "last_warmup_outcome": metrics.last_warmup_outcome,
            "last_completion_ms": metrics.last_completion_ms,
            "last_completion_outcome": metrics.last_completion_outcome,
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

    def _record_inference_warmup(self, *, duration_ms: float | None, outcome: str) -> None:
        self._inference_metrics = InferenceRuntimeMetrics(
            last_warmup_ms=duration_ms,
            last_warmup_outcome=outcome,
            last_completion_ms=self._inference_metrics.last_completion_ms,
            last_completion_outcome=self._inference_metrics.last_completion_outcome,
        )

    def _record_inference_completion(self, *, duration_ms: float | None, outcome: str) -> None:
        self._inference_metrics = InferenceRuntimeMetrics(
            last_warmup_ms=self._inference_metrics.last_warmup_ms,
            last_warmup_outcome=self._inference_metrics.last_warmup_outcome,
            last_completion_ms=duration_ms,
            last_completion_outcome=outcome,
        )

    async def prepare_inference_runtime(self) -> InferenceRuntimePreparation:
        """Warm the active provider runtime for a more predictable first live turn."""
        start = time.perf_counter()
        if self._provider == "llamacpp":
            if self._llama_model is not None:
                self._mark_inference_ready("provider runtime already warm")
                self._record_inference_warmup(
                    duration_ms=round((time.perf_counter() - start) * 1000.0, 1),
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
                    duration_ms=round((time.perf_counter() - start) * 1000.0, 1),
                    outcome="failed",
                )
                return InferenceRuntimePreparation(
                    attempted=True,
                    success=False,
                    detail=f"LlamaCPP warm-up failed: {exc}",
                )

            self._mark_inference_ready("provider runtime warmed")
            self._record_inference_warmup(
                duration_ms=round((time.perf_counter() - start) * 1000.0, 1),
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
                duration_ms=round((time.perf_counter() - start) * 1000.0, 1),
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
                duration_ms=round((time.perf_counter() - start) * 1000.0, 1),
                outcome="request_error",
            )
            return InferenceRuntimePreparation(
                attempted=True,
                success=False,
                detail=f"{provider_name} warm-up failed: {exc}",
            )

        self._mark_inference_ready("provider runtime warmed")
        self._record_inference_warmup(
            duration_ms=round((time.perf_counter() - start) * 1000.0, 1),
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
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for entry in history:
            messages.append({"role": entry["role"], "content": entry["content"]})
        messages.append({"role": "user", "content": user_message})
        return messages

    # ── Tool definitions in OpenAI function-calling schema ────────────────
    def _tool_schemas(self, allowed_tags: list[str] | None = None) -> list[dict[str, Any]]:
        return self.tool_engine.get_openai_tool_schemas(allowed_tags=allowed_tags)

    async def _request_chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Request one completion round and normalize provider failures to user text."""
        start = time.perf_counter()
        if self._provider == "llamacpp":
            try:
                data = await self._llamacpp_completion(messages, tools)
                self._mark_inference_ready("live request path warmed")
                self._record_inference_completion(
                    duration_ms=round((time.perf_counter() - start) * 1000.0, 1),
                    outcome="success",
                )
                return data, None
            except Exception as exc:
                log.error("LlamaCPP error: %s", exc)
                self._mark_inference_degraded("live request failed")
                self._record_inference_completion(
                    duration_ms=round((time.perf_counter() - start) * 1000.0, 1),
                    outcome="failed",
                )
                return None, f"⚠️ LlamaCPP inference failed: {exc}"

        payload: dict[str, Any] = {
            "model": self._model(),
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            resp = await self._http_client().post(
                f"{self._base_url()}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            self._mark_inference_ready("live request path warmed")
            self._record_inference_completion(
                duration_ms=round((time.perf_counter() - start) * 1000.0, 1),
                outcome="success",
            )
        except httpx.HTTPStatusError as exc:
            log.error("LLM HTTP error: %s – %s", exc.response.status_code, exc.response.text[:500])
            self._mark_inference_degraded("live request failed")
            self._record_inference_completion(
                duration_ms=round((time.perf_counter() - start) * 1000.0, 1),
                outcome="http_error",
            )
            return None, f"⚠️ LLM request failed ({exc.response.status_code}). Check your provider settings."
        except httpx.RequestError as exc:
            log.error("LLM connection error: %s", exc)
            self._mark_inference_degraded("live request failed")
            self._record_inference_completion(
                duration_ms=round((time.perf_counter() - start) * 1000.0, 1),
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
    ) -> AsyncGenerator[_TurnEvent, None]:
        """Yield internal chat-turn events while handling tool-call rounds."""
        for _round in range(_MAX_TOOL_ROUNDS):
            yield _TurnEvent(kind="thinking_start")
            data, error_message = await self._request_chat_completion(messages, tools)
            if error_message is not None:
                yield _TurnEvent(kind="error", content=error_message)
                return

            yield _TurnEvent(kind="thinking_end")

            choice = (data or {}).get("choices", [{}])[0]
            message = choice.get("message", {})
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
        messages = self._build_messages(system_prompt, history, user_message)
        tools = self._tool_schemas(allowed_tags=allowed_tags)

        async for event in self._chat_turn_events(
            messages,
            tools,
            allowed_tags=allowed_tags,
            console=console,
            allow_sensitive_tools=allow_sensitive_tools,
        ):
            if event.kind == "tool_start":
                if live:
                    live.stop()
                if console:
                    console.print(f"  [dim cyan]⚙ calling tool:[/] [bold]{event.tool_name}[/]", highlight=False)
                continue

            if event.kind == "tool_end":
                if live:
                    live.start()
                continue

            if event.kind in {"final", "error"}:
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
    ) -> AsyncGenerator[str, None]:
        """Async generator that yields status updates during tool calls, then the final answer."""
        messages = self._build_messages(system_prompt, history, user_message)
        tools = self._tool_schemas()
        status_lines: list[str] = []

        async for event in self._chat_turn_events(
            messages,
            tools,
            allow_sensitive_tools=allow_sensitive_tools,
        ):
            if event.kind == "thinking_start":
                status_lines.append("*🔄 Thinking…*")
                yield "\n\n".join(status_lines)
                continue

            if event.kind == "thinking_end":
                if status_lines:
                    status_lines.pop()
                continue

            if event.kind == "tool_start":
                status_lines.append(f"*⚙ Calling tool: **{event.tool_name}**…*")
                yield "\n\n".join(status_lines)
                continue

            if event.kind == "tool_end":
                if status_lines:
                    status_lines[-1] = f"*✅ {event.tool_name} — done*"
                yield "\n\n".join(status_lines)
                continue

            if event.kind in {"final", "error"}:
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
