"""Focused regression check for command-center inventory stability."""

from __future__ import annotations

import asyncio

import httpx

from backend.main import create_app
from backend.runtime_gateway import shutdown_runtime


EXPECTED_PRESENT = {"merge_python_files", "search_web"}
EXPECTED_ABSENT = {"dataclass"}


async def request_json(client: httpx.AsyncClient, method: str, path: str) -> dict | list:
    response = await client.request(method, path)
    response.raise_for_status()
    return response.json()


def tool_snapshot(overview: dict) -> list[tuple[str, str]]:
    return sorted((tool["source"], tool["name"]) for tool in overview.get("tools", []))


def validate_expected_tools(snapshot: list[tuple[str, str]]) -> None:
    names = {name for _, name in snapshot}
    missing = sorted(EXPECTED_PRESENT - names)
    unexpected = sorted(EXPECTED_ABSENT & names)

    if missing or unexpected:
        issues: list[str] = []
        if missing:
            issues.append(f"missing expected tools: {', '.join(missing)}")
        if unexpected:
            issues.append(f"unexpected leaked helpers: {', '.join(unexpected)}")
        raise AssertionError("; ".join(issues))


def assert_same_inventory(label: str, expected: list[tuple[str, str]], actual: list[tuple[str, str]]) -> None:
    if expected == actual:
        return

    expected_set = set(expected)
    actual_set = set(actual)
    missing = sorted(f"{source}:{name}" for source, name in expected_set - actual_set)
    added = sorted(f"{source}:{name}" for source, name in actual_set - expected_set)
    details: list[str] = [f"command-center inventory drift after {label}"]
    if missing:
        details.append(f"missing: {', '.join(missing)}")
    if added:
        details.append(f"added: {', '.join(added)}")
    raise AssertionError("; ".join(details))


async def main() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            timeout=180.0,
        ) as client:
            await request_json(client, "GET", "/api/command-center/overview")

            await request_json(client, "POST", "/api/runtime/reload")
            baseline_overview = await request_json(client, "GET", "/api/command-center/overview")
            baseline_snapshot = tool_snapshot(baseline_overview)
            validate_expected_tools(baseline_snapshot)

            await request_json(client, "POST", "/api/runtime/reload")
            reload_overview = await request_json(client, "GET", "/api/command-center/overview")
            reload_snapshot = tool_snapshot(reload_overview)
            validate_expected_tools(reload_snapshot)
            assert_same_inventory("runtime reload", baseline_snapshot, reload_snapshot)

            session_payload = await request_json(client, "POST", "/api/sessions")
            session_id = session_payload["session_id"]
            history_payload = await request_json(client, "GET", f"/api/sessions/{session_id}/messages")
            if history_payload.get("messages"):
                raise AssertionError("new session should start with empty persisted history")

            session_overview = await request_json(client, "GET", "/api/command-center/overview")
            session_snapshot = tool_snapshot(session_overview)
            validate_expected_tools(session_snapshot)
            assert_same_inventory("new session transition", baseline_snapshot, session_snapshot)

            print("Command-center inventory regression passed.")
            print(f"Tool count: {len(baseline_snapshot)}")
            print("Verified present: merge_python_files, search_web")
            print("Verified absent: dataclass")
            print(f"Session id checked: {session_id}")
    finally:
        await shutdown_runtime()


if __name__ == "__main__":
    asyncio.run(main())