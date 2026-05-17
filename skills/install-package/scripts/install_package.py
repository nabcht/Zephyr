"""Skill: install a Python package into the current virtual environment via pip."""

from __future__ import annotations

import re
import subprocess
import sys


async def install_python_package(package_name: str) -> str:
    """Install a Python pip package into the currently active environment.

    This is useful when another skill or tool requires a third-party package
    that is not yet installed.  The installation runs against the same Python
    interpreter that is running μZephyr, so it honours virtualenvs.

    Args:
        package_name: The pip package specifier to install (e.g. "requests",
                      "beautifulsoup4>=4.12").
    """
    # Sanitise: allow only valid pip specifiers (name with optional version)
    if not re.match(r"^[A-Za-z0-9_][A-Za-z0-9._-]*(\[.*\])?(([><=!~]=?|@)\S*)*$", package_name):
        return f"Error: '{package_name}' does not look like a valid pip package specifier."

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package_name],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return f"Successfully installed '{package_name}'.\n{result.stdout[-500:]}"
        else:
            return (
                f"Failed to install '{package_name}' (exit code {result.returncode}).\n"
                f"stdout: {result.stdout[-300:]}\n"
                f"stderr: {result.stderr[-300:]}"
            )
    except subprocess.TimeoutExpired:
        return f"Error: installation of '{package_name}' timed out after 120 seconds."
    except Exception as exc:
        return f"Error installing '{package_name}': {type(exc).__name__}: {exc}"
