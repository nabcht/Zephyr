"""Shared truth-synthesis analysis helpers for runtime trust surfaces."""

from __future__ import annotations

from dataclasses import dataclass
import re

import config

_RECENT_FACTS_TO_PRESERVE = 3
_STATE_GROUPS: dict[str, tuple[str, int]] = {
    "enabled": ("switch", 1),
    "disabled": ("switch", -1),
    "active": ("activity", 1),
    "inactive": ("activity", -1),
    "available": ("availability", 1),
    "unavailable": ("availability", -1),
    "on": ("toggle", 1),
    "off": ("toggle", -1),
    "true": ("boolean", 1),
    "false": ("boolean", -1),
}


@dataclass(frozen=True, slots=True)
class TruthSynthesisHealth:
    """Health summary for the synthesized truth layer."""

    healthy: bool
    detail: str
    missing_recent_facts: list[str]
    contradictions: list[str]


def normalize_text(text: str) -> str:
    """Return a simplified lowercase representation for fact matching."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", text.lower())).strip()


def extract_timeline_facts(lines: list[str]) -> list[str]:
    """Extract the human-readable fact text from timeline entries."""
    facts: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[") and "]" in stripped:
            stripped = stripped.split("]", 1)[1].strip()
        if stripped:
            facts.append(stripped)
    return facts


def extract_state_claim(text: str) -> tuple[str, str, int] | None:
    """Parse simple newer-overrides-older state claims from text."""
    normalized = normalize_text(text)
    if not normalized:
        return None

    match = re.match(
        r"^(?P<subject>.+?)\s+(?:is|was|now|currently)\s+(?P<state>enabled|disabled|active|inactive|available|unavailable|on|off|true|false)$",
        normalized,
    )
    if not match:
        return None

    subject = match.group("subject").strip()
    state = match.group("state")
    group, polarity = _STATE_GROUPS[state]
    return subject, group, polarity


def recent_unique_facts(lines: list[str], limit: int = _RECENT_FACTS_TO_PRESERVE) -> list[str]:
    """Return the latest unique facts while collapsing repeated state claims."""
    unique_reversed: list[str] = []
    seen: set[str] = set()
    for fact in reversed(extract_timeline_facts(lines)):
        claim = extract_state_claim(fact)
        if claim is not None:
            subject, group, _ = claim
            dedupe_key = f"state::{subject}::{group}"
        else:
            dedupe_key = normalize_text(fact)

        if not dedupe_key or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        unique_reversed.append(fact)
        if len(unique_reversed) >= limit:
            break
    return list(reversed(unique_reversed))


def latest_state_claims(timeline_lines: list[str]) -> dict[tuple[str, str], int]:
    """Return the latest known polarity for each simple state claim."""
    latest_claims: dict[tuple[str, str], int] = {}
    for fact in recent_unique_facts(timeline_lines, limit=max(_RECENT_FACTS_TO_PRESERVE, len(timeline_lines))):
        claim = extract_state_claim(fact)
        if claim is None:
            continue
        subject, group, polarity = claim
        latest_claims[(subject, group)] = polarity
    return latest_claims


def detect_truth_contradictions(truth_text: str, timeline_lines: list[str]) -> list[str]:
    """Return contradicted state claims still present in truth.md."""
    contradictions: list[str] = []
    latest_claims = latest_state_claims(timeline_lines)
    if not latest_claims:
        return contradictions

    seen: set[str] = set()
    for line in truth_text.splitlines():
        stripped = line.strip().lstrip("- ").strip()
        claim = extract_state_claim(stripped)
        if claim is None:
            continue

        subject, group, polarity = claim
        latest_polarity = latest_claims.get((subject, group))
        if latest_polarity is None or latest_polarity == polarity:
            continue

        contradiction_key = f"{subject}::{group}"
        if contradiction_key in seen:
            continue
        seen.add(contradiction_key)
        contradictions.append(stripped)

    return contradictions


def remove_recent_contradictions(stabilized: str, timeline_lines: list[str]) -> str:
    """Drop older contradicted state claims from synthesized truth output."""
    latest_claims = latest_state_claims(timeline_lines)
    if not latest_claims:
        return stabilized.strip()

    filtered_lines: list[str] = []
    previous_blank = False
    for line in stabilized.splitlines():
        stripped = line.strip()
        claim = extract_state_claim(stripped)
        if claim is not None:
            subject, group, polarity = claim
            latest_polarity = latest_claims.get((subject, group))
            if latest_polarity is not None and latest_polarity != polarity:
                continue

        if not stripped:
            if previous_blank:
                continue
            previous_blank = True
            filtered_lines.append("")
            continue

        previous_blank = False
        filtered_lines.append(line)

    return "\n".join(filtered_lines).strip()


def get_truth_synthesis_health(lines: int = 40) -> TruthSynthesisHealth:
    """Inspect truth.md against recent timeline facts and return a health summary."""
    if not config.TIMELINE_FILE.exists():
        return TruthSynthesisHealth(
            healthy=False,
            detail="timeline.log is missing.",
            missing_recent_facts=[],
            contradictions=[],
        )

    all_lines = config.TIMELINE_FILE.read_text(encoding="utf-8").splitlines()
    recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
    if not recent:
        return TruthSynthesisHealth(
            healthy=False,
            detail="timeline.log is empty.",
            missing_recent_facts=[],
            contradictions=[],
        )

    truth_text = config.TRUTH_FILE.read_text(encoding="utf-8").strip() if config.TRUTH_FILE.exists() else ""
    normalized_truth = normalize_text(truth_text)
    missing_recent_facts = [
        fact for fact in recent_unique_facts(recent)
        if normalize_text(fact) not in normalized_truth
    ]
    contradictions = detect_truth_contradictions(truth_text, recent)

    issues: list[str] = []
    if not config.TRUTH_FILE.exists():
        issues.append("truth.md is missing")
    if missing_recent_facts:
        issues.append(f"missing {len(missing_recent_facts)} recent fact(s)")
    if contradictions:
        issues.append(f"detected {len(contradictions)} contradicted state claim(s)")

    if not issues:
        detail = "truth.md covers recent timeline facts with no detected simple contradictions."
    else:
        detail = "; ".join(issues) + "."

    return TruthSynthesisHealth(
        healthy=not issues,
        detail=detail,
        missing_recent_facts=missing_recent_facts,
        contradictions=contradictions,
    )


def describe_truth_synthesis_health(lines: int = 40) -> list[str]:
    """Render truth synthesis health in a compact verify-friendly format."""
    health = get_truth_synthesis_health(lines)
    status = "healthy" if health.healthy else "needs attention"
    output = [
        f"Truth synthesis health: {status}",
        f"Truth detail: {health.detail}",
    ]
    if health.missing_recent_facts:
        output.append("Truth missing recent facts: " + "; ".join(health.missing_recent_facts[:3]))
    if health.contradictions:
        output.append("Truth contradictions: " + "; ".join(health.contradictions[:3]))
    return output