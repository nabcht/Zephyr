"""Tool registration, storage, and schema generation helpers."""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, get_args, get_origin, get_type_hints

from core.tool_executor import tool_is_allowed

log = logging.getLogger("uzephyr.tool_registry")

_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


@dataclass(slots=True)
class ToolDef:
    """A registered tool and its metadata."""

    name: str
    description: str
    fn: Callable[..., Any]
    parameters: dict[str, Any] = field(default_factory=dict)
    sensitive: bool = False
    tags: list[str] = field(default_factory=lambda: ["general"])
    source: str = "manual"


class ToolRegistry:
    """Own the registered tool catalog and derived schemas."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}

    def register(
        self,
        fn: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
        sensitive: bool = False,
        tags: list[str] | None = None,
        parameters: dict[str, Any] | None = None,
        source: str = "manual",
    ) -> None:
        """Register a callable as a tool and derive its JSON schema."""
        tool_name = name or fn.__name__
        tool_desc = description or inspect.getdoc(fn) or "No description."
        params = parameters if parameters is not None else self._params_from_signature(fn)

        self._tools[tool_name] = ToolDef(
            name=tool_name,
            description=tool_desc,
            fn=fn,
            parameters=params,
            sensitive=sensitive,
            tags=list(tags) if tags is not None else ["general"],
            source=source,
        )
        log.debug(
            "Registered tool: %s (source=%s, sensitive=%s, tags=%s)",
            tool_name,
            source,
            sensitive,
            self._tools[tool_name].tags,
        )

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    def list_tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def list_tools(self) -> list[ToolDef]:
        """Return registered tools with metadata for UI rendering."""
        return list(self._tools.values())

    def remove_by_source(self, sources: set[str]) -> None:
        stale_names = [name for name, tool_def in self._tools.items() if tool_def.source in sources]
        for name in stale_names:
            self._tools.pop(name, None)

    def get_openai_tool_schemas(
        self,
        allowed_tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return OpenAI-compatible function-calling schemas for registered tools."""
        schemas: list[dict[str, Any]] = []
        for tool_def in self._tools.values():
            if not tool_is_allowed(tool_def, allowed_tags):
                continue

            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool_def.name,
                        "description": tool_def.description,
                        "parameters": tool_def.parameters,
                    },
                }
            )
        return schemas

    @staticmethod
    def _params_from_signature(fn: Callable[..., Any]) -> dict[str, Any]:
        """Derive a JSON-Schema-style parameters object from a callable signature."""
        sig = inspect.signature(fn)
        try:
            resolved_hints = get_type_hints(fn)
        except Exception:
            resolved_hints = {}
        properties: dict[str, Any] = {}
        required: list[str] = []

        for name, param in sig.parameters.items():
            if name in {"self", "cls"}:
                continue

            annotation = resolved_hints.get(name, param.annotation)
            if annotation is inspect.Parameter.empty:
                json_type = "string"
            else:
                origin = get_origin(annotation)
                annotation_args = get_args(annotation)
                if annotation_args:
                    non_none = [arg for arg in annotation_args if arg is not type(None)]
                    candidate = non_none[0] if non_none else str
                    json_type = _TYPE_MAP.get(get_origin(candidate) or candidate, "string")
                else:
                    json_type = _TYPE_MAP.get(annotation if origin is None else origin, "string")

            properties[name] = {
                "type": json_type,
                "description": name.replace("_", " ").capitalize(),
            }

            if param.default is inspect.Parameter.empty:
                required.append(name)

        schema: dict[str, Any] = {
            "type": "object",
            "properties": properties,
        }
        if required:
            schema["required"] = required
        return schema