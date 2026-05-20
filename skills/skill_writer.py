"""Skill writer — allows the LLM to create new agentskills.io-compatible skill packages dynamically.

Each skill is stored as a directory following the agentskills.io open standard:

    skills/<skill-name>/
    ├── SKILL.md          ← required: YAML frontmatter + instructions
    └── scripts/
        └── <skill_name>.py  ← executable Python code
"""

from __future__ import annotations

import ast
import logging
import re
import textwrap
from pathlib import Path

import config

log = logging.getLogger("zephyr.skill_writer")

# ── AST-based safety analysis ─────────────────────────────────────────────

# Dangerous module-level imports
_BLOCKED_IMPORTS: set[str] = {
    "subprocess", "shutil", "ctypes", "multiprocessing",
    "socket", "http.server", "xmlrpc", "pickle", "shelve",
    "webbrowser", "code", "codeop", "compileall",
}

# Dangerous attribute calls: (module_or_obj, method_name)
_BLOCKED_ATTR_CALLS: set[tuple[str, str]] = {
    ("os", "system"),
    ("os", "popen"),
    ("os", "exec"),
    ("os", "execl"),
    ("os", "execle"),
    ("os", "execlp"),
    ("os", "execv"),
    ("os", "execve"),
    ("os", "execvp"),
    ("os", "execvpe"),
    ("os", "spawn"),
    ("os", "spawnl"),
    ("os", "spawnle"),
    ("os", "remove"),
    ("os", "unlink"),
    ("os", "rmdir"),
    ("os", "removedirs"),
    ("os", "rename"),
    ("sys", "exit"),
    ("pathlib", "unlink"),
}

# Dangerous built-in function names
_BLOCKED_BUILTINS: set[str] = {
    "eval", "exec", "compile", "__import__", "globals", "locals",
    "breakpoint", "exit", "quit",
}


def _ast_safety_check(tree: ast.AST) -> str:
    """Walk the AST and return a human-readable reason if dangerous patterns are found,
    or an empty string if the code is safe.
    """
    for node in ast.walk(tree):
        # ── Block dangerous imports ──────────────────────────────────
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_mod = alias.name.split(".")[0]
                if root_mod in _BLOCKED_IMPORTS:
                    return f"Import of blocked module '{alias.name}'."

        if isinstance(node, ast.ImportFrom):
            if node.module:
                root_mod = node.module.split(".")[0]
                if root_mod in _BLOCKED_IMPORTS:
                    return f"Import from blocked module '{node.module}'."

        # ── Block dangerous built-in calls ───────────────────────────
        if isinstance(node, ast.Call):
            func = node.func

            # Direct call: eval(...), exec(...), __import__(...)
            if isinstance(func, ast.Name) and func.id in _BLOCKED_BUILTINS:
                return f"Call to blocked built-in '{func.id}()'."

            # Attribute call: os.system(...), subprocess.run(...)
            if isinstance(func, ast.Attribute):
                # Resolve simple `module.method` patterns
                if isinstance(func.value, ast.Name):
                    pair = (func.value.id, func.attr)
                    if pair in _BLOCKED_ATTR_CALLS:
                        return f"Call to blocked function '{func.value.id}.{func.attr}()'."

                # Also catch chained access like os.path.join being fine,
                # but flag the attr name itself in the blocked set
                if func.attr in ("system", "popen"):
                    return f"Call to potentially dangerous method '.{func.attr}()'."

        # ── Block direct __dunder__ attribute access on modules ──────
        if isinstance(node, ast.Attribute):
            if node.attr in ("__subclasses__", "__bases__", "__globals__",
                             "__code__", "__builtins__"):
                return f"Access to restricted dunder attribute '{node.attr}'."

    return ""


# ── agentskills.io helpers ────────────────────────────────────────────────────

