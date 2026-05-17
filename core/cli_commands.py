"""Slash-command handlers for the interactive μZephyr CLI."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import uuid

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import config
from core.app_runtime import AppRuntime
from core.embedding_model import describe_embedding_model_preparation, prepare_embedding_model
from core.evals import run_eval_scenarios, summarize_eval_results
from core.llm import (
    describe_inference_runtime_preparation,
    describe_llamacpp_preparation,
    prepare_llamacpp_runtime,
)
from core.startup_guidance import format_startup_guidance_lines, get_startup_guidance
from core.truth_synthesis import describe_truth_synthesis_health
from skills.skill_loader import SkillLoader
from skills.sandbox.scripts.sandbox import (
    describe_sandbox_preparation,
    describe_sandbox_readiness,
    prepare_sandbox_backend,
)


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Outcome of handling a single slash-command."""

    handled: bool
    should_exit: bool = False


class CLICommandHandler:
    """Owns slash-command behavior for the terminal interface."""

    def __init__(
        self,
        *,
        console: Console,
        runtime: AppRuntime,
        set_session_id: Callable[[str], None],
        run_eval_mission: Callable[[str], Awaitable[str]],
    ) -> None:
        self.console = console
        self.runtime = runtime
        self.set_session_id = set_session_id
        self.run_eval_mission = run_eval_mission

    async def handle(self, text: str) -> CommandResult:
        """Execute one slash-command if it is supported."""
        cmd = text.strip().lower()

        if cmd in {"/quit", "/exit", "/q"}:
            return CommandResult(handled=True, should_exit=True)
        if cmd == "/reload":
            await self._reload()
            return CommandResult(handled=True)
        if cmd in {"/prepare", "/prepare-sandbox"}:
            await self._prepare_runtime()
            return CommandResult(handled=True)
        if cmd == "/skills":
            self._print_skills()
            return CommandResult(handled=True)
        if cmd == "/help":
            self._print_help()
            return CommandResult(handled=True)
        if cmd == "/mcp":
            self._print_mcp_status()
            return CommandResult(handled=True)
        if cmd in {"/mcp refresh", "/mcp-refresh"}:
            await self._refresh_mcp_discovery()
            return CommandResult(handled=True)
        if cmd == "/session":
            self._start_new_session()
            return CommandResult(handled=True)
        if cmd == "/memory":
            await self._print_memory()
            return CommandResult(handled=True)
        if cmd == "/verify":
            await self._verify_runtime()
            return CommandResult(handled=True)

        return CommandResult(handled=False)

    async def _reload(self) -> None:
        if self.runtime.tool_engine is not None:
            await self.runtime.reload_skills()
            self.console.print("[info]Skills reloaded.[/]")
        if self.runtime.indexer is not None:
            try:
                count = await self.runtime.refresh_search_index(wait_for_completion=True)
                self.console.print(f"[info]Search index refreshed ({count} file(s) updated).[/]")
            except Exception as exc:
                self.console.print(f"[warning]Re-index failed: {exc}[/]")

    async def _prepare_runtime(self) -> None:
        sandbox_preparation = await prepare_sandbox_backend()
        lines = describe_sandbox_preparation(sandbox_preparation)
        embedding_preparation = await prepare_embedding_model()
        lines.append("")
        lines.extend(describe_embedding_model_preparation(embedding_preparation))
        if config.LLM_PROVIDER == "llamacpp":
            llamacpp_preparation = await prepare_llamacpp_runtime()
            lines.append("")
            lines.extend(describe_llamacpp_preparation(llamacpp_preparation))
            success = sandbox_preparation.success and embedding_preparation.success and llamacpp_preparation.success
        else:
            success = sandbox_preparation.success and embedding_preparation.success

        inference_preparation = await self.runtime.prepare_inference_runtime()
        lines.append("")
        lines.extend(describe_inference_runtime_preparation(inference_preparation))
        success = success and inference_preparation.success

        await self.runtime.prepare_search_runtime()
        lines.append("")
        lines.append(f"Search runtime status: {self.runtime.search_status}.")

        self.console.print(Panel(
            "\n".join(lines),
            title="[bold]Runtime Preparation[/]",
            border_style="cyan" if success else "yellow",
        ))

    def _print_help(self) -> None:
        table = Table(title="[bold cyan]Slash Commands[/]", box=None, pad_edge=False)
        table.add_column("Command", style="bold cyan", no_wrap=True)
        table.add_column("Description")
        table.add_row("/mission <task>", "Run the multi-agent agency loop")
        table.add_row("/skills", "Show loaded tools grouped by source")
        table.add_row("/memory", "Show durable memory facts")
        table.add_row("/mcp", "Show MCP server status and discovered tools")
        table.add_row("/mcp refresh", "Refresh MCP discovery and reuse cached inventory on transient failures")
        table.add_row("/prepare", "Prepare sandbox image and local model assets")
        table.add_row("/session", "Create a fresh session id")
        table.add_row("/reload", "Reload skills and refresh the search index")
        table.add_row("/help", "Show this command reference")
        table.add_row("/quit | /exit | /q", "Exit the CLI")
        self.console.print(table)

    def _print_skills(self) -> None:
        if self.runtime.tool_engine is None:
            self.console.print("[warning]Tool engine is not initialised.[/]")
            return

        source_order = {"local": 0, "builtin": 1, "mcp": 2, "manual": 3}
        tools = sorted(
            self.runtime.tool_engine.list_tools(),
            key=lambda tool: (source_order.get(tool.source, 99), tool.source, tool.name.lower()),
        )

        if not tools:
            self.console.print(Panel(
                "[dim]No tools loaded.[/]",
                title="[bold]Available Tools & Skills[/]",
                border_style="cyan",
            ))
            return

        table = Table(title="[bold magenta]Available Tools & Skills[/]", box=None, pad_edge=False)
        table.add_column("Tool Name", style="cyan", no_wrap=True)
        table.add_column("Source", style="magenta", no_wrap=True)
        table.add_column("Tags", style="green")

        current_source: str | None = None
        for tool in tools:
            if current_source is not None and tool.source != current_source:
                table.add_section()
            current_source = tool.source
            table.add_row(
                tool.name,
                self._source_label(tool.source),
                ", ".join(tool.tags) if tool.tags else "general",
            )

        self.console.print(table)

    def _print_mcp_status(self) -> None:
        if self.runtime.tool_engine is None:
            self.console.print("[warning]Tool engine is not initialised.[/]")
            return

        statuses = self.runtime.tool_engine.get_mcp_server_statuses()
        if not statuses:
            if not config.MCP_ENABLED:
                detail = "[dim]MCP is disabled. Set MCP_ENABLED=true and configure MCP_SERVERS in .env to enable server tools.[/]"
            elif not config.EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED:
                detail = (
                    "[dim]MCP server tools are disabled in this runtime because external subprocess integrations are off. "
                    "This is the packaged-mode default. Re-enable with EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED=true "
                    "only after confirming the required external tools are installed.[/]"
                )
            else:
                detail = "[dim]No MCP servers configured. Set MCP_ENABLED=true and MCP_SERVERS in .env.[/]"
            self.console.print(Panel(
                detail,
                title="[bold]MCP Servers[/]",
                border_style="cyan",
            ))
            return

        lines: list[str] = []
        for status in statuses:
            state = str(status.state)
            if status.last_error_kind:
                state = f"{state} ({status.last_error_kind})"
            lines.append(f"• {status.name} [{state}]")
            lines.append(f"  prefix: {status.tool_prefix}")
            lines.append(f"  command: {status.command} {' '.join(status.args)}".rstrip())
            lines.append(
                "  cached tools: " + (", ".join(status.discovered_tools) if status.discovered_tools else "none discovered yet")
            )
            lines.append(f"  last connected: {status.last_successful_connection_at or 'never'}")
            lines.append(f"  last discovered: {status.last_discovered_at or 'never'}")
            lines.append(
                "  inventory: "
                + (
                    "cached from the last successful discovery refresh"
                    if status.last_discovered_at
                    else "awaiting first successful discovery refresh"
                )
            )
            if status.degraded_reason:
                lines.append(f"  degraded reason: {status.degraded_reason}")
            if status.last_error:
                lines.append(f"  error: {status.last_error}")

        self.console.print(Panel(
            "\n".join(lines),
            title="[bold]MCP Servers[/]",
            border_style="cyan",
        ))

    async def _refresh_mcp_discovery(self) -> None:
        if self.runtime.tool_engine is None:
            self.console.print("[warning]Tool engine is not initialised.[/]")
            return

        await self.runtime.tool_engine.refresh_mcp_tools()
        self.console.print("[info]MCP discovery refreshed. Showing cached inventory from the latest successful refresh.[/]")
        self._print_mcp_status()

    def _start_new_session(self) -> None:
        session_id = uuid.uuid4().hex[:12]
        self.set_session_id(session_id)
        self.console.print(f"[info]New session started: {session_id}[/]")

    async def _print_memory(self) -> None:
        facts = await self.runtime.memory.get_durable_facts()
        self.console.print(Panel(
            facts or "[dim]No durable facts stored yet.[/]",
            title="[bold]Durable Memory[/]",
            border_style="cyan",
        ))

    async def _verify_runtime(self) -> None:
        if self.runtime.tool_engine is None:
            self.console.print("[warning]Tool engine is not initialised.[/]")
            return

        tool_engine = self.runtime.tool_engine
        if tool_engine.skill_loader is None:
            tool_engine.skill_loader = SkillLoader(tool_engine)

        results = await tool_engine.skill_loader.verify_skill_integrity(auto_repair=True)
        verify_lines = [
            f"Valid: {len(results['valid'])}",
            f"Repaired: {results['repaired']}",
            f"Broken: {results['broken']}",
        ]
        verify_lines.append("")
        verify_lines.extend(describe_sandbox_readiness())
        verify_lines.append("")
        verify_lines.extend(self._describe_truth_synthesis_health())

        startup_guidance = get_startup_guidance()
        if startup_guidance.actions:
            verify_lines.append("")
            verify_lines.extend(format_startup_guidance_lines(startup_guidance))

        if self.runtime.llm is None:
            verify_lines.append("")
            verify_lines.append("Mission evals: skipped (LLM runtime is not initialised).")
        else:
            eval_results = await run_eval_scenarios(self.run_eval_mission, tool_engine)
            verify_lines.append("")
            verify_lines.append(summarize_eval_results(eval_results))

        self.console.print(Panel("\n".join(verify_lines), title="Skill Integrity Check"))

    @staticmethod
    def _source_label(source: str) -> str:
        labels = {
            "builtin": "Built-in",
            "local": "Skill",
            "manual": "Manual",
            "mcp": "MCP",
        }
        return labels.get(source, source.replace("_", " ").title())

    @staticmethod
    def _describe_truth_synthesis_health() -> list[str]:
        try:
            return list(describe_truth_synthesis_health())
        except Exception as exc:
            return [
                "Truth synthesis health: unavailable",
                f"Truth detail: probe failed with {type(exc).__name__}: {exc}",
            ]