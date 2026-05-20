"""Runtime configuration for the shared CLI and hybrid web app."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
from typing import Any

from core.mcp_contracts import MCPServerSettings

try:
	from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency during bootstrap
	def load_dotenv(*args: Any, **kwargs: Any) -> bool:
		return False


PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _env_str(name: str, default: str) -> str:
	value = os.getenv(name)
	if value is None:
		return default
	stripped = value.strip()
	return stripped if stripped else default


def _env_bool(name: str, default: bool) -> bool:
	value = os.getenv(name)
	if value is None:
		return default
	normalized = value.strip().lower()
	if normalized in {"1", "true", "yes", "on"}:
		return True
	if normalized in {"0", "false", "no", "off"}:
		return False
	return default


def _env_int(name: str, default: int) -> int:
	value = os.getenv(name)
	if value is None:
		return default
	try:
		return int(value.strip())
	except ValueError:
		return default


def _env_float(name: str, default: float) -> float:
	value = os.getenv(name)
	if value is None:
		return default
	try:
		return float(value.strip())
	except ValueError:
		return default


def _env_path(name: str, default: Path) -> Path:
	value = os.getenv(name)
	if not value or not value.strip():
		return default
	candidate = Path(value.strip()).expanduser()
	return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def _env_optional_path(name: str, default: Path | None = None) -> Path | None:
	value = os.getenv(name)
	if value is None:
		return default
	stripped = value.strip()
	if not stripped:
		return None
	candidate = Path(stripped).expanduser()
	return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def _env_list(name: str, default: list[str]) -> list[str]:
	value = os.getenv(name)
	if value is None:
		return list(default)
	parts = [part.strip() for part in re.split(r"[;,]", value) if part.strip()]
	return parts if parts else list(default)


def _env_command(name: str, default: list[str]) -> list[str]:
	value = os.getenv(name)
	if value is None or not value.strip():
		return list(default)
	stripped = value.strip()
	try:
		parsed = json.loads(stripped)
	except json.JSONDecodeError:
		parsed = None
	if isinstance(parsed, list) and all(isinstance(item, str) for item in parsed):
		return list(parsed)
	return shlex.split(stripped, posix=False)


def _normalize_provider(value: str) -> str:
	normalized = value.strip().lower()
	if normalized in {"ollama", "openrouter", "llamacpp"}:
		return normalized
	return "ollama"


RUNTIME_ROOT = _env_path("RUNTIME_ROOT", PROJECT_ROOT)
DATA_DIR = _env_path("DATA_DIR", PROJECT_ROOT / "data")
RUNTIME_DATA_DIR = _env_path("RUNTIME_DATA_DIR", DATA_DIR)
KNOWLEDGE_DIR = _env_path("KNOWLEDGE_DIR", PROJECT_ROOT / "knowledge")
BRAIN_DIR = _env_path("BRAIN_DIR", KNOWLEDGE_DIR / "brain")
PERSONAS_DIR = _env_path("PERSONAS_DIR", BRAIN_DIR / "personas")
ENTITIES_DIR = _env_path("ENTITIES_DIR", BRAIN_DIR / "entities")
LOGS_DIR = _env_path("LOGS_DIR", PROJECT_ROOT / "logs")
SKILLS_DIR = _env_path("SKILLS_DIR", PROJECT_ROOT / "skills")
SEARCH_DIR = _env_path("SEARCH_DIR", PROJECT_ROOT)
MEMORIES_FILE = _env_path("MEMORIES_FILE", KNOWLEDGE_DIR / "memories.md")
TIMELINE_FILE = _env_path("TIMELINE_FILE", BRAIN_DIR / "timeline.log")
TRUTH_FILE = _env_path("TRUTH_FILE", BRAIN_DIR / "truth.md")
DB_PATH = _env_path("DB_PATH", DATA_DIR / "zephyr.db")
VECTOR_STORE_DIR = _env_path("VECTOR_STORE_DIR", DATA_DIR / "vector_store")
KEYWORD_INDEX_DIR = _env_path("KEYWORD_INDEX_DIR", DATA_DIR / "keyword_index")
SCENARIOS_FILE = _env_path("SCENARIOS_FILE", DATA_DIR / "scenarios.json")
EMBEDDING_MODEL_DIR = _env_path("EMBEDDING_MODEL_DIR", PROJECT_ROOT / "LLM" / "vector-models")
SESSION_ATTACHMENTS_DIR = _env_path("SESSION_ATTACHMENTS_DIR", PROJECT_ROOT / "temp_core" / "attachments")

LLM_PROVIDER = _normalize_provider(_env_str("LLM_PROVIDER", "ollama"))
OLLAMA_BASE_URL = _env_str("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = _env_str("OLLAMA_MODEL", "llama3.1:8b")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = _env_str("OPENROUTER_MODEL", "openai/gpt-oss-120b:free")
LLAMACPP_MODEL_PATH = _env_path(
	"LLAMACPP_MODEL_PATH",
	PROJECT_ROOT / "LLM" / "gemma-4" / "gemma-4-E4B-it-UD-Q8_K_XL.gguf",
)
LLAMACPP_MMPROJ_PATH = _env_optional_path(
	"LLAMACPP_MMPROJ_PATH",
	LLAMACPP_MODEL_PATH.parent / "mmproj-F32.gguf",
)
LLAMACPP_N_CTX = _env_int("LLAMACPP_N_CTX", 32768)
LLAMACPP_N_GPU_LAYERS = _env_int("LLAMACPP_N_GPU_LAYERS", -1)
LLAMACPP_CHAT_FORMAT = os.getenv("LLAMACPP_CHAT_FORMAT", "").strip()

EMBEDDING_MODEL_NAME = _env_str("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
MAX_CONTEXT_TOKENS = _env_int("MAX_CONTEXT_TOKENS", 4000)
CHUNK_WORDS = _env_int("CHUNK_WORDS", 220)
CHUNK_OVERLAP = _env_int("CHUNK_OVERLAP", 40)
INDEX_IGNORE_PATTERNS = tuple(
	_env_list(
		"INDEX_IGNORE_PATTERNS",
		[
			".git",
			"__pycache__",
			"node_modules",
			"venv",
			".venv",
			".pytest_cache",
			".mypy_cache",
			".ruff_cache",
			"vector_store",
			"keyword_index",
			"LLM",
			"logs",
			"backups",
			"temp_core",
		],
	)
)

SANDBOX_BACKEND = _env_str("SANDBOX_BACKEND", "auto").lower()
SANDBOX_DOCKER_IMAGE = _env_str("SANDBOX_DOCKER_IMAGE", "python:3.11-slim")

MCP_ENABLED = _env_bool("MCP_ENABLED", False)
EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED = _env_bool("EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED", False)
REQUIRE_CONFIRMATION = _env_bool("REQUIRE_CONFIRMATION", False)

CLAUDE_MEM_WORKER_HOST = _env_str("CLAUDE_MEM_WORKER_HOST", "127.0.0.1")
CLAUDE_MEM_WORKER_PORT = _env_int("CLAUDE_MEM_WORKER_PORT", 8765)
CLAUDE_MEM_WORKER_AUTOSTART = _env_bool("CLAUDE_MEM_WORKER_AUTOSTART", False)
CLAUDE_MEM_WORKER_START_COMMAND = _env_command("CLAUDE_MEM_WORKER_START_COMMAND", [])
CLAUDE_MEM_WORKER_START_CWD = _env_path("CLAUDE_MEM_WORKER_START_CWD", PROJECT_ROOT)
CLAUDE_MEM_WORKER_STARTUP_TIMEOUT = _env_float("CLAUDE_MEM_WORKER_STARTUP_TIMEOUT", 20.0)

PERSONA_PLACEHOLDER = "{{durable_facts}}"
AGENCY_ROLES = tuple(_env_list("AGENCY_ROLES", ["Supervisor", "Researcher", "Coder", "Reviewer"]))
SYSTEM_PROMPT = os.getenv(
	"SYSTEM_PROMPT",
	(
		"You are uZephyr, a local-first AI sidekick for this workspace. "
		"Be precise, prefer grounded repository facts over guesses, use tools when they materially improve accuracy, "
		"and state uncertainty plainly when information is missing."
	),
).strip()


for directory in (
	DATA_DIR,
	RUNTIME_DATA_DIR,
	KNOWLEDGE_DIR,
	BRAIN_DIR,
	PERSONAS_DIR,
	ENTITIES_DIR,
	LOGS_DIR,
	VECTOR_STORE_DIR,
	KEYWORD_INDEX_DIR,
	EMBEDDING_MODEL_DIR,
	SESSION_ATTACHMENTS_DIR,
	LLAMACPP_MODEL_PATH.parent,
):
	directory.mkdir(parents=True, exist_ok=True)


def _normalize_mcp_server_config(raw: dict[str, Any], *, index: int) -> MCPServerSettings | None:
	return MCPServerSettings.from_config(raw, index=index, project_root=PROJECT_ROOT)


def get_mcp_server_configs() -> list[MCPServerSettings]:
	raw_json = os.getenv("MCP_SERVERS_JSON", "").strip()
	configs: list[MCPServerSettings] = []

	if raw_json:
		try:
			parsed = json.loads(raw_json)
		except json.JSONDecodeError:
			parsed = []
		if isinstance(parsed, list):
			for index, item in enumerate(parsed, start=1):
				if not isinstance(item, dict):
					continue
				normalized = _normalize_mcp_server_config(item, index=index)
				if normalized is not None:
					configs.append(normalized)

	single_command = os.getenv("MCP_SERVER_COMMAND", "").strip()
	if single_command:
		normalized = _normalize_mcp_server_config(
			{
				"name": os.getenv("MCP_SERVER_NAME", "archive"),
				"command": single_command,
				"args": os.getenv("MCP_SERVER_ARGS", ""),
				"env": os.getenv("MCP_SERVER_ENV", "") or os.getenv("MCP_SERVER_ENV_JSON", ""),
				"cwd": os.getenv("MCP_SERVER_CWD", ""),
				"tool_prefix": os.getenv("MCP_TOOL_PREFIX", "mcp"),
				"connect_timeout_seconds": os.getenv("MCP_SERVER_CONNECT_TIMEOUT_SECONDS", ""),
				"discovery_timeout_seconds": os.getenv("MCP_SERVER_DISCOVERY_TIMEOUT_SECONDS", ""),
				"tool_timeout_seconds": os.getenv("MCP_SERVER_TOOL_TIMEOUT_SECONDS", ""),
				"max_retries": os.getenv("MCP_SERVER_MAX_RETRIES", ""),
				"retry_backoff_seconds": os.getenv("MCP_SERVER_RETRY_BACKOFF_SECONDS", ""),
			},
			index=len(configs) + 1,
		)
		if normalized is not None:
			configs.append(normalized)

	indexed_server_keys = sorted(
		{
			int(match.group(1))
			for key in os.environ
			for match in [re.fullmatch(r"MCP_SERVER_(\d+)_COMMAND", key)]
			if match is not None
		}
	)
	for server_index in indexed_server_keys:
		prefix = f"MCP_SERVER_{server_index}_"
		normalized = _normalize_mcp_server_config(
			{
				"name": os.getenv(f"{prefix}NAME", f"server-{server_index}"),
				"command": os.getenv(f"{prefix}COMMAND", ""),
				"args": os.getenv(f"{prefix}ARGS", ""),
				"env": os.getenv(f"{prefix}ENV", "") or os.getenv(f"{prefix}ENV_JSON", ""),
				"cwd": os.getenv(f"{prefix}CWD", ""),
				"tool_prefix": os.getenv(f"{prefix}TOOL_PREFIX", "mcp"),
					"connect_timeout_seconds": os.getenv(f"{prefix}CONNECT_TIMEOUT_SECONDS", ""),
					"discovery_timeout_seconds": os.getenv(f"{prefix}DISCOVERY_TIMEOUT_SECONDS", ""),
					"tool_timeout_seconds": os.getenv(f"{prefix}TOOL_TIMEOUT_SECONDS", ""),
					"max_retries": os.getenv(f"{prefix}MAX_RETRIES", ""),
					"retry_backoff_seconds": os.getenv(f"{prefix}RETRY_BACKOFF_SECONDS", ""),
			},
			index=len(configs) + 1,
		)
		if normalized is not None:
			configs.append(normalized)

	return configs


def get_persona_prompt(role: str, durable_facts: str = "") -> str:
	normalized_role = role.strip()
	persona_path = PERSONAS_DIR / f"{normalized_role}.md"
	if persona_path.is_file():
		template = persona_path.read_text(encoding="utf-8")
	else:
		template = (
			f"## Instructions\n"
			f"You are the {normalized_role.upper()} agent.\n\n"
			f"## Durable Facts about the User\n"
			f"{PERSONA_PLACEHOLDER}"
		)

	return template.replace(PERSONA_PLACEHOLDER, durable_facts.strip())