"""Runtime privacy and backend status helpers for UI surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_LOCAL_PROVIDERS = {"ollama", "llamacpp"}
_REMOTE_TOOL_NAMES = {
    "search_web": "Web Search",
    "browser_search": "Browser Search",
}
_REMOTE_SKILL_DIR_NAMES = {
    "search-web": "Web Search",
    "browser-search": "Browser Search",
}


@dataclass(frozen=True, slots=True)
class PrivacyStatus:
    """Privacy posture for the current runtime configuration."""

    level: str
    badge: str
    title: str
    summary: str
    inference_backend: str
    remote_capabilities: tuple[str, ...]


def _backend_label(provider: str) -> str:
    normalized = provider.strip().lower()
    labels = {
        "ollama": "Ollama",
        "llamacpp": "LlamaCPP",
        "openrouter": "OpenRouter",
    }
    return labels.get(normalized, provider or "Unknown")


def detect_remote_capabilities(
    *,
    tool_names: Iterable[str] | None = None,
    skills_dir: Path | None = None,
) -> tuple[str, ...]:
    """Return known network-capable tool labels detected from runtime or skills on disk."""
    capabilities: list[str] = []
    seen: set[str] = set()

    for tool_name in tool_names or []:
        label = _REMOTE_TOOL_NAMES.get(tool_name)
        if label and label not in seen:
            seen.add(label)
            capabilities.append(label)

    if skills_dir is not None and skills_dir.exists():
        for skill_dir_name, label in _REMOTE_SKILL_DIR_NAMES.items():
            if label in seen:
                continue
            if (skills_dir / skill_dir_name).exists():
                seen.add(label)
                capabilities.append(label)

    return tuple(capabilities)


def get_privacy_status(
    *,
    provider: str,
    tool_names: Iterable[str] | None = None,
    skills_dir: Path | None = None,
) -> PrivacyStatus:
    """Classify the current privacy posture as green, yellow, or red."""
    normalized_provider = provider.strip().lower()
    backend_label = _backend_label(provider)
    remote_capabilities = detect_remote_capabilities(tool_names=tool_names, skills_dir=skills_dir)

    if normalized_provider == "openrouter":
        return PrivacyStatus(
            level="red",
            badge="🔴",
            title="Cloud",
            summary="Prompts are sent to OpenRouter or another cloud inference backend.",
            inference_backend=backend_label,
            remote_capabilities=remote_capabilities,
        )

    if normalized_provider in _LOCAL_PROVIDERS and remote_capabilities:
        return PrivacyStatus(
            level="yellow",
            badge="🟡",
            title="Hybrid",
            summary="Inference stays local, but network-capable tools are available and may send selected queries off-machine.",
            inference_backend=backend_label,
            remote_capabilities=remote_capabilities,
        )

    if normalized_provider in _LOCAL_PROVIDERS:
        return PrivacyStatus(
            level="green",
            badge="🟢",
            title="Air-gapped",
            summary="Inference is local and no known network-capable search tools were detected.",
            inference_backend=backend_label,
            remote_capabilities=remote_capabilities,
        )

    return PrivacyStatus(
        level="yellow",
        badge="🟡",
        title="Unclassified",
        summary="The inference backend is not classified yet; review provider and tool configuration before trusting privacy assumptions.",
        inference_backend=backend_label,
        remote_capabilities=remote_capabilities,
    )


def format_privacy_status_markdown(status: PrivacyStatus) -> str:
    """Render a compact Markdown card for the GUI header."""
    remote_capabilities = ", ".join(status.remote_capabilities) if status.remote_capabilities else "none detected"
    return (
        f"### {status.badge} Privacy Mode: {status.title}\n"
        f"Inference backend: {status.inference_backend}\n\n"
        f"Remote-capable tools: {remote_capabilities}\n\n"
        f"{status.summary}"
    )