#!/usr/bin/env python3
"""μZephyr (Zephyr Micro) — main entry-point & interactive CLI loop."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import logging
import os
import signal
import uuid

# ── SHUT UP NOISY THIRD-PARTY LIBRARIES ──────────────────────────────────────
# This must happen BEFORE importing models to kill the progress bars and verbose logs
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.logging import RichHandler
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

import config
from core.app_runtime import AppRuntime
from core.chat_service import ChatService
from core.cli_commands import CLICommandHandler
from core.mission_service import MissionService
from core.startup_guidance import format_startup_guidance_lines, get_startup_guidance

# ── Theme & Console ──────────────────────────────────────────────────────────
_THEME = Theme({
    "info": "dim cyan",
    "warning": "bold yellow",
    "error": "bold red",
    "zephyr": "bold magenta",
})
console = Console(theme=_THEME)

BANNER = r"""
[bold magenta]         ╔═╗┌─┐┌─┐┬ ┬┬ ┬┬─┐  ╔╦╗┬┌─┐┬─┐┌─┐[/]
[bold magenta]         ╔═╝├┤ ├─┘├─┤└┬┘├┬┘  ║║║││  ├┬┘│ │[/]
[bold magenta]         ╚═╝└─┘┴  ┴ ┴ ┴ ┴└─  ╩ ╩┴└─┘┴└─└─┘[/]
[dim]         Local-first AI sidekick  •  v0.1.0[/]
[dim]         Type [bold]/help[/bold] for commands  •  [bold]/quit[/bold] to exit[/]
"""


class ZephyrCLI:
    """Interactive CLI powering the μZephyr experience."""

    def __init__(self) -> None:
        self.console = console
        self.session_id: str = uuid.uuid4().hex[:12]
        self.runtime = AppRuntime(console=self.console)
        self.chat_service = ChatService(self.runtime)
        self.mission_service = MissionService(self.runtime, self.console)
        self.command_handler = CLICommandHandler(
            console=self.console,
            runtime=self.runtime,
            set_session_id=self._set_session_id,
            run_eval_mission=self._run_eval_mission,
        )
        self.prompt_session: PromptSession[str] = PromptSession(
            history=FileHistory(str(config.LOGS_DIR / ".prompt_history")),
        )
        self._running = True

    # ── Bootstrap ─────────────────────────────────────────────────────────
    async def _init_subsystems(self) -> None:
        """Initialise memory, LLM router, tool engine, and search indexer."""
        await self.runtime.initialize()

    def _model_display_name(self) -> str:
        if config.LLM_PROVIDER == "ollama":
            return config.OLLAMA_MODEL
        if config.LLM_PROVIDER == "openrouter":
            return config.OPENROUTER_MODEL
        if config.LLM_PROVIDER == "llamacpp":
            return config.LLAMACPP_MODEL_PATH.name
        return "unknown"

    def _tool_source_counts(self) -> Counter[str]:
        if self.runtime.tool_engine is None:
            return Counter()
        return Counter(tool.source for tool in self.runtime.tool_engine.list_tools())

    def _print_dashboard(self) -> None:
        counts = self._tool_source_counts()
        startup_guidance = get_startup_guidance()

        info_table = Table(box=None, show_header=False, pad_edge=False)
        info_table.add_row("[magenta]Session[/]", self.session_id)
        info_table.add_row("[magenta]Provider[/]", config.LLM_PROVIDER)
        info_table.add_row("[magenta]Model[/]", self._model_display_name())
        info_table.add_row(
            "[magenta]Archive[/]",
            "[green]Connected[/]" if self.runtime.memory.archive else "[red]Offline[/]",
        )
        info_table.add_row("[magenta]Search[/]", self.runtime.search_status)

        stats_table = Table(box=None, show_header=False, pad_edge=False)
        stats_table.add_row("[magenta]Total tools[/]", str(sum(counts.values())))
        stats_table.add_row("[magenta]Skill tools[/]", str(counts.get("local", 0)))
        stats_table.add_row("[magenta]Built-ins[/]", str(counts.get("builtin", 0)))
        stats_table.add_row("[magenta]MCP tools[/]", str(counts.get("mcp", 0)))

        cmd_table = Table(box=None, show_header=False, pad_edge=False)
        cmd_table.add_row("[bold cyan]/mission <task>[/]", "Start a multi-agent task")
        cmd_table.add_row("[bold cyan]/skills[/]", "List tools by source and tags")
        cmd_table.add_row("[bold cyan]/memory[/]", "Show durable facts")
        cmd_table.add_row("[bold cyan]/mcp[/]", "Inspect MCP connections")
        cmd_table.add_row("[bold cyan]/prepare[/]", "Prepare sandbox image and local model assets")
        cmd_table.add_row("[bold cyan]/reload[/]", "Refresh skills and search index")
        cmd_table.add_row("[bold cyan]/session[/]", "Start a new session id")
        cmd_table.add_row("[bold cyan]/help[/]", "Show all slash commands")
        cmd_table.add_row("[bold cyan]/quit[/]", "Exit the CLI")

        self.console.print(Panel(
            Columns([info_table, stats_table, cmd_table], expand=True),
            title="[bold white]Control Center[/]",
            border_style="magenta",
            padding=(0, 1),
        ))
        if startup_guidance.actions:
            self.console.print(Panel(
                "\n".join(format_startup_guidance_lines(startup_guidance)),
                title="[bold yellow]Startup Guidance[/]",
                border_style="yellow",
                padding=(0, 1),
            ))

    # ── Graceful shutdown ─────────────────────────────────────────────────
    async def _shutdown(self) -> None:
        await self.runtime.shutdown()
        self.console.print("\n[zephyr]μZephyr signing off. Goodbye! 👋[/zephyr]")

    def _set_session_id(self, session_id: str) -> None:
        self.session_id = session_id

    async def _run_eval_mission(self, user_task: str) -> str:
        """Run one deterministic mission eval using the standard Agency path."""
        return await self.mission_service.run_mission(user_task)

    # ── Main conversation turn ────────────────────────────────────────────
    async def _chat_turn(self, user_input: str) -> None:
        """Send user input through the full pipeline and display response."""
        # Inference + tool loop with streaming
        self.console.print()
        with Live(Text("Thinking…", style="dim"), console=self.console, refresh_per_second=12, transient=True) as live:
            full_response = await self.chat_service.run_turn(
                self.session_id,
                user_input,
                console=self.console,
                live=live,
            )

        # Render final answer as Markdown
        if full_response.strip():
            self.console.print(Panel(
                Markdown(full_response),
                title="[zephyr]μZephyr[/zephyr]",
                border_style="magenta",
                padding=(0, 1),
            ))

    # ── Multi-Agent Mission Turn ──────────────────────────────────────────
    async def _mission_turn(self, user_task: str) -> None:
        """Hand the task over to the Multi-Agent Orchestrator."""
        full_response = await self.mission_service.run_turn(self.session_id, user_task)

        # Render final, review-approved answer as Markdown
        if full_response.strip():
            self.console.print(Panel(
                Markdown(full_response),
                title="[zephyr]μZephyr Agency[/zephyr]",
                border_style="magenta",
                padding=(0, 1),
            ))

    # ── Run loop ──────────────────────────────────────────────────────────
    async def run(self) -> None:
        """Top-level entry: banner → init → REPL."""
        self.console.print(BANNER)

        with self.console.status("[bold cyan]Initialising subsystems…[/]"):
            await self._init_subsystems()

        self._print_dashboard()
        self.console.print()

        while self._running:
            try:
                # Use native prompt_async instead of a background thread
                try:
                    user_input: str = await self.prompt_session.prompt_async("  ❯ ")
                except Exception as e:
                    # Fallback for IDE terminals (PyCharm/VS Code) that lack native Windows buffers
                    if "NoConsoleScreenBufferError" in type(e).__name__ or "Output is not a terminal" in str(e):
                        user_input = await asyncio.get_event_loop().run_in_executor(None, input, "  ❯ ")
                    else:
                        raise
                        
            except (EOFError, KeyboardInterrupt):
                self._running = False
                break

            text = user_input.strip()
            if not text:
                continue

            if text.startswith("/"):
                if text.lower().startswith("/mission "):
                    task = text[9:].strip()
                    try:
                        await self._mission_turn(task)
                    except Exception as exc:
                        self.console.print(f"[error]Error during mission: {exc}[/error]")
                    continue

                outcome = await self.command_handler.handle(text)
                if outcome.should_exit:
                    self._running = False
                    continue
                if outcome.handled:
                    continue

            try:
                await self._chat_turn(text)
            except Exception as exc:
                self.console.print(f"[error]Error during turn: {exc}[/error]")

        await self._shutdown()


# ── Entry-point ──────────────────────────────────────────────────────────────
def _setup_logging() -> None:
    """Configure root logger to write to both Rich console and a log file."""
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(config.LOGS_DIR / "uzephyr.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s  %(name)-28s  %(levelname)-7s  %(message)s"))

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[
            RichHandler(console=console, show_path=False, show_time=False, rich_tracebacks=True, markup=True),
            file_handler,
        ],
    )

    # Silence noisy third-party loggers so they don't print to the CLI
    noisy_loggers = [
        "httpx",
        "httpcore",
        "chromadb.telemetry.product.posthog",
        "chromadb",
        "sentence_transformers.SentenceTransformer",
        "huggingface_hub.utils._http",
        "transformers",
        "urllib3",
        "duckduckgo_search"
    ]
    for logger_name in noisy_loggers:
        # Set to WARNING. You will still see things like PDF parse warnings
        # but the wall of HTTP Request INFO logs will disappear.
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def main() -> None:
    _setup_logging()
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    cli = ZephyrCLI()
    try:
        asyncio.run(cli.run())
    except KeyboardInterrupt:
        console.print("\n[zephyr]Interrupted – exiting.[/zephyr]")


if __name__ == "__main__":
    main()