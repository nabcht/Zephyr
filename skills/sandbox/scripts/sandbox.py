from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import config


_SANDBOX_TIMEOUT_SECONDS = 15
_DOCKER_INFRA_FAILURE_CODES = {125, 126, 127}
_DOCKER_PROBE_TIMEOUT_SECONDS = 5
_DOCKER_PULL_TIMEOUT_SECONDS = 600


@dataclass(frozen=True, slots=True)
class SandboxReadiness:
    """Readiness status for the configured sandbox backend."""

    requested_backend: str
    effective_backend: str
    ready: bool
    detail: str


@dataclass(frozen=True, slots=True)
class SandboxPreparation:
    """Preparation result for the configured sandbox backend."""

    requested_backend: str
    attempted_backend: str
    attempted: bool
    success: bool
    detail: str


def _build_sandbox_env(sandbox_root: Path) -> dict[str, str]:
    """Create a minimal process environment for contained sandbox execution."""
    workspace_dir = sandbox_root / "workspace"
    home_dir = sandbox_root / "home"
    temp_dir = sandbox_root / "tmp"
    roaming_dir = home_dir / "AppData" / "Roaming"
    local_dir = home_dir / "AppData" / "Local"

    for directory in (workspace_dir, home_dir, temp_dir, roaming_dir, local_dir):
        directory.mkdir(parents=True, exist_ok=True)

    env: dict[str, str] = {}
    for key in (
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "PATH",
        "PATHEXT",
        "OS",
        "PROCESSOR_ARCHITECTURE",
        "PROCESSOR_IDENTIFIER",
        "NUMBER_OF_PROCESSORS",
    ):
        value = os.environ.get(key)
        if value:
            env[key] = value

    env.update(
        {
            "HOME": str(home_dir),
            "USERPROFILE": str(home_dir),
            "APPDATA": str(roaming_dir),
            "LOCALAPPDATA": str(local_dir),
            "TEMP": str(temp_dir),
            "TMP": str(temp_dir),
            "TMPDIR": str(temp_dir),
            "PYTHONNOUSERSITE": "1",
        }
    )
    return env


def _requested_backend() -> str:
    backend = getattr(config, "SANDBOX_BACKEND", "auto").strip().lower()
    if backend in {"auto", "process", "docker"}:
        return backend
    return "auto"


def _docker_cli_available() -> bool:
    return shutil.which("docker") is not None


def _run_docker_probe(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=_DOCKER_PROBE_TIMEOUT_SECONDS,
        stdin=subprocess.DEVNULL,
    )


def _normalize_probe_output(result: subprocess.CompletedProcess[str]) -> str:
    summary = " ".join(((result.stderr or "") or (result.stdout or "")).split())
    return summary[:160] if summary else f"exit code {result.returncode}"


def _probe_docker_backend() -> tuple[bool, str]:
    if not _docker_cli_available():
        return False, "docker CLI is unavailable."

    try:
        version_result = _run_docker_probe(["docker", "version", "--format", "{{.Server.Version}}"])
    except subprocess.TimeoutExpired:
        return False, "docker daemon probe timed out."
    except Exception as exc:
        return False, f"docker daemon probe failed: {exc}"

    if version_result.returncode != 0:
        return False, f"docker daemon unavailable: {_normalize_probe_output(version_result)}"

    try:
        image_result = _run_docker_probe(["docker", "image", "inspect", config.SANDBOX_DOCKER_IMAGE])
    except subprocess.TimeoutExpired:
        return False, f"docker image probe timed out for {config.SANDBOX_DOCKER_IMAGE}."
    except Exception as exc:
        return False, f"docker image probe failed: {exc}"

    if image_result.returncode != 0:
        return False, f"docker image '{config.SANDBOX_DOCKER_IMAGE}' is not available locally."

    docker_version = (version_result.stdout or "").strip() or "unknown"
    return True, f"docker daemon reachable, image '{config.SANDBOX_DOCKER_IMAGE}' available locally, server version {docker_version}."