def _to_kebab(name: str) -> str:
    """Normalise a skill name to agentskills.io kebab-case.

    Accepts snake_case, camelCase, or already-kebab input and returns a
    lowercase hyphen-separated name with no consecutive hyphens.
    """
    # CamelCase → insert hyphens before uppercase letters
    name = re.sub(r"([A-Z])", r"-\1", name)
    # Replace underscores and spaces with hyphens
    name = re.sub(r"[_\s]+", "-", name)
    # Strip any character that is not alphanumeric or hyphen
    name = re.sub(r"[^a-z0-9\-]", "", name.lower())
    # Collapse consecutive hyphens and strip leading/trailing hyphens
    name = re.sub(r"-{2,}", "-", name).strip("-")
    return name


def _to_snake(kebab: str) -> str:
    """Convert a kebab-case name to snake_case (valid Python identifier)."""
    return kebab.replace("-", "_")


def _extract_description(code: str) -> str:
    """Return the first module-level or function-level docstring found in *code*."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ""

    # Module docstring
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        return tree.body[0].value.value.strip().splitlines()[0]

    # First function docstring
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            docstring = ast.get_docstring(node)
            if docstring:
                return docstring.strip().splitlines()[0]

    return ""


def _build_skill_md(kebab_name: str, description: str, tags: list[str] = None) -> str:
    """Generate a SKILL.md file with valid agentskills.io frontmatter."""
    safe_desc = description.replace('"', "'") if description else f"Skill: {kebab_name}"
    tag_list = tags if tags else ["general"]
    
    return textwrap.dedent(f"""\
        ---
        name: {kebab_name}
        description: {safe_desc}
        compatibility: Requires Python 3.10+
        tags: {tag_list}
        ---

        # {kebab_name}
        {description}
        """)


async def write_skill(skill_name: str, code: str, description: str = "", tags: list[str] = None) -> str:
    """
    Args:
        skill_name: Name of the skill.
        code: Python source code.
        description: Description for the LLM.
        tags: List of personas authorized to use this (e.g. ["researcher", "coder"]).
    """
    # ── Normalise names ───────────────────────────────────────────────
    kebab_name = _to_kebab(skill_name)
    if not kebab_name:
        return f"Invalid skill name: '{skill_name}'. Could not convert to a valid kebab-case identifier."

    snake_name = _to_snake(kebab_name)

    # Prevent overwriting infrastructure files
    protected = {"__init__", "skill_loader", "skill_writer"}
    if snake_name in protected:
        return f"Cannot overwrite protected skill: '{snake_name}'."

    # ── Validate Python syntax ────────────────────────────────────────
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"Syntax error in provided code: {exc}"

    # Verify the code defines at least one function
    has_function = any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for node in ast.walk(tree)
    )
    if not has_function:
        return "The code must define at least one function to be usable as a tool."

    # ── Safety checks ─────────────────────────────────────────────────
    unsafe_report = _ast_safety_check(tree)
    if unsafe_report:
        log.warning("Blocked unsafe code in '%s': %s", kebab_name, unsafe_report)
        return f"Blocked: {unsafe_report} Refactor to use safer alternatives."

    # ── Resolve description ───────────────────────────────────────────
    if not description:
        description = _extract_description(code)

    # ── Build directory structure ─────────────────────────────────────
    skills_dir: Path = config.SKILLS_DIR
    skill_dir = skills_dir / kebab_name
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    skill_md_path = skill_dir / "SKILL.md"
    script_path = scripts_dir / f"{snake_name}.py"

    existed = skill_dir.exists() and script_path.exists()

    skill_md_path.write_text(_build_skill_md(kebab_name, description, tags), encoding="utf-8")
    script_path.write_text(code, encoding="utf-8")

    action = "Updated" if existed else "Created"
    log.info("%s skill package: %s", action, skill_dir)
    return (
        f"{action} skill '{kebab_name}' at {skill_dir}. "
        f"SKILL.md and scripts/{snake_name}.py written. "
        f"Use /reload or restart to activate."
    )
