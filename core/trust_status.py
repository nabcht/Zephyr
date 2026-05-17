"""Runtime trust and readiness helpers for UI surfaces."""

from __future__ import annotations

from dataclasses import dataclass

from core.truth_synthesis import get_truth_synthesis_health as _core_get_truth_synthesis_health
from skills.sandbox.scripts.sandbox import get_sandbox_readiness


@dataclass(frozen=True, slots=True)
class TrustSignal:
    """A single operational trust signal surfaced to the user."""

    label: str
    level: str
    badge: str
    summary: str


@dataclass(frozen=True, slots=True)
class RuntimeTrustStatus:
    """Combined operational trust posture for the current runtime."""

    level: str
    badge: str
    title: str
    signals: tuple[TrustSignal, ...]


def _badge_for(level: str) -> str:
    return {
        "green": "🟢",
        "yellow": "🟡",
        "red": "🔴",
    }.get(level, "⚪")


def _get_truth_synthesis_health(lines: int = 40):
    return _core_get_truth_synthesis_health(lines)


def _build_sandbox_signal() -> TrustSignal:
    readiness = get_sandbox_readiness()
    level = "green" if readiness.ready else "red"
    readiness_label = "Ready" if readiness.ready else "Not ready"
    return TrustSignal(
        label="Sandbox",
        level=level,
        badge=_badge_for(level),
        summary=(
            f"{readiness_label} via {readiness.effective_backend}. "
            f"{readiness.detail}"
        ),
    )


def _build_truth_signal(lines: int = 40) -> TrustSignal:
    try:
        health = _get_truth_synthesis_health(lines)
    except Exception as exc:
        level = "red"
        return TrustSignal(
            label="Truth Layer",
            level=level,
            badge=_badge_for(level),
            summary=f"Health probe unavailable. {exc}",
        )

    level = "green" if getattr(health, "healthy", False) else "yellow"
    state = "Healthy" if level == "green" else "Needs attention"
    return TrustSignal(
        label="Truth Layer",
        level=level,
        badge=_badge_for(level),
        summary=f"{state}. {getattr(health, 'detail', 'No detail available.')}",
    )


def get_runtime_trust_status(lines: int = 40) -> RuntimeTrustStatus:
    """Return the combined operational trust posture for the current runtime."""
    signals = (
        _build_sandbox_signal(),
        _build_truth_signal(lines),
    )
    levels = {signal.level for signal in signals}

    if "red" in levels:
        level = "red"
        title = "Blocked"
    elif "yellow" in levels:
        level = "yellow"
        title = "Attention"
    else:
        level = "green"
        title = "Ready"

    return RuntimeTrustStatus(
        level=level,
        badge=_badge_for(level),
        title=title,
        signals=signals,
    )


def format_runtime_trust_status_markdown(status: RuntimeTrustStatus) -> str:
    """Render a compact Markdown trust card for the GUI header."""
    lines = [f"### {status.badge} Runtime Trust: {status.title}", ""]
    for signal in status.signals:
        lines.append(f"- {signal.label}: {signal.badge} {signal.summary}")
    return "\n".join(lines)