def get_sandbox_readiness() -> SandboxReadiness:
    """Return readiness for the configured sandbox backend with Docker-aware detail."""
    requested_backend = _requested_backend()

    if requested_backend == "process":
        return SandboxReadiness(
            requested_backend="process",
            effective_backend="process",
            ready=True,
            detail="process backend ready; Docker probe skipped because SANDBOX_BACKEND=process.",
        )

    docker_ready, docker_detail = _probe_docker_backend()
    if requested_backend == "docker":
        return SandboxReadiness(
            requested_backend="docker",
            effective_backend="docker",
            ready=docker_ready,
            detail=(
                f"docker backend ready: {docker_detail}"
                if docker_ready
                else f"docker backend unavailable: {docker_detail}"
            ),
        )

    if docker_ready:
        return SandboxReadiness(
            requested_backend="auto",
            effective_backend="docker",
            ready=True,
            detail=f"auto mode will prefer Docker: {docker_detail}",
        )

    return SandboxReadiness(
        requested_backend="auto",
        effective_backend="process",
        ready=True,
        detail=f"auto mode will fall back to process isolation because Docker is unavailable: {docker_detail}",
    )


def describe_sandbox_readiness() -> list[str]:
    """Render sandbox readiness in a compact verify-friendly format."""
    readiness = get_sandbox_readiness()
    status = "ready" if readiness.ready else "not ready"
    return [
        f"Sandbox readiness: {status}",
        f"Sandbox backend: requested={readiness.requested_backend}, effective={readiness.effective_backend}",
        f"Sandbox detail: {readiness.detail}",
    ]


def describe_sandbox_preparation(preparation: SandboxPreparation) -> list[str]:
    """Render sandbox preparation in a compact CLI-friendly format."""
    if preparation.success and preparation.attempted:
        status = "prepared"
    elif preparation.success:
        status = "ready"
    else:
        status = "failed"
    return [
        f"Sandbox preparation: {status}",
        (
            f"Sandbox preparation backend: requested={preparation.requested_backend}, "
            f"attempted={preparation.attempted_backend}"
        ),
        f"Sandbox preparation detail: {preparation.detail}",
    ]


def _run_docker_pull() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "pull", config.SANDBOX_DOCKER_IMAGE],
        capture_output=True,
        text=True,
        timeout=_DOCKER_PULL_TIMEOUT_SECONDS,
        stdin=subprocess.DEVNULL,
    )


async def prepare_sandbox_backend() -> SandboxPreparation:
    """Prepare the configured sandbox backend, pulling the Docker image when appropriate."""
    requested_backend = _requested_backend()

    if requested_backend == "process":
        return SandboxPreparation(
            requested_backend="process",
            attempted_backend="process",
            attempted=False,
            success=True,
            detail="process backend configured; Docker image preparation skipped.",
        )

    if not _docker_cli_available():
        return SandboxPreparation(
            requested_backend=requested_backend,
            attempted_backend="docker",
            attempted=False,
            success=False,
            detail="docker CLI is unavailable.",
        )

    readiness = get_sandbox_readiness()
    if readiness.ready and readiness.effective_backend == "docker":
        return SandboxPreparation(
            requested_backend=requested_backend,
            attempted_backend="docker",
            attempted=False,
            success=True,
            detail="docker sandbox backend is already ready.",
        )

    if "not available locally" not in readiness.detail:
        return SandboxPreparation(
            requested_backend=requested_backend,
            attempted_backend="docker",
            attempted=False,
            success=False,
            detail=readiness.detail,
        )

    loop = asyncio.get_running_loop()
    try:
        pull_result = await loop.run_in_executor(None, _run_docker_pull)
    except subprocess.TimeoutExpired:
        return SandboxPreparation(
            requested_backend=requested_backend,
            attempted_backend="docker",
            attempted=True,
            success=False,
            detail=f"docker pull timed out for {config.SANDBOX_DOCKER_IMAGE}.",
        )
    except Exception as exc:
        return SandboxPreparation(
            requested_backend=requested_backend,
            attempted_backend="docker",
            attempted=True,
            success=False,
            detail=f"docker pull failed: {exc}",
        )

    if pull_result.returncode != 0:
        return SandboxPreparation(
            requested_backend=requested_backend,
            attempted_backend="docker",
            attempted=True,
            success=False,
            detail=(
                f"docker pull failed for {config.SANDBOX_DOCKER_IMAGE}: "
                f"{_normalize_probe_output(pull_result)}"
            ),
        )

    post_readiness = get_sandbox_readiness()
    if post_readiness.ready and post_readiness.effective_backend == "docker":
        return SandboxPreparation(
            requested_backend=requested_backend,
            attempted_backend="docker",
            attempted=True,
            success=True,
            detail=f"docker image '{config.SANDBOX_DOCKER_IMAGE}' prepared and sandbox is ready.",
        )

    return SandboxPreparation(
        requested_backend=requested_backend,
        attempted_backend="docker",
        attempted=True,
        success=False,
        detail=post_readiness.detail,
    )


