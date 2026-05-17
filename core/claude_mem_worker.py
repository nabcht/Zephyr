"""Claude-Mem worker lifecycle helpers for optional local autostart."""

from __future__ import annotations

import logging
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import config

log = logging.getLogger("uzephyr.claude_mem_worker")

_worker_process: subprocess.Popen[str] | None = None


def is_worker_running(host: str | None = None, port: int | None = None, timeout: float = 0.2) -> bool:
    selected_host = host or config.CLAUDE_MEM_WORKER_HOST
    selected_port = port or config.CLAUDE_MEM_WORKER_PORT

    try:
        with socket.create_connection((selected_host, selected_port), timeout=timeout):
            return True
    except OSError:
        return False


def ensure_worker_started(console: Any | None = None) -> bool:
    global _worker_process

    if not config.EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED:
        log.info("Claude-Mem worker autostart skipped because external subprocess integrations are disabled.")
        if console is not None:
            console.print(
                "[warning]Claude-Mem worker autostart is disabled in this runtime; archive features may stay degraded.[/]"
            )
        return False

    if is_worker_running():
        return True

    if not config.CLAUDE_MEM_WORKER_AUTOSTART:
        return False

    if _worker_process is not None and _worker_process.poll() is None:
        return _wait_for_worker_startup(config.CLAUDE_MEM_WORKER_STARTUP_TIMEOUT)

    try:
        command = _resolve_launch_command(config.CLAUDE_MEM_WORKER_START_COMMAND)
    except ValueError as exc:
        log.warning("Failed to start Claude-Mem worker: %s", exc)
        if console is not None:
            console.print(f"[warning]Claude-Mem worker autostart failed: {exc}[/]")
        _worker_process = None
        return False

    try:
        _worker_process = subprocess.Popen(
            command,
            cwd=str(config.CLAUDE_MEM_WORKER_START_CWD),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, ValueError) as exc:
        log.warning("Failed to start Claude-Mem worker: %s", exc)
        if console is not None:
            console.print(f"[warning]Claude-Mem worker autostart failed: {exc}[/]")
        _worker_process = None
        return False

    started = _wait_for_worker_startup(config.CLAUDE_MEM_WORKER_STARTUP_TIMEOUT)
    if started and console is not None:
        console.print("[info]Claude-Mem worker started automatically.[/]")
    elif not started:
        log.warning("Claude-Mem worker process started but did not become ready before timeout.")
        if console is not None:
            console.print("[warning]Claude-Mem worker autostart timed out; archive features may stay degraded.[/]")
    return started


def _resolve_launch_command(command: list[str]) -> list[str]:
    if not command:
        raise ValueError("Claude-Mem worker start command is empty.")

    executable = command[0]
    args = list(command[1:])
    resolved_executable = _resolve_executable(executable)
    if resolved_executable is None:
        raise ValueError(f"Could not find Claude-Mem worker launcher '{executable}'.")

    lowered = resolved_executable.lower()
    if lowered.endswith((".cmd", ".bat")):
        return [os.environ.get("ComSpec", "cmd.exe"), "/c", resolved_executable, *args]

    return [resolved_executable, *args]


def _resolve_executable(executable: str) -> str | None:
    path_candidate = Path(executable)
    if path_candidate.is_file():
        return str(path_candidate)

    direct_match = shutil.which(executable)
    if direct_match:
        return direct_match

    lowered = executable.lower()
    if lowered == "npx":
        for candidate in _npx_candidates():
            if candidate.is_file():
                return str(candidate)
            resolved = shutil.which(str(candidate)) if candidate.parent == Path(".") else None
            if resolved:
                return resolved
        for fallback_name in ("npx.cmd", "npx.exe"):
            resolved = shutil.which(fallback_name)
            if resolved:
                return resolved

    return None


def _npx_candidates() -> list[Path]:
    candidates = [Path("npx.cmd"), Path("npx.exe")]
    for env_var in ("ProgramFiles", "ProgramFiles(x86)"):
        root = os.environ.get(env_var)
        if root:
            candidates.append(Path(root) / "nodejs" / "npx.cmd")
            candidates.append(Path(root) / "nodejs" / "npx.exe")
    return candidates


def stop_managed_worker() -> None:
    global _worker_process

    if _worker_process is None:
        return

    if _worker_process.poll() is None:
        _worker_process.terminate()
        try:
            _worker_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _worker_process.kill()
            _worker_process.wait(timeout=3)

    _worker_process = None


def _wait_for_worker_startup(timeout_seconds: float) -> bool:
    deadline = time.monotonic() + max(timeout_seconds, 0.0)
    while time.monotonic() < deadline:
        if is_worker_running():
            return True
        time.sleep(0.2)
    return is_worker_running()