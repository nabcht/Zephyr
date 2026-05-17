from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch, AsyncMock

from core.app_runtime import AppRuntime
from core.llm import InferenceRuntimePreparation


class _FakeMemory:
    def __init__(self) -> None:
        self.archive = object()

    async def initialize(self) -> None:
        return None

    async def close(self) -> None:
        return None


class _FakeToolEngine:
    def __init__(self, memory: object) -> None:
        self.memory = memory

    async def load_all_skills(self) -> None:
        return None

    async def aclose(self) -> None:
        return None


class _FakeLLMRouter:
    ready_event: asyncio.Event | None = None

    def __init__(self, tool_engine: object, memory: object) -> None:
        self.tool_engine = tool_engine
        self.memory = memory
        self.prepare_calls = 0
        self._status = "[yellow]Cold[/] (Fake provider: provider runtime not warmed)"

    def describe_inference_status(self) -> str:
        return self._status

    def mark_inference_warming(self, detail: str) -> None:
        self._status = f"[yellow]Warming[/] (Fake provider: {detail})"

    def mark_inference_degraded(self, detail: str) -> None:
        self._status = f"[yellow]Degraded[/] (Fake provider: {detail})"

    async def prepare_inference_runtime(self) -> InferenceRuntimePreparation:
        self.prepare_calls += 1
        if type(self).ready_event is not None:
            await type(self).ready_event.wait()

        self._status = "[green]Ready[/] (Fake provider: provider runtime warmed)"
        return InferenceRuntimePreparation(
            attempted=True,
            success=True,
            detail="Fake provider warmed for test coverage.",
        )

    async def close(self) -> None:
        return None


class _FakeCollection:
    def __init__(self, count: int) -> None:
        self._count = count

    def count(self) -> int:
        return self._count


class _FakeIndexer:
    def __init__(self, count: int) -> None:
        self.collection = _FakeCollection(count)


class AppRuntimeInferenceWarmupTests(unittest.IsolatedAsyncioTestCase):
    async def test_initialize_starts_background_inference_warmup_and_reuses_it_for_prepare(self) -> None:
        ready_event = asyncio.Event()
        _FakeLLMRouter.ready_event = ready_event

        with (
            patch("core.app_runtime.ToolEngine", _FakeToolEngine),
            patch("core.app_runtime.LLMRouter", _FakeLLMRouter),
            patch("core.app_runtime.ensure_worker_started", return_value=None),
            patch("core.app_runtime.stop_managed_worker", return_value=None),
            patch.object(AppRuntime, "_bind_archive_bridge", return_value=None),
            patch.object(AppRuntime, "_configure_search_runtime", return_value=None),
        ):
            runtime = AppRuntime()
            runtime.memory = _FakeMemory()

            await runtime.initialize()

            llm = runtime.require_llm()
            self.assertIn("Warming", llm.describe_inference_status())
            self.assertIsNotNone(runtime._inference_warmup_task)

            prepare_task = asyncio.create_task(runtime.prepare_inference_runtime())
            await asyncio.sleep(0)

            self.assertEqual(llm.prepare_calls, 1)

            ready_event.set()
            preparation = await prepare_task

            self.assertTrue(preparation.success)
            self.assertEqual(llm.prepare_calls, 1)
            self.assertIn("Ready", llm.describe_inference_status())

            await runtime.shutdown()

    def test_cached_search_store_defers_initial_refresh(self) -> None:
        runtime = AppRuntime()
        runtime.indexer = _FakeIndexer(7)

        with patch.object(runtime, "_schedule_search_refresh") as schedule_refresh:
            runtime._configure_initial_search_refresh()

        schedule_refresh.assert_not_called()
        self.assertTrue(runtime._search_refresh_deferred)
        self.assertIn("7 cached doc(s), initial refresh deferred", runtime.search_status)

    async def test_prepare_search_runtime_runs_deferred_refresh(self) -> None:
        runtime = AppRuntime()
        runtime.indexer = _FakeIndexer(7)
        runtime._search_refresh_deferred = True

        refresh_task: asyncio.Future[int] = asyncio.get_running_loop().create_future()
        refresh_task.set_result(4)

        with (
            patch.object(runtime, "initialize", AsyncMock(return_value=None)),
            patch.object(runtime, "ensure_search_runtime", AsyncMock(return_value=True)),
            patch.object(runtime, "_schedule_search_refresh", return_value=refresh_task) as schedule_refresh,
        ):
            prepared = await runtime.prepare_search_runtime()

        self.assertTrue(prepared)
        schedule_refresh.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
