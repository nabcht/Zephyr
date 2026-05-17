import ast
import hashlib
import json
from datetime import datetime
from pathlib import Path

import config


_ALLOWED_FILES = {"main.py", "config.py"}
_ALLOWED_PREFIXES = ("core/",)


def _content_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _normalize_target_path(file_path: str) -> Path:
    target = Path(file_path)
    if target.is_absolute() or any(part == ".." for part in target.parts):
        raise ValueError(f"Invalid target path: {file_path}")
    return target


def _is_allowed_path(target: Path) -> bool:
    target_str = target.as_posix()
    return target_str in _ALLOWED_FILES or any(target_str.startswith(prefix) for prefix in _ALLOWED_PREFIXES)


def _timestamped_backup_path(target: Path) -> Path:
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    backup_name = f"{target.name}_{ts}.bak"
    return config.RUNTIME_ROOT / "backups" / target.parent / backup_name


def _staged_file_path(target: Path) -> Path:
    return config.RUNTIME_ROOT / "temp_core" / target


def _staged_metadata_path(target: Path) -> Path:
    staged_file = _staged_file_path(target)
    return staged_file.with_name(f"{staged_file.name}.meta.json")


def _live_file_path(target: Path) -> Path:
    return config.PROJECT_ROOT / target


def _memories_file_path() -> Path:
    return config.KNOWLEDGE_DIR / 'memories.md'

async def propose_core_change(file_path: str, new_code: str, reasoning: str):
    """
    Validates, backups, and stages changes to core project files.
    Restricted to standard file operations to ensure environment compliance.
    """
    # 1. Scope Check
    try:
        target_path = _normalize_target_path(file_path)
    except ValueError as exc:
        return f"Error: {exc}"

    if not _is_allowed_path(target_path):
        return f"Error: Permission denied. {file_path} is outside the allowed core scope."

    # 2. Syntax Validation
    try:
        ast.parse(new_code)
    except Exception as e:
        return f"Aborting: Proposed code has syntax errors: {e}"

    # 3. Directory Management
    live_target_path = _live_file_path(target_path)
    for folder in [config.RUNTIME_ROOT / "backups", config.RUNTIME_ROOT / "temp_core", config.KNOWLEDGE_DIR]:
        folder.mkdir(parents=True, exist_ok=True)

    # 4. Backup Operation
    backup_path = "N/A"
    original_content = ""
    if live_target_path.exists():
        original_content = live_target_path.read_text(encoding="utf-8")
        backup_file = _timestamped_backup_path(target_path)
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        backup_file.write_text(original_content, encoding="utf-8")
        backup_path = backup_file.as_posix()

    # 5. Staging Operation
    temp_path = _staged_file_path(target_path)
    metadata_path = _staged_metadata_path(target_path)
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.write_text(new_code, encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "target_path": target_path.as_posix(),
                "reasoning": reasoning,
                "staged_at": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
                "target_existed_at_stage": live_target_path.exists(),
                "base_content_sha256": _content_digest(original_content),
                "staged_content_sha256": _content_digest(new_code),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # 6. Self-Documentation
    mem_file = _memories_file_path()
    log_entry = f"- [EVOLVE] {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}: Staged update for {file_path}. Reason: {reasoning}\n"
    mem_file.parent.mkdir(parents=True, exist_ok=True)
    with mem_file.open('a', encoding='utf-8') as f:
        f.write(log_entry)

    return (f"Change successfully staged.\n"
            f"- File: {file_path}\n"
            f"- Temp: {temp_path.as_posix()}\n"
            f"- Backup: {backup_path}\n"
            f"Please verify the code in the temp folder.")

async def apply_core_change(file_path: str):
    """
    Moves staged code from temp_core/ to the live file path.
    """
    try:
        target_path = _normalize_target_path(file_path)
    except ValueError as exc:
        return f"Error: {exc}"

    live_target_path = _live_file_path(target_path)
    temp_path = _staged_file_path(target_path)
    metadata_path = _staged_metadata_path(target_path)
    if not temp_path.exists() or not metadata_path.exists():
        return f"Error: No staged changes found for {file_path}."

    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    if metadata.get("target_path") != target_path.as_posix():
        return f"Error: Staged metadata does not match {file_path}."

    # Read from staged
    staged_content = temp_path.read_text(encoding='utf-8')
    try:
        ast.parse(staged_content)
    except Exception as exc:
        return f"Error: Staged code for {file_path} no longer parses: {exc}"

    expected_stage_digest = metadata.get("staged_content_sha256")
    if expected_stage_digest and expected_stage_digest != _content_digest(staged_content):
        return f"Error: Staged code for {file_path} changed after staging. Re-stage the change before applying it."

    if "target_existed_at_stage" in metadata and "base_content_sha256" in metadata:
        current_exists = live_target_path.exists()
        if current_exists != bool(metadata.get("target_existed_at_stage")):
            return f"Error: Live file {file_path} changed since staging. Re-stage the change before applying it."

        current_content = live_target_path.read_text(encoding='utf-8') if current_exists else ""
        if _content_digest(current_content) != metadata.get("base_content_sha256"):
            return f"Error: Live file {file_path} changed since staging. Re-stage the change before applying it."
    
    # Overwrite live
    live_target_path.parent.mkdir(parents=True, exist_ok=True)
    live_target_path.write_text(staged_content, encoding='utf-8')

    temp_path.unlink(missing_ok=True)
    metadata_path.unlink(missing_ok=True)

    return f"Successfully applied staged changes to {file_path}."
