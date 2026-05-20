"""Algorithmic Art Skill — Compile and save interactive p5.js art artifacts."""

from __future__ import annotations
import os
import re
from pathlib import Path

# Locate workspace root relative to this script
SKILL_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = SKILL_DIR.parent.parent

async def create_art_artifact(
    art_title: str,
    html_code: str,
    output_name: str | None = None
) -> str:
    """
    Compiles and saves a self-contained interactive p5.js art piece into the workspace build directory.

    Args:
        art_title: The conceptual title of the algorithmic art movement or piece.
        html_code: The complete, self-contained HTML string (including inline p5.js canvas logic and UI controls).
        output_name: Optional custom filename (slugified automatically if not provided).

    Returns:
        A status message with the absolute path to the saved interactive file.
    """
    try:
        # 1. Establish an output directory inside the workspace
        build_dir = WORKSPACE_ROOT / "build" / "algorithmic-art"
        build_dir.mkdir(parents=True, exist_ok=True)

        # 2. Resolve safe filename
        if not output_name:
            # Clean and slugify the title
            slug = art_title.lower()
            slug = re.sub(r'[^a-z0-9\s-]', '', slug)
            slug = re.sub(r'[\s-]+', '-', slug).strip('-')
            filename = f"{slug}.html"
        else:
            filename = output_name if output_name.endswith(".html") else f"{output_name}.html"

        target_file = build_dir / filename

        # 3. Validation safeguard: Ensure it contains the core canvas framework
        if "p5.js" not in html_code and "setup()" not in html_code:
            return "Error: Provided HTML missing foundational p5.js components or canvas lifecycle setup."

        # 4. Write the file to disk
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(html_code)

        # 5. Return confirmation to the orchestration loop
        return (
            f"Successfully compiled and rendered algorithmic artwork: '{art_title}'\n"
            f"Artifact saved locally to: {target_file.absolute()}\n"
            f"You can now open this file in any browser or live server preview to test parameters."
        )

    except Exception as e:
        return f"Failed to execute art generation tool due to an internal error: {str(e)}"