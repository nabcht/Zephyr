"""Archive researcher skill for Claude-Mem history lookups."""

from __future__ import annotations

import json
from typing import Any

_archive_bridge: Any = None


def _set_archive_bridge(archive_bridge: Any) -> None:
    global _archive_bridge
    _archive_bridge = archive_bridge


def _json_list(raw: Any) -> list[str]:
    if raw in (None, ""):
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return [raw]
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return []


async def deep_search_history(query: str, limit: int = 5) -> str:
    """Deep-search historical Claude-Mem observations for debugging context."""
    if _archive_bridge is None:
        return "Archive bridge is not configured."

    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 5

    hits = await _archive_bridge.search(query, limit=max(limit, 5))
    if not hits:
        return f"No archive history found for '{query}'."

    selected_hits = hits[:limit]
    ids = [hit.get("id") for hit in selected_hits if isinstance(hit.get("id"), int)]

    lines = [f"Archive history for: {query}", "", "Matched observations:"]
    for hit in selected_hits:
        lines.append(f"- #{hit.get('id', '?')}: {hit.get('title', 'Untitled')}")

    if not ids:
        return "\n".join(lines)

    observations = await _archive_bridge.get_observations(ids, limit=limit)
    if not observations:
        return "\n".join(lines)

    lines.extend(["", "Detailed observations:"])
    for observation in observations:
        obs_id = observation.get("id", "?")
        title = observation.get("title") or "Untitled"
        lines.append(f"- #{obs_id}: {title}")

        subtitle = observation.get("subtitle")
        if subtitle:
            lines.append(f"  Subtitle: {subtitle}")

        narrative = observation.get("narrative") or observation.get("text") or ""
        if narrative:
            lines.append(f"  Narrative: {' '.join(str(narrative).split())}")

        facts = _json_list(observation.get("facts"))
        if facts:
            lines.append(f"  Facts: {'; '.join(facts[:5])}")

        concepts = _json_list(observation.get("concepts"))
        if concepts:
            lines.append(f"  Concepts: {', '.join(concepts[:8])}")

        files = _json_list(observation.get("files_modified")) or _json_list(observation.get("files_read"))
        if files:
            lines.append(f"  Files: {', '.join(files[:8])}")

        created_at = observation.get("created_at")
        if created_at:
            lines.append(f"  Created: {created_at}")

        lines.append("")

    return "\n".join(lines).rstrip()