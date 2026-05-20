"""Dynamic skill loader — discovers and registers Python functions from the /skills directory.

Now parses `tags: [array]` from SKILL.md to route tools to specific Agents (Coder, Researcher, etc).
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
import logging
import re
import sys
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

import config

if TYPE_CHECKING:
    from core.tool_engine import ToolEngine

log = logging.getLogger("zephyr.skill_loader")

# Files that are part of the loader infrastructure — never load as skills
_EXCLUDED: set[str] = {"__init__.py", "skill_loader.py", "skill_writer.py"}

# Mark certain skill names as sensitive (require Y/N confirmation)
_SENSITIVE_SKILLS: set[str] = {"compose_email", "create_calendar_event", "install_python_package"}


def _parse_skill_md_metadata(skill_dir: Path) -> dict[str, Any]:
    """Extract `description` and `tags` from SKILL.md YAML frontmatter."""
    meta = {
        "description": "",
        "tags": ["general"]  # Default tag if none is specified
    }
    
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return meta
        
    content = skill_md.read_text(encoding="utf-8")
    
    # Match frontmatter block between --- delimiters
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not fm_match:
        return meta
        
    frontmatter = fm_match.group(1)
    
    # 1. Extract Description
    desc_match = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
    if desc_match:
        meta["description"] = desc_match.group(1).strip()
        
    # 2. Extract Tags (e.g., tags:[researcher, coder])
    tags_match = re.search(r"^tags:\s*\[(.*?)\]", frontmatter, re.MULTILINE)
    if tags_match:
        raw_tags = tags_match.group(1)
        # Split by comma, remove quotes and whitespace
        parsed_tags =[t.strip().strip("'\"") for t in raw_tags.split(",") if t.strip()]
        if parsed_tags:
            meta["tags"] = parsed_tags
            
    return meta


class SkillLoader:
    """Scans the skills directory, dynamically imports modules, and registers async/sync functions as tools."""

    def __init__(self, engine: ToolEngine) -> None:
        self.engine = engine
        self.skills_dir: Path = config.SKILLS_DIR

    async def load(self) -> list[str]:
        """Discover skills from both flat files and directory packages."""
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        registered: list[str] =[]

        # ── Track which snake_case names are covered by directory packages ──
        package_snake_names: set[str] = set()

        # ── 1. Directory packages (agentskills.io standard) ──────────────────
        for skill_dir in sorted(self.skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            if not (skill_dir / "SKILL.md").is_file():
                continue  # not a valid skill package

            meta = _parse_skill_md_metadata(skill_dir)
            names = self._load_skill_package(skill_dir, meta["description"], meta["tags"])
            registered.extend(names)
            # Record snake_case equivalents so we skip flat files below
            package_snake_names.update(n for n in names)

        # ── 2. Legacy flat .py files ──────────────────────────────────────────
        for py_file in sorted(self.skills_dir.glob("*.py")):
            if py_file.name in _EXCLUDED:
                continue
            # Skip if a directory package already registered this function name
            if py_file.stem in package_snake_names:
                log.debug("Skipping flat file %s — covered by a skill package.", py_file.name)
                continue
            # Legacy files get the default "general" tag
            names = self._load_module(py_file, skill_desc="", tags=["general"])
            registered.extend(names)

        log.info("Loaded %d skill(s): %s", len(registered), registered)
        return registered

    def _load_skill_package(self, skill_dir: Path, skill_desc: str, tags: list[str]) -> list[str]:
        """Load all Python scripts from a directory-based skill package."""
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.is_dir():
            py_files = sorted(scripts_dir.glob("*.py"))
        else:
            py_files = sorted(p for p in skill_dir.glob("*.py") if not p.name.startswith("_"))

        names: list[str] =[]
        for py_file in py_files:
            names.extend(self._load_module(py_file, skill_desc=skill_desc, tags=tags))
        return names

    def _load_module(self, path: Path, skill_desc: str = "", tags: list[str] | None = None) -> list[str]:
        """Import a single .py file and register its public async/sync functions."""
        module_name = f"skills.{path.stem}"
        names: list[str] = []
        tags = tags or ["general"]

        try:
            # Remove stale module from cache to allow hot-reload
            if module_name in sys.modules:
                del sys.modules[module_name]

            spec = importlib.util.spec_from_file_location(module_name, str(path))
            if spec is None or spec.loader is None:
                log.warning("Cannot create module spec for %s", path)
                return names

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)  # type: ignore[union-attr]

        except Exception as exc:
            log.error("Failed to import skill %s: %s", path.name, exc)
            return names

        # Walk public callables
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            obj = getattr(module, attr_name)
            if not callable(obj):
                continue
            if not (inspect.isfunction(obj) or inspect.iscoroutinefunction(obj)):
                continue
            if getattr(obj, "__module__", None) != module.__name__:
                continue

            fn_name = obj.__name__
            # SKILL.md description takes precedence; fall back to function docstring
            fn_doc = inspect.getdoc(obj) or f"Skill from {path.name}"
            description = skill_desc if skill_desc else fn_doc
            sensitive = fn_name in _SENSITIVE_SKILLS

            try:
                self.engine.register(
                    obj,
                    name=fn_name,
                    description=description,
                    sensitive=sensitive,
                    tags=tags,
                    source="local",
                )
                names.append(fn_name)
            except Exception as exc:
                log.error("Failed to register %s from %s: %s", fn_name, path.name, exc)

        return names

    async def reload(self) -> list[str]:
        """Full reload: clear dynamic skills and re-discover."""
        # ── Collect all Python files to unload ───────────────────────
        py_files_to_unload: list[Path] =[]

        # Flat legacy files
        for py_file in self.skills_dir.glob("*.py"):
            if py_file.name not in _EXCLUDED:
                py_files_to_unload.append(py_file)

        # Directory package scripts
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            scripts_dir = skill_dir / "scripts"
            search_dir = scripts_dir if scripts_dir.is_dir() else skill_dir
            for py_file in search_dir.glob("*.py"):
                if not py_file.name.startswith("_"):
                    py_files_to_unload.append(py_file)

        # ── Unregister and evict from sys.modules ────────────────────
        for py_file in py_files_to_unload:
            module_name = f"skills.{py_file.stem}"
            if module_name in sys.modules:
                mod = sys.modules[module_name]
                for attr_name in dir(mod):
                    if attr_name.startswith("_"):
                        continue
                    obj = getattr(mod, attr_name)
                    if not (callable(obj) and inspect.isfunction(obj)):
                        continue
                    if getattr(obj, "__module__", None) != mod.__name__:
                        continue

                        self.engine.unregister(obj.__name__)
                del sys.modules[module_name]

        return await self.load()
    async def verify_skill_integrity(self, auto_repair: bool = False) -> dict[str, list[str]]:
        """
        Scans all skill packages to ensure SKILL.md is present and valid.
        Returns a report of 'valid', 'broken', and 'repaired' skills.
        """
        report = {"valid": [], "broken": [], "repaired": []}
        
        for skill_dir in sorted(self.skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
                continue
            
            skill_md = skill_dir / "SKILL.md"
            issues = []

            # 1. Check if SKILL.md exists
            if not skill_md.is_file():
                issues.append("Missing SKILL.md")
            else:
                # 2. Check for required metadata
                meta = _parse_skill_md_metadata(skill_dir)
                if not meta.get("description"):
                    issues.append("Empty or missing description")
                if meta.get("tags") == ["general"] and "general" not in skill_md.read_text():
                    # Defaulting to general is fine, but we flag if it's implicitly empty
                    pass 

            if not issues:
                report["valid"].append(skill_dir.name)
                continue

            # 3. AI-Powered Auto-Repair Integration
            if auto_repair:
                try:
                    from skills.skill_writer import _extract_description, _build_skill_md
                    
                    # Find the primary script to analyze
                    scripts = list((skill_dir / "scripts").glob("*.py")) or list(skill_dir.glob("*.py"))
                    if scripts:
                        code = scripts[0].read_text(encoding="utf-8")
                        # AI Logic: Extract docstring as description if missing
                        desc = _extract_description(code) or f"Automated description for {skill_dir.name}"
                        
                        # Rebuild the SKILL.md
                        new_md_content = _build_skill_md(
                            kebab_name=skill_dir.name,
                            description=desc,
                            tags=meta.get("tags", ["general"])
                        )
                        skill_md.write_text(new_md_content, encoding="utf-8")
                        report["repaired"].append(f"{skill_dir.name} (Fixed: {', '.join(issues)})")
                        log.info("AI Auto-Repair: Regenerated SKILL.md for %s", skill_dir.name)
                        continue
                except Exception as e:
                    log.error("Failed to repair %s: %s", skill_dir.name, e)

            report["broken"].append(f"{skill_dir.name} -> {', '.join(issues)}")

        return report