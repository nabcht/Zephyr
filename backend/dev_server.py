"""Development launcher for the watcher-driven hybrid backend."""

from __future__ import annotations

from pathlib import Path

import uvicorn

try:
    from watchfiles import PythonFilter, run_process
except ImportError:  # pragma: no cover - fallback for environments without watchfiles
    PythonFilter = None
    run_process = None


ROOT = Path(__file__).resolve().parents[1]
WATCH_PATHS = (
    ROOT / "backend",
    ROOT / "core",
    ROOT / "skills",
    ROOT / "config.py",
)


def serve() -> None:
    """Run the FastAPI backend without delegating reload to Uvicorn."""
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000)


if PythonFilter is not None:

    class BackendReloadFilter(PythonFilter):
        """Keep process reloads scoped to backend-affecting Python changes."""

        def __call__(self, change: object, path: str) -> bool:
            relative_path = Path(path).resolve().relative_to(ROOT).as_posix()

            if relative_path == "config.py":
                return True

            if relative_path.startswith("skills/") and "/scripts/" in relative_path:
                return False

            return super().__call__(change, path)


def main() -> None:
    """Run the FastAPI backend with a stable reload scope for hybrid development."""
    if run_process is None or PythonFilter is None:
        uvicorn.run(
            "backend.main:app",
            host="127.0.0.1",
            port=8000,
            reload=True,
            reload_excludes=["skills/*/scripts/*.py"],
        )
        return

    run_process(*WATCH_PATHS, target=serve, watch_filter=BackendReloadFilter())


if __name__ == "__main__":
    main()