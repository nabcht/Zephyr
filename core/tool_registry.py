"""Tool registration, storage, and schema generation helpers."""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
import re
from typing import Any, Callable, get_args, get_origin, get_type_hints

from core.tool_executor import tool_is_allowed

log = logging.getLogger("zephyr.tool_registry")

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")
_PROVIDER_TOOL_DESCRIPTION_MAXIMUM_LENGTH = 140

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
        *,
        compact_for_provider: bool = False,
    ) -> list[dict[str, Any]]:
        """Return OpenAI-compatible function-calling schemas for registered tools."""
        schemas: list[dict[str, Any]] = []
        for tool_def in self._tools.values():
            if not tool_is_allowed(tool_def, allowed_tags):
                continue

            tool_description = tool_def.description
            tool_parameters = tool_def.parameters
            if compact_for_provider:
                tool_description = self._compact_tool_description(tool_description)
                tool_parameters = self._compact_parameter_schema(tool_parameters)

            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool_def.name,
                        "description": tool_description,
                        "parameters": tool_parameters,
                    },
                }
            )
        return schemas

    @staticmethod
    def _compact_tool_description(description: str) -> str:
        collapsed_description = " ".join(description.split())
        if not collapsed_description:
            return "No description."

        first_sentence = _SENTENCE_BOUNDARY_RE.split(collapsed_description, maxsplit=1)[0].strip()
        if first_sentence:
            candidate_description = first_sentence
        else:
            candidate_description = collapsed_description

        if len(candidate_description) <= _PROVIDER_TOOL_DESCRIPTION_MAXIMUM_LENGTH:
            return candidate_description

        trimmed_description = candidate_description[: _PROVIDER_TOOL_DESCRIPTION_MAXIMUM_LENGTH - 1].rstrip()
        return f"{trimmed_description}…"

    @classmethod
    def _compact_parameter_schema(cls, schema: dict[str, Any]) -> dict[str, Any]:
        compact_schema: dict[str, Any] = {}
        for key, value in schema.items():
            if key in {"description", "title", "examples", "default"}:
                continue

            if key == "properties" and isinstance(value, dict):
                compact_schema[key] = {
                    property_name: cls._compact_parameter_schema(property_schema)
                    if isinstance(property_schema, dict)
                    else property_schema
                    for property_name, property_schema in value.items()
                }
                continue

            if key == "items" and isinstance(value, dict):
                compact_schema[key] = cls._compact_parameter_schema(value)
                continue

            if isinstance(value, dict):
                compact_schema[key] = cls._compact_parameter_schema(value)
                continue

            if isinstance(value, list):
                compact_schema[key] = [
                    cls._compact_parameter_schema(item) if isinstance(item, dict) else item
                    for item in value
                ]
                continue

            compact_schema[key] = value

        return compact_schema

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