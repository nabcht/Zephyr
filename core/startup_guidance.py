"""Startup guidance for local prerequisites and zero-config gaps."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

import config
from core.embedding_model import embedding_model_is_cached
from skills.sandbox.scripts.sandbox import get_sandbox_readiness


@dataclass(frozen=True, slots=True)
class StartupAction:
    """A concrete startup action surfaced to the user."""

    level: str
    badge: str
    label: str
    summary: str
    command: str | None = None
    supports_prepare: bool = False


@dataclass(frozen=True, slots=True)
class StartupGuidance:
    """Actionable startup guidance for the current runtime configuration."""

    level: str
    badge: str
    title: str
    actions: tuple[StartupAction, ...]


def _badge_for(level: str) -> str:
    return {
        "green": "🟢",
        "yellow": "🟡",
        "red": "🔴",
    }.get(level, "⚪")


def _make_action(
    level: str,
    label: str,
    summary: str,
    command: str | None = None,
    *,
    supports_prepare: bool = False,
) -> StartupAction:
    return StartupAction(
        level=level,
        badge=_badge_for(level),
        label=label,
        summary=summary,
        command=command,
        supports_prepare=supports_prepare,
    )


def _probe_ollama_models() -> tuple[bool, set[str], str]:
    url = config.OLLAMA_BASE_URL.rstrip("/")
    try:
        with httpx.Client(timeout=httpx.Timeout(1.5, connect=0.5)) as client:
            response = client.get(f"{url}/api/tags")
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        return False, set(), f"Ollama is not reachable at {url}. {exc}"

    models = {
        str(item.get("name", "")).strip()
        for item in payload.get("models", [])
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    }
    return True, models, f"Ollama is reachable at {url}."


def _collect_provider_actions() -> tuple[StartupAction, ...]:
    provider = config.LLM_PROVIDER

    if provider == "ollama":
        reachable, models, detail = _probe_ollama_models()
        if not reachable:
            return (
                _make_action(
                    "red",
                    "Ollama",
                    f"{detail} Install or start Ollama before launching chat.",
                    command=f"ollama pull {config.OLLAMA_MODEL}",
                ),
            )
        if config.OLLAMA_MODEL not in models:
            return (
                _make_action(
                    "red",
                    "Ollama Model",
                    f"Ollama is running, but model '{config.OLLAMA_MODEL}' is not installed locally.",
                    command=f"ollama pull {config.OLLAMA_MODEL}",
                ),
            )
        return ()

    if provider == "llamacpp":
        if config.LLAMACPP_MODEL_PATH.is_file():
            return ()
        return (
            _make_action(
                "red",
                "LlamaCPP Model",
                (
                    f"Expected GGUF model at {config.LLAMACPP_MODEL_PATH}, but the file is missing. "
                    "Use /prepare in the CLI to let μZephyr fetch the local model assets up front, "
                    "or let the first LlamaCPP use trigger the download if network access is available."
                ),
                command=".\\venv\\Scripts\\python -c \"from core.llm import ensure_models; ensure_models()\"",
                supports_prepare=True,
            ),
        )

    if provider == "openrouter" and not config.OPENROUTER_API_KEY.strip():
        return (
            _make_action(
                "red",
                "OpenRouter",
                "OPENROUTER_API_KEY is empty, so cloud inference cannot start.",
                command="set OPENROUTER_API_KEY=your-key-here",
            ),
        )

    return ()


def _collect_embedding_model_actions() -> tuple[StartupAction, ...]:
    if embedding_model_is_cached():
        return ()

    return (
        _make_action(
            "yellow",
            "Embedding Model",
            (
                f"Embedding model '{config.EMBEDDING_MODEL_NAME}' is not cached locally at {config.EMBEDDING_MODEL_DIR}. "
                "Use /prepare or the web Prepare runtime action to cache it before the first search-backed request falls back to a hub download."
            ),
            command="python download_vector_model.py",
            supports_prepare=True,
        ),
    )


def _collect_sandbox_actions() -> tuple[StartupAction, ...]:
    readiness = get_sandbox_readiness()
    detail = readiness.detail

    if readiness.requested_backend == "docker" and not readiness.ready:
        command = f"docker pull {config.SANDBOX_DOCKER_IMAGE}" if "not available locally" in detail else None
        return (
            _make_action(
                "red",
                "Docker Sandbox",
                (
                    f"Docker sandbox was requested, but it is not ready. {detail} "
                    "Use /prepare in the CLI to let μZephyr pull the image when Docker itself is available."
                ),
                command=command,
                supports_prepare="not available locally" in detail,
            ),
        )

    if readiness.requested_backend == "auto" and readiness.effective_backend == "process":
        return (
            _make_action(
                "yellow",
                "Sandbox Containment",
                (
                    f"Auto mode is using process isolation because Docker is unavailable. {detail} "
                    "If Docker is installed and only the image is missing, run /prepare in the CLI to fetch it."
                ),
                command=f"docker pull {config.SANDBOX_DOCKER_IMAGE}",
                supports_prepare="not available locally" in detail,
            ),
        )

    return ()


def _collect_external_integration_actions() -> tuple[StartupAction, ...]:
    if config.EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED:
        return ()

    disabled_features: list[str] = []
    if config.CLAUDE_MEM_WORKER_AUTOSTART:
        disabled_features.append("Claude-Mem archive autostart")
    if config.MCP_ENABLED:
        disabled_features.append("MCP server tools")

    if not disabled_features:
        disabled_features.append("subprocess-backed archive and MCP integrations")

    features = ", ".join(disabled_features)
    return (
        _make_action(
            "yellow",
            "External Integrations",
            (
                f"This runtime has external subprocess integrations disabled, so {features} will stay unavailable. "
                "This is the packaged-mode default. Re-enable by setting EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED=true "
                "in your environment or .env only if the required external tools are installed."
            ),
            command="set EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED=true",
        ),
    )


def get_startup_guidance() -> StartupGuidance:
    """Return actionable startup guidance for current local prerequisites."""
    actions = (
        _collect_external_integration_actions()
        + _collect_sandbox_actions()
        + _collect_embedding_model_actions()
        + _collect_provider_actions()
    )
    levels = {action.level for action in actions}

    if "red" in levels:
        level = "red"
        title = "Action Needed"
    elif "yellow" in levels:
        level = "yellow"
        title = "Recommended"
    else:
        level = "green"
        title = "Ready"

    return StartupGuidance(
        level=level,
        badge=_badge_for(level),
        title=title,
        actions=actions,
    )


def format_startup_guidance_markdown(guidance: StartupGuidance) -> str:
    """Render actionable startup guidance for the GUI."""
    if not guidance.actions:
        return "### 🟢 Startup Guidance: Ready\n\nNo startup fixes detected for the current provider and sandbox configuration."

    lines = [f"### {guidance.badge} Startup Guidance: {guidance.title}", ""]
    for action in guidance.actions:
        line = f"- {action.label}: {action.badge} {action.summary}"
        if action.command:
            line += f" Action: `{action.command}`"
        lines.append(line)
    return "\n".join(lines)


def format_startup_guidance_lines(guidance: StartupGuidance) -> tuple[str, ...]:
    """Render startup guidance as compact CLI-friendly lines."""
    if not guidance.actions:
        return ("Startup guidance: ready",)

    lines = [f"Startup guidance: {guidance.title.lower()}"]
    for action in guidance.actions:
        line = f"- {action.label}: {action.summary}"
        if action.command:
            line += f" Action: {action.command}"
        lines.append(line)
    return tuple(lines)


def has_prepare_call_to_action(guidance: StartupGuidance) -> bool:
    """Return whether the GUI should surface an in-app /prepare call to action."""
    return any(action.supports_prepare for action in guidance.actions)


def format_prepare_call_to_action_markdown(guidance: StartupGuidance) -> str:
    """Render a compact /prepare call to action for GUI surfaces."""
    prepare_actions = [action.label for action in guidance.actions if action.supports_prepare]
    if not prepare_actions:
        return ""

    labels = ", ".join(prepare_actions)
    return (
        "### Prepare Local Runtime\n\n"
        f"Startup guidance detected local assets that can be prepared in-app: {labels}.\n\n"
        "Open the CLI with `run.bat` or `python main.py`, then run `/prepare` and `/verify`."
    )