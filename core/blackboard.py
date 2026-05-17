"""Blackboard — shared structured state for multi-agent missions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


_HARDENED_SANDBOX_BACKENDS = {"DOCKER", "WASM", "VENV"}


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True)
    except TypeError:
        return str(value)


def review_feedback_passes(feedback: str) -> bool:
    """Return True only for a PASS review with the required checklist evidence."""
    cleaned = feedback.strip().lstrip("*#-`> ")
    if not cleaned.upper().startswith("PASS"):
        return False

    normalized = re.sub(r"\s+", " ", cleaned.upper().replace("-", " "))
    required_checks = (
        r"DOCSTRINGS?\s*:\s*PASS",
        r"ERROR\s+HANDLING\s*:\s*PASS",
        r"SANDBOX\s*:\s*PASS",
    )
    return all(re.search(pattern, normalized) for pattern in required_checks)


def sandbox_feedback_backend(feedback: str) -> str:
    """Return the backend name reported by sandbox feedback, if present."""
    for line in feedback.splitlines():
        normalized = line.strip()
        if not normalized.upper().startswith("BACKEND:"):
            continue
        backend_value = normalized.split(":", 1)[1].strip()
        if not backend_value:
            return ""
        return backend_value.split()[0].strip("(),").upper()
    return ""


def sandbox_feedback_reported_success(feedback: str) -> bool:
    """Return True when sandbox execution explicitly reported a successful run."""
    cleaned = feedback.strip().upper()
    if not cleaned:
        return False
    first_line = cleaned.splitlines()[0]
    return "TEST PASSED" in first_line


def sandbox_feedback_passes(feedback: str) -> bool:
    """Return True only for successful runs executed in a hardened sandbox backend."""
    if not sandbox_feedback_reported_success(feedback):
        return False
    return sandbox_feedback_backend(feedback) in _HARDENED_SANDBOX_BACKENDS


@dataclass(slots=True)
class Blackboard:
    """Mission-scoped source of truth shared by all agency roles."""

    mission_id: str
    goal: str
    findings: dict[str, Any] = field(default_factory=dict)
    requests: list[dict[str, str]] = field(default_factory=list)
    milestones: list[str] = field(default_factory=list)
    current_code: str = ""
    review_feedback: str = ""
    current_agent: str = "Supervisor"
    code_version: int = 0
    reviewed_code_version: int = 0
    sandbox_feedback: str = ""
    sandboxed_code_version: int = 0
    agent_turn_counts: dict[str, int] = field(default_factory=dict)

    def add_finding(self, key: str, value: Any) -> None:
        self.findings[key] = value

    def update_finding(self, key: str, value: Any) -> None:
        self.add_finding(key, value)

    def add_request(self, sender: str, recipient: str, content: str) -> None:
        self.requests.append(
            {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "from": sender,
                "to": recipient,
                "content": content,
            }
        )

    def add_milestone(self, note: str) -> None:
        self.milestones.append(note)

    def record_turn(self, agent: str) -> None:
        self.agent_turn_counts[agent] = self.agent_turn_counts.get(agent, 0) + 1

    def turn_count(self, agent: str) -> int:
        return self.agent_turn_counts.get(agent, 0)

    def set_code(self, code: str) -> None:
        self.current_code = code.strip()
        if self.current_code:
            self.code_version += 1
            self.sandbox_feedback = ""
            self.sandboxed_code_version = 0

    def set_sandbox_feedback(self, feedback: str) -> None:
        self.sandbox_feedback = feedback.strip()
        if self.current_code:
            self.sandboxed_code_version = self.code_version

    def set_review_feedback(self, feedback: str) -> None:
        self.review_feedback = feedback.strip()
        if self.current_code:
            self.reviewed_code_version = self.code_version

    def review_passed(self) -> bool:
        return review_feedback_passes(self.review_feedback) and self.latest_code_has_passing_sandbox()

    def review_rejected(self) -> bool:
        return bool(self.review_feedback) and not self.review_passed()

    def latest_code_needs_review(self) -> bool:
        return bool(self.current_code) and self.code_version > self.reviewed_code_version

    def latest_code_has_passing_sandbox(self) -> bool:
        return (
            bool(self.current_code)
            and self.code_version == self.sandboxed_code_version
            and sandbox_feedback_passes(self.sandbox_feedback)
        )

    def render_for_llm(self) -> str:
        lines = [
            f"## MISSION BOARD [{self.mission_id}]",
            f"### MISSION GOAL\n{self.goal}",
            f"### CURRENT AGENT\n{self.current_agent}",
            "### FINDINGS & DATA:",
        ]

        if not self.findings:
            lines.append("- No findings yet.")
        else:
            for key, value in self.findings.items():
                rendered = _stringify(value)
                if "\n" in rendered:
                    lines.append(f"- **{key}**:\n{rendered}")
                else:
                    lines.append(f"- **{key}**: {rendered}")

        lines.append("### INTER-AGENT REQUESTS:")
        if not self.requests:
            lines.append("- No pending requests.")
        else:
            for request in self.requests:
                lines.append(
                    f"- [{request['from']} -> {request['to']} @ {request['ts']}]: {request['content']}"
                )

        lines.append("### MILESTONES:")
        if not self.milestones:
            lines.append("- Mission started.")
        else:
            lines.extend(f"- {milestone}" for milestone in self.milestones)

        lines.append("### LATEST CODE PROPOSAL:")
        if self.current_code:
            lines.append(f"```python\n{self.current_code}\n```")
        else:
            lines.append("- No code posted yet.")

        lines.append("### SANDBOX STATUS:")
        if not self.current_code:
            lines.append("- No code to verify yet.")
        elif self.code_version != self.sandboxed_code_version:
            lines.append("- Latest code revision has not been sandbox-verified yet.")
        elif self.latest_code_has_passing_sandbox():
            lines.append("- Latest code revision passed sandbox verification.")
        elif sandbox_feedback_reported_success(self.sandbox_feedback):
            backend = sandbox_feedback_backend(self.sandbox_feedback) or "unknown"
            lines.append(
                f"- Latest code revision only passed in an unhardened backend ({backend}) and does not satisfy the review gate."
            )
        else:
            lines.append("- Latest code revision failed sandbox verification.")
        lines.append(self.sandbox_feedback or "- No sandbox feedback yet.")

        lines.append("### REVIEW STATUS:")
        if self.latest_code_needs_review():
            lines.append("- Latest code revision is awaiting reviewer verification.")
        elif self.review_passed():
            lines.append("- Latest reviewed code revision has PASS status.")
        elif self.review_rejected():
            lines.append("- Latest reviewed code revision was REJECTED.")
        else:
            lines.append("- No review has been completed yet.")

        lines.append("### REVIEWER FEEDBACK:")
        lines.append(self.review_feedback or "- No review feedback yet.")

        return "\n".join(lines)

    def render(self) -> str:
        return self.render_for_llm()