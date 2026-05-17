"""The Agency — Multi-Agent Orchestration for complex tasks."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import re
import uuid

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

import config
from core.blackboard import Blackboard, review_feedback_passes


_MAX_MISSION_ROUNDS = 12
_AGENT_PANEL_TITLES = {
    "Supervisor": "🧭 Supervisor Decision",
    "Researcher": "🔍 Research Brief",
    "Coder": "🛠 Coder Output",
    "Reviewer": "🧪 Reviewer Verdict",
}
_AGENT_PANEL_STYLES = {
    "Supervisor": "cyan",
    "Researcher": "green",
    "Coder": "yellow",
    "Reviewer": "magenta",
}
_AGENT_STATUS_TEXT = {
    "Supervisor": "Planning next step...",
    "Researcher": "Gathering intelligence...",
    "Coder": "Building...",
    "Reviewer": "Reviewing...",
}
_AGENT_USER_MESSAGES = {
    "Supervisor": (
        "Analyze the mission board and choose exactly one next agent: Researcher, "
        "Coder, Reviewer, or END. Output only the agent name."
    ),
    "Researcher": (
        "Review the mission board, gather the missing facts, and post structured findings "
        "or requests to the board."
    ),
    "Coder": (
        "Use the findings and reviewer feedback on the mission board to produce the next "
        "full code proposal in a markdown code block. Include comprehensive docstrings and "
        "error handling for any I/O or network paths. Before finalizing, use run_test_in_sandbox "
        "when available and post the verification result to the mission board."
    ),
    "Reviewer": (
        "Review the latest code proposal on the mission board. REJECT is the default. "
        "Only reply PASS when all required checks pass, and use this exact checklist format: "
        "PASS or REJECT, then '- Docstrings: PASS/REJECT', '- Error Handling: PASS/REJECT', "
        "'- Sandbox: PASS/REJECT', and '- Notes: <concise explanation>'. Reject if sandbox "
        "verification is missing or failed."
    ),
}

class Agency:
    def __init__(self, llm_router, memory, console: Console):
        self.llm = llm_router
        self.memory = memory
        self.console = console

    async def run_mission(
        self,
        user_task: str,
        *,
        on_progress: Callable[[Blackboard, str, int], Awaitable[None] | None] | None = None,
        allow_sensitive_tools: bool | None = None,
    ) -> str:
        board = Blackboard(mission_id=uuid.uuid4().hex[:8], goal=user_task)
        board.add_milestone("Mission created.")
        if self._mission_requires_skill(user_task):
            board.add_finding("requested_artifact", "uZephyr skill package")
            board.add_milestone("Mission explicitly requests a uZephyr skill artifact.")

        await self._emit_progress(on_progress, board, "Mission created.", 0)

        self.console.print(Panel(f"[bold white]{user_task}[/]", title="🎯 Agency Mission Started", border_style="blue"))

        durable_facts = await self.memory.get_durable_facts()

        registered_tools = self._register_board_tools(board)
        current_agent = "Supervisor"

        try:
            for round_num in range(1, _MAX_MISSION_ROUNDS + 1):
                board.record_turn(current_agent)
                prior_code_version = board.code_version
                await self._emit_progress(
                    on_progress,
                    board,
                    f"Round {round_num}: {current_agent} started.",
                    round_num,
                )
                self.console.print(
                    f"\n[bold blue]─── Round {round_num} | Agent: {current_agent} ───[/]"
                )
                response = await self._run_agent_turn(
                    current_agent,
                    durable_facts,
                    board,
                    allow_sensitive_tools=allow_sensitive_tools,
                )

                if current_agent == "Supervisor":
                    next_agent = self._resolve_next_agent(response, board)
                    if next_agent == "END":
                        board.add_milestone("Supervisor ended the mission.")
                        await self._emit_progress(on_progress, board, "Supervisor ended the mission.", round_num)
                        break

                    board.add_milestone(f"Supervisor routed the mission to {next_agent}.")
                    await self._emit_progress(
                        on_progress,
                        board,
                        f"Supervisor routed the mission to {next_agent}.",
                        round_num,
                    )
                    current_agent = next_agent
                    continue

                self._update_board_from_response(current_agent, response, board, prior_code_version)
                await self._emit_progress(
                    on_progress,
                    board,
                    board.milestones[-1] if board.milestones else f"{current_agent} completed a mission step.",
                    round_num,
                )

                if current_agent == "Coder":
                    await self._verify_latest_code_in_sandbox(board, prior_code_version)
                    await self._emit_progress(
                        on_progress,
                        board,
                        board.milestones[-1] if board.milestones else "Sandbox verification finished.",
                        round_num,
                    )

                if current_agent == "Reviewer" and board.review_passed():
                    self.console.print(Panel("✅ [bold green]Reviewer Approved![/]", border_style="green"))
                    await self._emit_progress(on_progress, board, "Reviewer approved the mission.", round_num)
                    return self._format_final_result(board)

                current_agent = "Supervisor"
        finally:
            for tool_name in registered_tools:
                self.llm.tool_engine.unregister(tool_name)

        return self._format_final_result(board)

    @staticmethod
    async def _emit_progress(
        on_progress: Callable[[Blackboard, str, int], Awaitable[None] | None] | None,
        board: Blackboard,
        status: str,
        round_num: int,
    ) -> None:
        if on_progress is None:
            return

        maybe_awaitable = on_progress(board, status, round_num)
        if maybe_awaitable is not None:
            await maybe_awaitable

    async def _run_agent_turn(
        self,
        agent: str,
        durable_facts: str,
        board: Blackboard,
        *,
        allow_sensitive_tools: bool | None = None,
    ) -> str:
        board.current_agent = agent
        system_prompt = f"{config.get_persona_prompt(agent, durable_facts).rstrip()}\n\n{board.render_for_llm()}"
        allowed_tags = [agent.lower(), "universal"]
        user_message = self._build_agent_user_message(agent, board)

        with Live(Text(_AGENT_STATUS_TEXT[agent], style="dim"), console=self.console, transient=True) as live:
            response = await self.llm.chat(
                system_prompt=system_prompt,
                history=[],
                user_message=user_message,
                console=self.console,
                live=live,
                allowed_tags=allowed_tags,
                allow_sensitive_tools=allow_sensitive_tools,
            )

        self.console.print(
            Panel(
                Markdown(response or "No response."),
                title=_AGENT_PANEL_TITLES[agent],
                border_style=_AGENT_PANEL_STYLES[agent],
            )
        )
        return response

    async def _verify_latest_code_in_sandbox(self, board: Blackboard, prior_code_version: int) -> None:
        if board.code_version <= prior_code_version or not board.current_code:
            return

        if "run_test_in_sandbox" not in self.llm.tool_engine.list_tool_names():
            board.set_sandbox_feedback(
                "Sandbox verification unavailable: tool 'run_test_in_sandbox' is not registered."
            )
            board.add_milestone("Sandbox verification could not run because run_test_in_sandbox is unavailable.")
            return

        sandbox_feedback = await self.llm.tool_engine.execute(
            "run_test_in_sandbox",
            {"code": board.current_code},
            allowed_tags=["coder", "universal"],
            console=self.console,
        )
        board.set_sandbox_feedback(sandbox_feedback)
        if board.latest_code_has_passing_sandbox():
            board.add_milestone("Sandbox verification passed for the latest code proposal.")
        else:
            board.add_milestone("Sandbox verification failed for the latest code proposal.")

    def _register_board_tools(self, board: Blackboard) -> list[str]:
        def sync_code_if_needed(text: str) -> None:
            if board.current_agent != "Coder":
                return

            candidate = self._extract_code_block(text)
            if not candidate and self._looks_like_code(text):
                candidate = text.strip()
            if candidate:
                board.set_code(candidate)

        def update_mission_board(
            key: str = "note",
            value: str = "",
            note_for_others: str = "",
            recipient: str = "All",
        ) -> str:
            normalized_key = key.strip() or "note"
            normalized_value = value.strip() or note_for_others.strip()
            if not normalized_value:
                return "Board update ignored: no value or note was provided."

            board.add_finding(normalized_key, normalized_value)
            sync_code_if_needed(normalized_value)
            if note_for_others.strip():
                board.add_request(board.current_agent, recipient.strip() or "All", note_for_others.strip())
            return f"Board updated: {normalized_key} saved."

        def post_finding(key: str = "note", value: str = "") -> str:
            normalized_key = key.strip() or "note"
            normalized_value = value.strip()
            if not normalized_value:
                return "Finding ignored: no value was provided."

            board.add_finding(normalized_key, normalized_value)
            sync_code_if_needed(normalized_value)
            return f"Board updated: {normalized_key} saved."

        def post_request(recipient: str = "All", content: str = "") -> str:
            normalized_recipient = recipient.strip() or "All"
            normalized_content = content.strip()
            if not normalized_content:
                return "Request ignored: no content was provided."

            board.add_request(board.current_agent, normalized_recipient, normalized_content)
            return f"Request posted to {normalized_recipient}."

        def mark_milestone(note: str = "") -> str:
            normalized_note = note.strip()
            if not normalized_note:
                return "Milestone ignored: no note was provided."

            board.add_milestone(normalized_note)
            return "Milestone recorded."

        registrations = [
            (
                update_mission_board,
                {
                    "name": "update_mission_board",
                    "description": "Update the shared mission board with a finding and an optional note for another agent.",
                },
            ),
            (
                post_finding,
                {
                    "name": "post_finding",
                    "description": "Post a structured finding to the shared mission board for other agents.",
                },
            ),
            (
                post_request,
                {
                    "name": "post_request",
                    "description": "Post a targeted request to another role on the shared mission board.",
                },
            ),
            (
                mark_milestone,
                {
                    "name": "mark_milestone",
                    "description": "Record a notable mission milestone on the shared mission board.",
                },
            ),
        ]

        for fn, metadata in registrations:
            self.llm.tool_engine.register(
                fn,
                name=metadata["name"],
                description=metadata["description"],
                tags=["universal"],
                source="mission",
            )

        return [metadata["name"] for _, metadata in registrations]

    @staticmethod
    def _pick_next_agent(supervisor_response: str) -> str:
        first_line = supervisor_response.strip().splitlines()[0] if supervisor_response.strip() else "END"
        normalized = first_line.upper()
        for role in ("RESEARCHER", "CODER", "REVIEWER", "END"):
            if re.search(rf"\b{role}\b", normalized):
                return role.title() if role != "END" else "END"
        return "END"

    def _resolve_next_agent(self, supervisor_response: str, board: Blackboard) -> str:
        requested_agent = self._pick_next_agent(supervisor_response)

        if board.latest_code_needs_review() and requested_agent != "Reviewer":
            board.add_milestone(
                f"Supervisor requested {requested_agent}, but the latest code revision still needed review, so Reviewer was forced."
            )
            return "Reviewer"

        if requested_agent == "Researcher" and not board.current_code and board.turn_count("Researcher") >= 2:
            board.add_milestone(
                "Repeated researcher loop detected; Coder was forced to proceed with the mission goal and current board context."
            )
            return "Coder"

        if requested_agent == "END" and not board.review_passed():
            if board.latest_code_needs_review() or board.current_code:
                board.add_milestone("Supervisor tried to end before PASS; Reviewer was forced instead.")
                return "Reviewer"
            if board.review_rejected():
                board.add_milestone("Supervisor tried to end after REJECT; Coder was forced instead.")
                return "Coder"
            if board.findings:
                board.add_milestone("Supervisor tried to end before implementation; Coder was forced instead.")
                return "Coder"
            board.add_milestone("Supervisor tried to end before research; Researcher was forced instead.")
            return "Researcher"

        return requested_agent

    @staticmethod
    def _extract_code_block(text: str) -> str:
        match = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def _looks_like_code(text: str) -> bool:
        stripped = text.strip()
        if not stripped or len(stripped) < 40:
            return False

        signals = (
            "\ndef ",
            "\nasync def ",
            "\nclass ",
            "import ",
            "from ",
            "if __name__ == \"__main__\"",
        )
        return any(signal in stripped for signal in signals)

    def _build_agent_user_message(self, agent: str, board: Blackboard) -> str:
        message = _AGENT_USER_MESSAGES[agent]
        if agent == "Coder" and self._mission_requires_skill(board.goal):
            return (
                f"{message} The mission explicitly asks for a uZephyr skill. "
                "Use write_skill to create or update the skill package, and still output the final Python source in a markdown code block for review."
            )
        if agent == "Coder" and self._mission_requires_staged_core_change(board.goal):
            return (
                f"{message} The mission targets μZephyr core files. Use propose_core_change to stage any edits under temp_core "
                "instead of editing live core files directly. Do not call apply_core_change unless the mission explicitly asks "
                "to promote the staged change. Still return the staged Python source in a markdown code block for review."
            )
        if agent == "Reviewer" and self._mission_requires_skill(board.goal):
            return (
                f"{message} Also verify that the output satisfies the requested artifact type: reject plain standalone scripts if the mission asked for a skill package."
            )
        if agent == "Reviewer" and self._mission_requires_staged_core_change(board.goal):
            return (
                f"{message} Also reject outputs that skip the staged evolve-core workflow for core files or that apply live core changes when the mission only asked to stage them."
            )
        return message

    @staticmethod
    def _mission_requires_skill(user_task: str) -> bool:
        lowered = user_task.lower()
        patterns = (
            "write a skill",
            "create a skill",
            "build a skill",
            "uzephyr skill",
            "agent skill",
        )
        return any(pattern in lowered for pattern in patterns)

    @staticmethod
    def _mission_requires_staged_core_change(user_task: str) -> bool:
        lowered = user_task.lower()
        core_targets = ("main.py", "config.py", "core/")
        core_actions = ("stage", "staged", "core change", "core file", "modify", "update", "patch")
        return any(target in lowered for target in core_targets) and any(action in lowered for action in core_actions)

    @staticmethod
    def _review_passed(review: str) -> bool:
        return review_feedback_passes(review)

    @staticmethod
    def _format_final_result(board: Blackboard) -> str:
        if board.review_passed() and board.current_code:
            return f"Mission successful. Final approved output:\n\n```python\n{board.current_code}\n```"

        if board.latest_code_needs_review():
            status = "Latest code proposal was never re-reviewed."
        elif board.review_feedback:
            status = board.review_feedback
        else:
            status = "Mission ended without a completed review."

        if board.current_code:
            return (
                f"Mission ended. Final Status: {status}\n\n"
                f"Last Proposed Code:\n```python\n{board.current_code}\n```"
            )

        return f"Mission ended. Final Status: {status}"

    def _update_board_from_response(self, agent: str, response: str, board: Blackboard, prior_code_version: int) -> None:
        if agent == "Researcher":
            board.add_milestone("Researcher completed a research pass.")
            return

        if agent == "Coder":
            code = self._extract_code_block(response)
            if code:
                board.set_code(code)
                board.add_milestone("Coder posted an updated code proposal.")
            elif board.code_version > prior_code_version:
                board.add_milestone("Coder posted an updated code proposal via a mission board tool.")
            else:
                board.add_request("Coder", "Researcher", "I need concrete findings on the board before I can implement.")
                board.add_milestone("Coder requested more context.")
            return

        if agent == "Reviewer":
            board.set_review_feedback(response)
            if board.review_passed():
                board.add_milestone("Reviewer approved the latest code proposal.")
            elif self._review_passed(response) and not board.latest_code_has_passing_sandbox():
                board.add_milestone("Reviewer returned PASS without verified sandbox evidence; treated as REJECT.")
            elif response.strip().lstrip("*#-`> ").upper().startswith("PASS"):
                board.add_milestone("Reviewer returned PASS without the required checklist evidence; treated as REJECT.")
            else:
                board.add_milestone("Reviewer requested another coding pass.")