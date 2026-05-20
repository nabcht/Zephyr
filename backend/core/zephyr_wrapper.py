"""Thin wrapper around the existing uZephyr core configuration and status APIs."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import re
from typing import Any

import config
from core.app_runtime import AppRuntime
from core.runtime_status import get_privacy_status
from core.startup_guidance import get_startup_guidance
from core.trust_status import get_runtime_trust_status


_RICH_TAG_RE = re.compile(r"\[/?[^\]]+\]")


class ZephyrCoreWrapper:
    """Expose a narrow, API-safe view of the current core runtime."""

    def get_system_snapshot(self, runtime: AppRuntime | None = None) -> dict[str, Any]:
        guidance = get_startup_guidance()
        trust_status = get_runtime_trust_status()
        tool_names = runtime.tool_engine.list_tool_names() if runtime and runtime.tool_engine is not None else None
        privacy_status = get_privacy_status(
            provider=config.LLM_PROVIDER,
            tool_names=tool_names,
            skills_dir=config.SKILLS_DIR,
        )
        tool_counts = self._tool_counts(runtime)
        return {
            "name": "uZephyr Hybrid API",
            "version": "0.1.0",
            "provider": config.LLM_PROVIDER,
            "model": self._model_name(),
            "interfaces": ["cli", "api"],
            "runtime_initialized": runtime is not None and runtime.llm is not None and runtime.tool_engine is not None,
            "inference_status": self._plain_status(runtime.llm.describe_inference_status()) if runtime is not None and runtime.llm is not None else "Pending (runtime not initialized)",
            "inference_metrics": runtime.llm.describe_inference_metrics() if runtime is not None and runtime.llm is not None else {
                "last_warmup_milliseconds": None,
                "last_warmup_outcome": "not_run",
                "first_response_token_milliseconds": None,
                "first_response_token_outcome": "not_run",
                "last_completion_milliseconds": None,
                "last_completion_outcome": "not_run",
            },
            "provider_payload_metrics": runtime.llm.describe_provider_payload_metrics() if runtime is not None and runtime.llm is not None else {
                "provider_message_count": None,
                "history_message_count": None,
                "tool_schema_count": None,
                "serialized_payload_characters": None,
                "used_lightweight_payload_strategy": None,
            },
            "search_status": self._plain_search_status(runtime.search_status) if runtime is not None else "Starting",
            "external_integrations_enabled": config.EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED,
            "safety_confirmation_required": config.REQUIRE_CONFIRMATION,
            "design_system_path": "frontend/design.md",
            "prepare_actions": [action.label for action in guidance.actions if action.supports_prepare],
            "tool_counts": tool_counts,
            "privacy_status": {
                "level": privacy_status.level,
                "badge": privacy_status.badge,
                "title": privacy_status.title,
                "summary": privacy_status.summary,
                "inference_backend": privacy_status.inference_backend,
                "remote_capabilities": list(privacy_status.remote_capabilities),
            },
            "trust_status": {
                "level": trust_status.level,
                "badge": trust_status.badge,
                "title": trust_status.title,
                "signals": [asdict(signal) for signal in trust_status.signals],
            },
            "startup_guidance": {
                "level": guidance.level,
                "badge": guidance.badge,
                "title": guidance.title,
                "actions": [asdict(action) for action in guidance.actions],
            },
        }

    @staticmethod
    def _plain_status(search_status: str) -> str:
        cleaned = _RICH_TAG_RE.sub("", search_status or "")
        return " ".join(cleaned.split()) or "Unknown"

    @staticmethod
    def _plain_search_status(search_status: str) -> str:
        return ZephyrCoreWrapper._plain_status(search_status)

    @staticmethod
    def _tool_counts(runtime: AppRuntime | None) -> dict[str, int]:
        if runtime is None or runtime.tool_engine is None:
            return {
                "total": 0,
                "skill_tools": 0,
                "builtins": 0,
                "mcp_tools": 0,
                "manual_tools": 0,
            }

        counts = Counter(tool.source for tool in runtime.tool_engine.list_tools())
        return {
            "total": sum(counts.values()),
            "skill_tools": counts.get("local", 0),
            "builtins": counts.get("builtin", 0),
            "mcp_tools": counts.get("mcp", 0),
            "manual_tools": counts.get("manual", 0),
        }

    def _model_name(self) -> str:
        if config.LLM_PROVIDER == "ollama":
            return config.OLLAMA_MODEL
        if config.LLM_PROVIDER == "openrouter":
            return config.OPENROUTER_MODEL
        if config.LLM_PROVIDER == "llamacpp":
            return config.LLAMACPP_MODEL_PATH.name
        return "unknown"