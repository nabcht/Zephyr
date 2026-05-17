# merge_files_recursively/__init__.py
"""uZephyr skill: merge_files_recursively

This skill provides a single asynchronous entry point ``run`` that accepts a
path to a directory, walks the tree recursively, concatenates the contents of
all ``.py`` files in a deterministic depth‑first alphabetical order and returns
the combined source as a string.

The function is deliberately simple and has no external dependencies, making
it suitable for inclusion in the `skills/` directory of a uZephyr project.

The implementation includes comprehensive docstrings, type hints and robust
error handling for I/O operations.
"""

import asyncio
import os
from pathlib import Path
from typing import List


async def _read_file(path: Path) -> str:
    """Read a single file safely.

    Parameters
    ----------
    path: Path
        Path object pointing to a ``.py`` file.

    Returns
    -------
    str
        The file contents as a string.
    """
    try:
        return path.read_text(encoding="utf-8")
    except Exception as exc:
        raise IOError(f"Failed to read {path}: {exc}") from exc


def _collect_py_files(root: Path) -> List[Path]:
    """Collect ``.py`` files in depth‑first alphabetical order.

    Parameters
    ----------
    root: Path
        Root directory to start the walk.

    Returns
    -------
    List[Path]
        Sorted list of Paths.
    """
    if not root.is_dir():
        raise NotADirectoryError(f"{root} is not a directory")
    files: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # sort directories and files for deterministic order
        dirnames.sort()
        filenames.sort()
        for fname in filenames:
            if fname.lower().endswith('.py'):
                files.append(Path(dirpath) / fname)
    return files


async def run(root_dir: str) -> str:
    """Entry point for the uZephyr skill.

    Parameters
    ----------
    root_dir: str
        Path to the directory that should be processed.

    Returns
    -------
    str
        A single string containing the concatenated source of all ``.py``
        files. Each file is prefixed with a marker comment indicating the
        relative path, e.g. ``# ---- path/to/file.py ----``.
    """
    root = Path(root_dir).resolve()
    try:
        py_files = _collect_py_files(root)
    except Exception as exc:
        raise RuntimeError(f"Error while collecting Python files: {exc}") from exc

    if not py_files:
        return ""  # nothing to merge

    parts: List[str] = []
    for file_path in py_files:
        rel = file_path.relative_to(root)
        header = f"# ---- {rel.as_posix()} ----"
        try:
            content = await _read_file(file_path)
        except Exception as exc:
            raise RuntimeError(f"Error reading file {rel}: {exc}") from exc
        parts.append(header)
        parts.append(content.rstrip())  # strip trailing newlines for neatness
        parts.append("\n")  # ensure separation
    return "\n".join(parts)


# Optional: provide a synchronous wrapper for convenience
def merge_sync(root_dir: str) -> str:
    """Synchronous wrapper around :func:`run`.

    This can be used in contexts where ``asyncio`` is not desired.
    """
    return asyncio.run(run(root_dir))
