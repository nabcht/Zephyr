"""Repeatable regression checks for the primary hybrid workflow and fallback surfaces."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from backend.main import create_app
from backend.runtime_gateway import ensure_runtime_ready, shutdown_runtime
from core.embedding_model import EmbeddingModelPreparation
from core.llm import InferenceRuntimePreparation, LlamaCppPreparation
from skills.sandbox.scripts.sandbox import SandboxPreparation
from verify_command_center_inventory import main as verify_command_center_inventory


ROOT = Path(__file__).resolve().parent


def require_text(path: Path, snippets: list[str]) -> None:
    content = path.read_text(encoding="utf-8")
    missing = [snippet for snippet in snippets if snippet not in content]
    if missing:
        raise AssertionError(f"{path.name} is missing expected text: {', '.join(missing)}")


def require_requirement(path: Path, package_name: str) -> None:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    declared = any(
        line
        and not line.startswith("#")
        and line.split("[", 1)[0].split("=", 1)[0].split("<", 1)[0].split(">", 1)[0].strip() == package_name
        for line in lines
    )
    if not declared:
        raise AssertionError(f"{path.name} must declare the '{package_name}' dependency.")


def verify_launcher_files() -> None:
    require_text(ROOT / "run.bat", ['call "%~dp0run-hybrid.bat" %*'])
    require_text(ROOT / "run-hybrid.bat", ["npm run dev:hybrid", "Starting the primary React interface."])
    require_text(ROOT / "run-cli.bat", ["python main.py %*", "CLI fallback/operator surface"])
    require_requirement(ROOT / "requirements.txt", "watchdog")
    require_text(
        ROOT / "backend" / "dev_server.py",
        ["run_process(*WATCH_PATHS", 'ROOT / "config.py"', 'relative_path.startswith("skills/")'],
    )

    package_json = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    scripts = package_json.get("scripts", {})
    required_scripts = {"dev:hybrid", "dev:hybrid:stable", "build:frontend", "verify:command-center", "verify:hybrid"}
    missing_scripts = sorted(required_scripts - set(scripts))
    if missing_scripts:
        raise AssertionError(f"package.json is missing expected scripts: {', '.join(missing_scripts)}")

    if "python -m backend.dev_server" not in scripts["dev:hybrid"]:
        raise AssertionError("dev:hybrid must use the dedicated watcher-driven backend launcher.")
    if "--reload" in scripts["dev:hybrid:stable"]:
        raise AssertionError("dev:hybrid:stable must omit --reload for the stable no-reload flow.")

    print("Launcher regression passed.")


async def kill_process_tree(pid: int) -> None:
    process = await asyncio.create_subprocess_exec(
        "taskkill",
        "/T",
        "/F",
        "/PID",
        str(pid),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await process.wait()


async def wait_for_http_ready(url: str, timeout: float) -> None:
    deadline = asyncio.get_running_loop().time() + timeout

    async with httpx.AsyncClient(timeout=httpx.Timeout(2.0, connect=0.5)) as client:
        while True:
            try:
                response = await client.get(url)
                if response.is_success:
                    return
            except Exception:
                pass

            if asyncio.get_running_loop().time() >= deadline:
                raise AssertionError(f"Timed out waiting for {url}")

            await asyncio.sleep(0.25)


async def smoke_long_running_command(
    label: str,
    command: str,
    *,
    readiness_urls: list[str],
    required_output_snippets: list[str] | None = None,
    timeout: float = 45.0,
) -> None:
    process = await asyncio.create_subprocess_shell(
        command,
        cwd=str(ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    assert process.stdout is not None

    lines: list[str] = []
    found_output: set[str] = set()
    required_output_snippets = required_output_snippets or []

    async def read_output() -> None:
        while True:
            line = await process.stdout.readline()
            if not line:
                break

            text = line.decode("utf-8", errors="replace").rstrip()
            lines.append(text)
            for snippet in required_output_snippets:
                if snippet in text:
                    found_output.add(snippet)

    output_task = asyncio.create_task(read_output())

    try:
        for url in readiness_urls:
            await wait_for_http_ready(url, timeout)
        if required_output_snippets and len(found_output) != len(required_output_snippets):
            missing = ", ".join(sorted(set(required_output_snippets) - found_output))
            excerpt = "\n".join(lines[-20:])
            raise AssertionError(f"{label} smoke failed; missing launch markers: {missing}\n{excerpt}")
    finally:
        await kill_process_tree(process.pid)
        await asyncio.sleep(1.0)
        await output_task

    print(f"{label} smoke passed.")


async def verify_mission_stream() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=90.0) as client:
            async with client.stream(
                "POST",
                "/api/missions/stream",
                json={"session_id": "hybrid-regression", "message": "summarize the repo state"},
            ) as response:
                response.raise_for_status()
                event_name = ""
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("event:"):
                        event_name = line.split(":", 1)[1].strip()
                        continue
                    if line.startswith("data:") and event_name == "snapshot":
                        payload = json.loads(line.split(":", 1)[1].strip())
                        content = str(payload.get("content", "")).strip()
                        if content:
                            required_sections = ("Mission in progress", "Sandbox:", "Review:", "Recent milestones:")
                            missing_sections = [section for section in required_sections if section not in content]
                            if missing_sections:
                                raise AssertionError(
                                    "Mission stream regression failed: first snapshot was missing expected sections: "
                                    + ", ".join(missing_sections)
                                )
                            print("Mission stream regression passed.")
                            return
    finally:
        await shutdown_runtime()

    raise AssertionError("Mission stream regression failed: no snapshot event was observed.")


async def verify_chat_stream_initial_snapshot() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=180.0) as client:
            async with client.stream(
                "POST",
                "/api/chat/stream",
                json={
                    "session_id": "hybrid-chat-regression",
                    "message": "Reply with exactly OK. Do not call tools.",
                },
            ) as response:
                response.raise_for_status()
                event_name = ""
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("event:"):
                        event_name = line.split(":", 1)[1].strip()
                        continue
                    if not line.startswith("data:"):
                        continue

                    payload = json.loads(line.split(":", 1)[1].strip())
                    if event_name != "snapshot":
                        continue

                    content = str(payload.get("content", "")).strip()
                    if not content:
                        raise AssertionError("Chat stream regression failed: first snapshot content was empty.")
                    if "Initializing shared runtime" not in content:
                        raise AssertionError(
                            "Chat stream regression failed: cold stream did not emit the expected runtime initialization snapshot."
                        )

                    print("Chat stream first-snapshot regression passed.")
                    return
    finally:
        await shutdown_runtime()

    raise AssertionError("Chat stream regression failed: no snapshot event was observed.")


async def verify_inference_status_degraded_on_failure() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    class FailingClient:
        async def post(self, *args: object, **kwargs: object) -> object:
            raise httpx.RequestError("simulated provider outage")

    try:
        with patch("core.llm.LLMRouter._http_client", return_value=FailingClient()):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=180.0) as client:
                response = await client.post(
                    "/api/chat/turn",
                    json={
                        "session_id": "hybrid-degraded-inference",
                        "message": "Reply with exactly OK. Do not call tools.",
                    },
                )
                response.raise_for_status()

                status_response = await client.get("/api/system/status")
                status_response.raise_for_status()
                inference_status = str(status_response.json().get("inference_status", "")).strip()
                if not inference_status:
                    raise AssertionError("Inference degradation regression failed: status snapshot omitted inference_status.")
                if "Degraded" not in inference_status:
                    raise AssertionError(
                        "Inference degradation regression failed: failed live provider requests should persist as degraded readiness."
                    )

                print("Inference degradation regression passed.")
    finally:
        await shutdown_runtime()


async def verify_inference_status_warming_during_background_warmup() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    warmup_started = asyncio.Event()
    release_warmup = asyncio.Event()

    async def blocked_prepare_inference_runtime(self: object) -> InferenceRuntimePreparation:
        warmup_started.set()
        await release_warmup.wait()
        getattr(self, "_mark_inference_ready")("provider runtime warmed")
        return InferenceRuntimePreparation(
            attempted=True,
            success=True,
            detail="Active provider runtime warmed for regression verification.",
        )

    try:
        with patch("core.llm.LLMRouter.prepare_inference_runtime", new=blocked_prepare_inference_runtime):
            runtime = await ensure_runtime_ready()
            try:
                await asyncio.wait_for(warmup_started.wait(), timeout=5.0)

                async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=180.0) as client:
                    warming_response = await client.get("/api/system/status")
                    warming_response.raise_for_status()
                    warming_status = str(warming_response.json().get("inference_status", "")).strip()
                    if "Warming" not in warming_status:
                        raise AssertionError(
                            "Inference warm-up regression failed: status snapshot should expose a Warming state during background provider warm-up."
                        )

                    release_warmup.set()
                    preparation = await runtime.prepare_inference_runtime()
                    if not preparation.success:
                        raise AssertionError(
                            "Inference warm-up regression failed: shared prepare path should complete successfully after releasing the background warm-up."
                        )

                    ready_response = await client.get("/api/system/status")
                    ready_response.raise_for_status()
                    ready_status = str(ready_response.json().get("inference_status", "")).strip()
                    if "Ready" not in ready_status:
                        raise AssertionError(
                            "Inference warm-up regression failed: status snapshot should expose a Ready state after the shared warm-up task completes."
                        )
            finally:
                release_warmup.set()

        print("Inference warm-up status regression passed.")
    finally:
        await shutdown_runtime()


async def verify_runtime_stream(
    client: httpx.AsyncClient,
    path: str,
    *,
    expected_action: str,
) -> dict:
    snapshot_seen = False
    event_name = ""

    async with client.stream("POST", path) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line:
                continue
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
                continue
            if not line.startswith("data:"):
                continue

            payload = json.loads(line.split(":", 1)[1].strip())
            if event_name == "snapshot":
                if payload.get("action") != expected_action:
                    raise AssertionError(f"{path} emitted unexpected action {payload.get('action')!r}")
                if not str(payload.get("message", "")).strip():
                    raise AssertionError(f"{path} emitted an empty snapshot message")
                snapshot_seen = True
                continue

            if event_name == "done":
                if not snapshot_seen:
                    raise AssertionError(f"{path} completed before emitting a snapshot")
                if payload.get("action") != expected_action:
                    raise AssertionError(f"{path} completed with unexpected action {payload.get('action')!r}")
                if payload.get("status") is None:
                    raise AssertionError(f"{path} completed without a status snapshot")
                return payload

            if event_name == "error":
                raise AssertionError(f"{path} emitted an error: {payload.get('message', 'unknown error')}")

    raise AssertionError(f"{path} ended without a completion event")


async def verify_runtime_action_streams() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=180.0) as client:
            reload_payload = await verify_runtime_stream(client, "/api/runtime/reload/stream", expected_action="reload")
            if reload_payload.get("success") is not True:
                raise AssertionError("Runtime reload stream should complete successfully")
            reload_status_payload = reload_payload.get("status") or {}
            reload_inference_status = str(reload_status_payload.get("inference_status", "")).strip()
            if not reload_inference_status:
                raise AssertionError("Runtime reload stream completed without an inference status")
            reload_metrics = reload_status_payload.get("inference_metrics") or {}
            if "last_completion_ms" not in reload_metrics or "last_warmup_ms" not in reload_metrics:
                raise AssertionError("Runtime reload stream completed without inference timing metrics")

            with (
                patch(
                    "backend.services.runtime_service.prepare_sandbox_backend",
                    AsyncMock(
                        return_value=SandboxPreparation(
                            requested_backend="process",
                            attempted_backend="process",
                            attempted=False,
                            success=True,
                            detail="process backend configured; Docker image preparation skipped.",
                        )
                    ),
                ),
                patch(
                    "backend.services.runtime_service.prepare_embedding_model",
                    AsyncMock(
                        return_value=EmbeddingModelPreparation(
                            attempted=False,
                            success=True,
                            detail="Embedding model is already cached for regression verification.",
                        )
                    ),
                ),
                patch(
                    "backend.services.runtime_service.prepare_llamacpp_runtime",
                    AsyncMock(
                        return_value=LlamaCppPreparation(
                            attempted=False,
                            success=True,
                            detail="llamacpp provider is not active; model preparation skipped.",
                        )
                    ),
                ),
                patch(
                    "core.app_runtime.AppRuntime.prepare_inference_runtime",
                    AsyncMock(
                        return_value=InferenceRuntimePreparation(
                            attempted=True,
                            success=True,
                            detail="Active provider runtime warmed for regression verification.",
                        )
                    ),
                ),
            ):
                prepare_payload = await verify_runtime_stream(client, "/api/runtime/prepare/stream", expected_action="prepare")

            if prepare_payload.get("success") is not True:
                raise AssertionError("Runtime prepare stream should complete successfully")
            lines = prepare_payload.get("lines") or []
            if not any("Sandbox preparation" in str(line) for line in lines):
                raise AssertionError("Runtime prepare stream did not include sandbox preparation details")
            if not any("Embedding model" in str(line) for line in lines):
                raise AssertionError("Runtime prepare stream did not include embedding-model preparation details")
            if not any("Inference runtime" in str(line) for line in lines):
                raise AssertionError("Runtime prepare stream did not report inference-runtime warm-up details")
            if not any("Search runtime" in str(line) for line in lines):
                raise AssertionError("Runtime prepare stream did not report search-runtime preparation details")

            status_payload = prepare_payload.get("status") or {}
            inference_status = str(status_payload.get("inference_status", "")).strip()
            if not inference_status:
                raise AssertionError("Runtime prepare stream completed without an inference status")
            inference_metrics = status_payload.get("inference_metrics") or {}
            if "last_completion_ms" not in inference_metrics or "last_warmup_ms" not in inference_metrics:
                raise AssertionError("Runtime prepare stream completed without inference timing metrics")
            search_status = str(status_payload.get("search_status", "")).strip()
            if not search_status:
                raise AssertionError("Runtime prepare stream completed without a search status")
            if "Warming" in search_status:
                raise AssertionError("Runtime prepare stream should settle search warm-up before completing")

            print("Runtime action stream regression passed.")
    finally:
        await shutdown_runtime()


async def main() -> None:
    verify_launcher_files()
    await smoke_long_running_command(
        "Primary watcher-driven launcher",
        "cmd /c run.bat",
        readiness_urls=[
            "http://127.0.0.1:5173/",
            "http://127.0.0.1:8000/",
        ],
        required_output_snippets=["Starting the primary React interface."],
    )
    await smoke_long_running_command(
        "Stable no-reload hybrid flow",
        "cmd /c npm run dev:hybrid:stable",
        readiness_urls=[
            "http://127.0.0.1:5173/",
            "http://127.0.0.1:8000/",
        ],
    )
    await verify_command_center_inventory()
    await verify_runtime_action_streams()
    await verify_chat_stream_initial_snapshot()
    await verify_inference_status_warming_during_background_warmup()
    await verify_inference_status_degraded_on_failure()
    await verify_mission_stream()
    print("Hybrid workflow regression passed.")


if __name__ == "__main__":
    asyncio.run(main())