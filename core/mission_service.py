"""Shared mission orchestration for multi-agent tasks."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable

from rich.console import Console

from core.app_runtime import AppRuntime
from core.blackboard import Blackboard


class MissionService:
    """Coordinates Agency execution and mission persistence."""

    def __init__(self, runtime: AppRuntime, console: Console) -> None:
        self.runtime = runtime
        self.console = console

    async def run_turn(
        self,
        session_id: str,
        user_task: str,
        *,
        allow_sensitive_tools: bool | None = None,
    ) -> str:
        """Run one persisted mission turn for the active session."""
        await self.runtime.memory.add_message(session_id, "user", f"/mission {user_task}")
        response = await self.run_mission(user_task, allow_sensitive_tools=allow_sensitive_tools)
        if response.strip():
            await self.runtime.memory.add_message(session_id, "assistant", response)
        return response

    async def stream_turn(
        self,
        session_id: str,
        user_task: str,
        *,
        allow_sensitive_tools: bool | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream mission progress snapshots and persist the final response."""
        await self.runtime.memory.add_message(session_id, "user", f"/mission {user_task}")

        queue: asyncio.Queue[str | None] = asyncio.Queue()
        last_snapshot = ""

        async def publish(board: Blackboard, status: str, round_num: int) -> None:
            nonlocal last_snapshot

            snapshot = self._format_progress_snapshot(
                board,
                status,
                round_num,
                latest_mcp_execution_summary=self._latest_mcp_execution_summary(),
            )
            if snapshot == last_snapshot:
                return

            last_snapshot = snapshot
            await queue.put(snapshot)

        async def runner() -> None:
            try:
                response = await self.run_mission(
                    user_task,
                    on_progress=publish,
                    allow_sensitive_tools=allow_sensitive_tools,
                )
                if response.strip():
                    await self.runtime.memory.add_message(session_id, "assistant", response)
                    if response != last_snapshot:
                        await queue.put(response)
            finally:
                await queue.put(None)

        task = asyncio.create_task(runner())

        try:
            while True:
                snapshot = await queue.get()
                if snapshot is None:
                    break
                yield snapshot
        finally:
            try:
                await task
            except asyncio.CancelledError:
                raise

    async def run_mission(
        self,
        user_task: str,
        *,
        on_progress: Callable[[Blackboard, str, int], Awaitable[None] | None] | None = None,
        allow_sensitive_tools: bool | None = None,
    ) -> str:
        """Run one agency mission without mutating chat history."""
        from core.orchestrator import Agency

        agency = Agency(self.runtime.require_llm(), self.runtime.memory, self.console)
        return await agency.run_mission(
            user_task,
            on_progress=on_progress,
            allow_sensitive_tools=allow_sensitive_tools,
        )

    @staticmethod
    def _format_progress_snapshot(
        board: Blackboard,
        status: str,
        round_num: int,
        *,
        latest_mcp_execution_summary: str | None = None,
    ) -> str:
        recent_milestones = board.milestones[-4:] if board.milestones else ["Mission started."]
        turn_counts = ", ".join(
            f"{agent}: {count}" for agent, count in sorted(board.agent_turn_counts.items())
        ) or "No turns recorded yet."

        if board.review_passed():
            review_status = "PASS"
        elif board.latest_code_needs_review():
            review_status = "Awaiting reviewer verification"
        elif board.review_rejected():
            review_status = "Reviewer requested changes"
        else:
            review_status = "No review completed yet"

        if not board.current_code:
            sandbox_status = "No code proposed yet"
        elif board.latest_code_has_passing_sandbox():
            sandbox_status = "Latest code passed sandbox verification"
        elif board.code_version != board.sandboxed_code_version:
            sandbox_status = "Latest code has not been sandbox-verified yet"
        else:
            sandbox_status = "Latest code failed sandbox verification"

        lines = [
            "Mission in progress",
            f"Goal: {board.goal}",
            f"Status: {status}",
            f"Round: {round_num}",
            f"Current agent: {board.current_agent}",
            f"Agent turns: {turn_counts}",
            f"Findings: {len(board.findings)} | Requests: {len(board.requests)} | Code revisions: {board.code_version}",
            f"Sandbox: {sandbox_status}",
            f"Review: {review_status}",
        ]
        if latest_mcp_execution_summary:
            lines.append(f"MCP: {latest_mcp_execution_summary}")
        lines.append("Recent milestones:")
        lines.extend(f"- {milestone}" for milestone in recent_milestones)
        return "\n".join(lines)

    def _latest_mcp_execution_summary(self) -> str | None:
        tool_engine = self.runtime.tool_engine
        if tool_engine is None:
            return None

        getter = getattr(tool_engine, "get_recent_tool_executions", None)
        if not callable(getter):
            return None

        recent = getter(source="mcp", limit=1)
        if not recent:
            return None
        return recent[0].summary(max_length=120)