"""Recursively merge Python files under a directory tree."""

import os


async def merge_python_files(root_dir: str) -> str:
    """Recursively merge all ``.py`` files under ``root_dir``.

    Parameters
    ----------
    root_dir: str
        Directory to traverse.

    Returns
    -------
    str
        Concatenated source with header comments indicating each file's
        absolute path.
    """
    if not os.path.isdir(root_dir):
        raise FileNotFoundError(f"Directory '{root_dir}' not found.")

    merged: list[str] = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in sorted(filenames):
            if not fn.lower().endswith(".py"):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    content = f.read()
                header = f"# ---- {os.path.abspath(fp)} ----"
                merged.append(header)
                merged.append(content)
            except OSError as e:
                raise OSError(f"Failed to read '{fp}': {e}")

    return "\n\n".join(merged)