def _build_docker_command(workspace_dir: Path) -> list[str]:
    mount_arg = f"{workspace_dir.resolve()}:/workspace:rw"
    return [
        "docker",
        "run",
        "--rm",
        "--pull=never",
        "--network",
        "none",
        "--pids-limit",
        "64",
        "--memory",
        "256m",
        "--cpus",
        "1.0",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=64m",
        "-v",
        mount_arg,
        "-w",
        "/workspace",
        config.SANDBOX_DOCKER_IMAGE,
        "python",
        "-I",
        "-B",
        "/workspace/sandbox_test.py",
    ]


def _run_process_backend(script_path: Path, workspace_dir: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-B", str(script_path)],
        capture_output=True,
        text=True,
        timeout=_SANDBOX_TIMEOUT_SECONDS,
        cwd=workspace_dir,
        env=env,
        stdin=subprocess.DEVNULL,
    )


def _run_docker_backend(workspace_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _build_docker_command(workspace_dir),
        capture_output=True,
        text=True,
        timeout=_SANDBOX_TIMEOUT_SECONDS,
        stdin=subprocess.DEVNULL,
    )


def _format_report(
    result: subprocess.CompletedProcess[str],
    *,
    backend: str,
    backend_note: str = "",
) -> str:
    report = []
    if result.returncode == 0:
        report.append("✅ TEST PASSED")
    else:
        report.append(f"❌ TEST FAILED (Exit Code {result.returncode})")

    backend_line = f"BACKEND: {backend}"
    if backend_note:
        backend_line = f"{backend_line} ({backend_note})"
    report.append(backend_line)
    report.append(f"STDOUT:\n{result.stdout}")
    if result.stderr:
        report.append(f"STDERR:\n{result.stderr}")
    return "\n".join(report)


def _summarize_docker_failure(result: subprocess.CompletedProcess[str]) -> str:
    summary = " ".join((result.stderr or "").split()) or f"docker exit {result.returncode}"
    return summary[:160]


async def run_test_in_sandbox(
    code: str = "",
    requirements: list[str] | None = None,
    description: str = "",
    **_ignored: Any,
) -> str:
    """
    Executes a snippet of Python code in a temporary sandbox.
    Use this to verify code works before finalizing a mission.
    """
    if not code.strip():
        if description.strip():
            return "❌ ERROR: Sandbox verification requires executable Python in the 'code' field, not only a description."
        return "❌ ERROR: Sandbox verification requires a non-empty 'code' field."

    if requirements:
        # Check if requirements are installed, or install them in a temp path
        pass 

    try:
        with tempfile.TemporaryDirectory(prefix="uzephyr-sandbox-") as sandbox_dir:
            sandbox_root = Path(sandbox_dir)
            workspace_dir = sandbox_root / "workspace"
            script_path = workspace_dir / "sandbox_test.py"
            env = _build_sandbox_env(sandbox_root)
            requested_backend = _requested_backend()

            script_path.write_text(code, encoding="utf-8")

            if requested_backend == "docker":
                if not _docker_cli_available():
                    return "❌ ERROR: Docker sandbox requested but docker CLI is unavailable."
                return _format_report(_run_docker_backend(workspace_dir), backend="docker")

            if requested_backend == "auto" and _docker_cli_available():
                docker_result = _run_docker_backend(workspace_dir)
                if docker_result.returncode not in _DOCKER_INFRA_FAILURE_CODES:
                    return _format_report(docker_result, backend="docker")

                process_result = _run_process_backend(script_path, workspace_dir, env)
                return _format_report(
                    process_result,
                    backend="process",
                    backend_note=f"docker fallback: {_summarize_docker_failure(docker_result)}",
                )

            process_note = "docker unavailable" if requested_backend == "auto" else ""
            return _format_report(
                _run_process_backend(script_path, workspace_dir, env),
                backend="process",
                backend_note=process_note,
            )

    except subprocess.TimeoutExpired:
        return "❌ ERROR: Execution timed out (Possible infinite loop)."
    except Exception as exc:
        return f"❌ ERROR: Sandbox crash: {exc}"