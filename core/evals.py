"""Deterministic evaluation scenario loading for mission regression checks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

import config


@dataclass(frozen=True, slots=True)
class EvalScenario:
    """A single deterministic mission scenario."""

    input_task: str
    expected_tools: list[str]
    validation_script: str


@dataclass(frozen=True, slots=True)
class EvalRunResult:
    """Outcome of running a deterministic mission scenario."""

    input_task: str
    passed: bool
    used_tools: list[str]
    missing_tools: list[str]
    validation_error: str
    mission_result: str


def load_eval_scenarios(path: Path | None = None) -> list[EvalScenario]:
    """Load and validate deterministic mission scenarios from JSON."""
    scenarios_path = path or config.SCENARIOS_FILE
    payload = json.loads(scenarios_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Eval scenarios file must contain a JSON array: {scenarios_path}")

    scenarios: list[EvalScenario] = []
    for index, raw_scenario in enumerate(payload, start=1):
        if not isinstance(raw_scenario, dict):
            raise ValueError(f"Eval scenario {index} must be a JSON object.")

        input_task = raw_scenario.get("input_task")
        expected_tools = raw_scenario.get("expected_tools")
        validation_script = raw_scenario.get("validation_script")

        if not isinstance(input_task, str) or not input_task.strip():
            raise ValueError(f"Eval scenario {index} requires a non-empty string 'input_task'.")
        if not isinstance(expected_tools, list) or not expected_tools:
            raise ValueError(f"Eval scenario {index} requires a non-empty list 'expected_tools'.")
        if not all(isinstance(tool_name, str) and tool_name.strip() for tool_name in expected_tools):
            raise ValueError(f"Eval scenario {index} field 'expected_tools' must contain non-empty strings.")
        if not isinstance(validation_script, str) or not validation_script.strip():
            raise ValueError(f"Eval scenario {index} requires a non-empty string 'validation_script'.")

        scenarios.append(
            EvalScenario(
                input_task=input_task.strip(),
                expected_tools=[tool_name.strip() for tool_name in expected_tools],
                validation_script=validation_script.strip(),
            )
        )

    return scenarios


async def run_eval_scenario(
    scenario: EvalScenario,
    mission_runner: Callable[[str], Awaitable[str]],
    tool_engine: Any | None = None,
) -> EvalRunResult:
    """Execute one eval scenario, recording tool usage and validation outcome."""
    used_tools: list[str] = []
    validation_error = ""

    if tool_engine is None:
        mission_result = await mission_runner(scenario.input_task)
    else:
        original_execute = tool_engine.execute

        async def tracked_execute(name: str, args: dict[str, Any], **kwargs: Any) -> str:
            used_tools.append(name)
            return await original_execute(name, args, **kwargs)

        tool_engine.execute = tracked_execute
        try:
            mission_result = await mission_runner(scenario.input_task)
        finally:
            tool_engine.execute = original_execute

    missing_tools = [tool_name for tool_name in scenario.expected_tools if tool_name not in used_tools]

    try:
        exec(
            scenario.validation_script,
            {"__builtins__": {"AssertionError": AssertionError, "len": len, "all": all, "any": any}},
            {"result": mission_result, "used_tools": used_tools},
        )
    except Exception as exc:
        validation_error = f"{type(exc).__name__}: {exc}"

    return EvalRunResult(
        input_task=scenario.input_task,
        passed=not missing_tools and not validation_error,
        used_tools=used_tools,
        missing_tools=missing_tools,
        validation_error=validation_error,
        mission_result=mission_result,
    )


async def run_eval_scenarios(
    mission_runner: Callable[[str], Awaitable[str]],
    tool_engine: Any | None = None,
    scenarios: list[EvalScenario] | None = None,
) -> list[EvalRunResult]:
    """Execute all deterministic eval scenarios in order."""
    scenario_list = scenarios if scenarios is not None else load_eval_scenarios()
    results: list[EvalRunResult] = []
    for scenario in scenario_list:
        results.append(await run_eval_scenario(scenario, mission_runner, tool_engine))
    return results


def summarize_eval_results(results: list[EvalRunResult]) -> str:
    """Render a compact text summary for CLI verification output."""
    passed_count = sum(1 for result in results if result.passed)
    lines = [f"Mission evals: {passed_count}/{len(results)} passed."]

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"- {status}: {result.input_task}")
        if result.missing_tools:
            lines.append(f"  Missing tools: {', '.join(result.missing_tools)}")
        if result.validation_error:
            lines.append(f"  Validation error: {result.validation_error}")

    return "\n".join(lines)