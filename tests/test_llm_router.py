from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

import httpx

from core.llm import LLMRouter


class _FakeToolEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object], dict[str, object]]] = []

    def get_openai_tool_schemas(self, allowed_tags: list[str] | None = None) -> list[dict[str, object]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "description": "Lookup data",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

    async def execute(self, name: str, args: dict[str, object], **kwargs: object) -> str:
        self.calls.append((name, args, kwargs))
        return f"tool:{name}"


class _FakeResponse:
    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self._payload = payload or {"choices": [{"message": {"content": "ok"}}]}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class _FakeHttpClient:
    async def get(self, *args: object, **kwargs: object) -> _FakeResponse:
        return _FakeResponse()

    async def post(self, *args: object, **kwargs: object) -> _FakeResponse:
        return _FakeResponse()


class LLMRouterLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_uses_shared_tool_loop(self) -> None:
        tool_engine = _FakeToolEngine()
        router = LLMRouter(tool_engine, object())
        router._request_chat_completion = AsyncMock(  # type: ignore[method-assign]
            side_effect=[
                (
                    {
                        "choices": [
                            {
                                "message": {
                                    "tool_calls": [
                                        {
                                            "id": "call_1",
                                            "type": "function",
                                            "function": {
                                                "name": "lookup",
                                                "arguments": '{"query": "runtime"}',
                                            },
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                    None,
                ),
                (
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "final answer",
                                }
                            }
                        ]
                    },
                    None,
                ),
            ]
        )

        result = await router.chat(
            system_prompt="system",
            history=[],
            user_message="hello",
            console=None,
            allowed_tags=["researcher"],
            allow_sensitive_tools=True,
        )

        self.assertEqual(result, "final answer")
        self.assertEqual(
            tool_engine.calls,
            [
                (
                    "lookup",
                    {"query": "runtime"},
                    {"allowed_tags": ["researcher"], "console": None, "allow_sensitive_tools": True},
                )
            ],
        )

    async def test_chat_stream_gui_emits_shared_progress_events(self) -> None:
        tool_engine = _FakeToolEngine()
        router = LLMRouter(tool_engine, object())
        router._request_chat_completion = AsyncMock(  # type: ignore[method-assign]
            side_effect=[
                (
                    {
                        "choices": [
                            {
                                "message": {
                                    "tool_calls": [
                                        {
                                            "id": "call_1",
                                            "type": "function",
                                            "function": {
                                                "name": "lookup",
                                                "arguments": '{"query": "runtime"}',
                                            },
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                    None,
                ),
                (
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "final answer",
                                }
                            }
                        ]
                    },
                    None,
                ),
            ]
        )

        chunks = [chunk async for chunk in router.chat_stream_gui("system", [], "hello")]

        self.assertEqual(
            chunks,
            [
                "*🔄 Thinking…*",
                "*⚙ Calling tool: **lookup**…*",
                "*✅ lookup — done*",
                "*✅ lookup — done*\n\n*🔄 Thinking…*",
                "final answer",
            ],
        )

    async def test_chat_stream_gui_yields_provider_errors(self) -> None:
        tool_engine = _FakeToolEngine()
        router = LLMRouter(tool_engine, object())
        router._request_chat_completion = AsyncMock(  # type: ignore[method-assign]
            return_value=(None, "⚠️ Could not reach the LLM. Is Ollama running?")
        )

        chunks = [chunk async for chunk in router.chat_stream_gui("system", [], "hello")]

        self.assertEqual(
            chunks,
            [
                "*🔄 Thinking…*",
                "⚠️ Could not reach the LLM. Is Ollama running?",
            ],
        )

    async def test_router_records_inference_metrics_for_warmup_and_completion(self) -> None:
        tool_engine = _FakeToolEngine()
        router = LLMRouter(tool_engine, object())
        fake_client = _FakeHttpClient()
        router._http_client = lambda: fake_client  # type: ignore[method-assign]

        preparation = await router.prepare_inference_runtime()
        completion, error_message = await router._request_chat_completion(
            [{"role": "system", "content": "system"}],
            [],
        )

        metrics = router.describe_inference_metrics()
        self.assertTrue(preparation.success)
        self.assertIsNone(error_message)
        self.assertIsNotNone(completion)
        self.assertEqual(metrics["last_warmup_outcome"], "success")
        self.assertEqual(metrics["last_completion_outcome"], "success")
        self.assertIsInstance(metrics["last_warmup_ms"], float)
        self.assertIsInstance(metrics["last_completion_ms"], float)


if __name__ == "__main__":
    unittest.main()