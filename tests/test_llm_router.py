from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

import httpx

from core.llm import LLMRouter


class _FakeToolEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object], dict[str, object]]] = []

    def get_openai_tool_schemas(
        self,
        allowed_tags: list[str] | None = None,
        *,
        compact_for_provider: bool = False,
    ) -> list[dict[str, object]]:
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


class _FakePayloadHttpClient(_FakeHttpClient):
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload
        self.last_json: dict[str, object] | None = None
        self.post_request_count = 0

    async def post(self, *args: object, **kwargs: object) -> _FakeResponse:
        self.post_request_count += 1
        raw_json = kwargs.get("json")
        if isinstance(raw_json, dict):
            self.last_json = raw_json
        return _FakeResponse(self._payload)


class _FakeStreamingResponse:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    async def __aenter__(self) -> _FakeStreamingResponse:
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeStreamingHttpClient(_FakeHttpClient):
    def __init__(self, lines: list[str]) -> None:
        self._streaming_response = _FakeStreamingResponse(lines)

    def stream(self, *args: object, **kwargs: object) -> _FakeStreamingResponse:
        return self._streaming_response


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
        router._provider = "llamacpp"
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
        router._provider = "llamacpp"
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

    async def test_explicit_no_tool_prompt_omits_provider_tool_schemas(self) -> None:
        tool_engine = _FakeToolEngine()
        router = LLMRouter(tool_engine, object())
        router._provider = "openrouter"
        payload_http_client = _FakePayloadHttpClient({"choices": [{"message": {"content": "OK"}}]})
        router._http_client = lambda: payload_http_client  # type: ignore[method-assign]

        response = await router.chat(
            system_prompt="system\n\n## Durable Facts\nKeep this hidden durable fact out of the lightweight exact-answer request.",
            history=[],
            user_message="Reply with exactly very good. Do not call tools.",
            console=None,
        )

        self.assertEqual(response, "OK")
        self.assertIsNotNone(payload_http_client.last_json)
        provider_messages = payload_http_client.last_json["messages"]
        self.assertEqual(provider_messages[0]["content"], "system")
        payload_metrics = router.describe_provider_payload_metrics()
        self.assertEqual(payload_metrics["provider_message_count"], 2)
        self.assertEqual(payload_metrics["history_message_count"], 0)
        self.assertEqual(payload_metrics["tool_schema_count"], 0)
        self.assertGreater(int(payload_metrics["serialized_payload_characters"] or 0), 0)
        self.assertIs(payload_metrics["used_lightweight_payload_strategy"], True)

    async def test_simple_exact_answer_prompt_uses_local_fast_path(self) -> None:
        tool_engine = _FakeToolEngine()
        router = LLMRouter(tool_engine, object())
        router._request_chat_completion = AsyncMock(  # type: ignore[method-assign]
            side_effect=AssertionError("Provider request should not run for local exact-answer fast path")
        )

        response = await router.chat(
            system_prompt="system\n\n## Durable Facts\nThis should not matter for the local fast path.",
            history=[{"role": "assistant", "content": "Earlier context"}],
            user_message="Reply with exactly OK. Do not call tools.",
            console=None,
        )

        self.assertEqual(response, "OK")
        router._request_chat_completion.assert_not_awaited()
        inference_metrics = router.describe_inference_metrics()
        self.assertEqual(inference_metrics["first_response_token_milliseconds"], 0.0)
        self.assertEqual(inference_metrics["first_response_token_outcome"], "local_fast_path")
        self.assertEqual(inference_metrics["last_completion_milliseconds"], 0.0)
        self.assertEqual(inference_metrics["last_completion_outcome"], "local_fast_path")
        payload_metrics = router.describe_provider_payload_metrics()
        self.assertEqual(payload_metrics["provider_message_count"], 0)
        self.assertEqual(payload_metrics["history_message_count"], 0)
        self.assertEqual(payload_metrics["tool_schema_count"], 0)
        self.assertEqual(payload_metrics["serialized_payload_characters"], 0)
        self.assertIs(payload_metrics["used_lightweight_payload_strategy"], True)

    async def test_router_records_provider_payload_metrics_for_normal_chat_request(self) -> None:
        tool_engine = _FakeToolEngine()
        router = LLMRouter(tool_engine, object())
        router._provider = "openrouter"
        payload_http_client = _FakePayloadHttpClient({"choices": [{"message": {"content": "OK"}}]})
        router._http_client = lambda: payload_http_client  # type: ignore[method-assign]

        response = await router.chat(
            system_prompt="system\n\n## Durable Facts\nRetain durable facts for normal requests.",
            history=[
                {"role": "user", "content": "Earlier question"},
                {"role": "assistant", "content": "Earlier answer"},
            ],
            user_message="hello",
            console=None,
        )

        self.assertEqual(response, "OK")
        self.assertIsNotNone(payload_http_client.last_json)
        provider_messages = payload_http_client.last_json["messages"]
        self.assertEqual(provider_messages[0]["content"], "system\n\n## Durable Facts\nRetain durable facts for normal requests.")
        payload_metrics = router.describe_provider_payload_metrics()
        self.assertEqual(payload_metrics["provider_message_count"], 4)
        self.assertEqual(payload_metrics["history_message_count"], 2)
        self.assertEqual(payload_metrics["tool_schema_count"], 1)
        self.assertGreater(int(payload_metrics["serialized_payload_characters"] or 0), 0)
        self.assertIs(payload_metrics["used_lightweight_payload_strategy"], False)

    async def test_non_exact_no_tool_prompt_keeps_full_system_prompt_context(self) -> None:
        tool_engine = _FakeToolEngine()
        router = LLMRouter(tool_engine, object())
        router._provider = "openrouter"
        payload_http_client = _FakePayloadHttpClient({"choices": [{"message": {"content": "Summary"}}]})
        router._http_client = lambda: payload_http_client  # type: ignore[method-assign]

        response = await router.chat(
            system_prompt="system\n\n## Durable Facts\nKeep durable facts for broader no-tool requests.",
            history=[{"role": "assistant", "content": "Existing context"}],
            user_message="Without tools, summarize the repository status.",
            console=None,
        )

        self.assertEqual(response, "Summary")
        self.assertIsNotNone(payload_http_client.last_json)
        provider_messages = payload_http_client.last_json["messages"]
        self.assertEqual(
            provider_messages[0]["content"],
            "system\n\n## Durable Facts\nKeep durable facts for broader no-tool requests.",
        )
        self.assertEqual(provider_messages[1]["content"], "Existing context")
        self.assertEqual(len(provider_messages), 3)
        self.assertNotIn("tools", payload_http_client.last_json)

    async def test_chat_stream_gui_uses_local_fast_path_for_simple_exact_answer_prompt(self) -> None:
        tool_engine = _FakeToolEngine()
        router = LLMRouter(tool_engine, object())
        router._request_chat_completion = AsyncMock(  # type: ignore[method-assign]
            side_effect=AssertionError("Provider request should not run for local exact-answer fast path")
        )

        chunks = [
            chunk
            async for chunk in router.chat_stream_gui(
                "system\n\n## Durable Facts\nThis should not matter for the local fast path.",
                [{"role": "assistant", "content": "Earlier context"}],
                'Reply with exactly "OK now".',
            )
        ]

        self.assertEqual(chunks, ["OK now"])
        router._request_chat_completion.assert_not_awaited()
        inference_metrics = router.describe_inference_metrics()
        self.assertEqual(inference_metrics["first_response_token_outcome"], "local_fast_path")
        self.assertEqual(inference_metrics["last_completion_outcome"], "local_fast_path")

    async def test_repeated_non_exact_prompt_uses_local_response_cache(self) -> None:
        tool_engine = _FakeToolEngine()
        router = LLMRouter(tool_engine, object())
        router._provider = "openrouter"
        payload_http_client = _FakePayloadHttpClient({"choices": [{"message": {"content": "Summary"}}]})
        router._http_client = lambda: payload_http_client  # type: ignore[method-assign]

        first_response = await router.chat(
            system_prompt="system",
            history=[],
            user_message="Without tools, summarize the repository status.",
            console=None,
        )
        second_response = await router.chat(
            system_prompt="system",
            history=[],
            user_message="Without tools, summarize the repository status.",
            console=None,
        )

        self.assertEqual(first_response, "Summary")
        self.assertEqual(second_response, "Summary")
        self.assertEqual(payload_http_client.post_request_count, 1)
        inference_metrics = router.describe_inference_metrics()
        self.assertEqual(inference_metrics["first_response_token_milliseconds"], 0.0)
        self.assertEqual(inference_metrics["first_response_token_outcome"], "local_response_cache")
        self.assertEqual(inference_metrics["last_completion_milliseconds"], 0.0)
        self.assertEqual(inference_metrics["last_completion_outcome"], "local_response_cache")
        payload_metrics = router.describe_provider_payload_metrics()
        self.assertEqual(payload_metrics["provider_message_count"], 0)
        self.assertEqual(payload_metrics["history_message_count"], 0)
        self.assertEqual(payload_metrics["tool_schema_count"], 0)
        self.assertEqual(payload_metrics["serialized_payload_characters"], 0)
        self.assertIs(payload_metrics["used_lightweight_payload_strategy"], False)

    async def test_chat_stream_gui_reuses_local_response_cache_for_repeated_non_exact_prompt(self) -> None:
        tool_engine = _FakeToolEngine()
        router = LLMRouter(tool_engine, object())
        router._provider = "openrouter"
        payload_http_client = _FakePayloadHttpClient({"choices": [{"message": {"content": "Summary"}}]})
        router._http_client = lambda: payload_http_client  # type: ignore[method-assign]

        first_response = await router.chat(
            system_prompt="system",
            history=[],
            user_message="Without tools, summarize the repository status.",
            console=None,
        )
        streamed_chunks = [
            chunk
            async for chunk in router.chat_stream_gui(
                "system",
                [],
                "Without tools, summarize the repository status.",
            )
        ]

        self.assertEqual(first_response, "Summary")
        self.assertEqual(streamed_chunks, ["Summary"])
        self.assertEqual(payload_http_client.post_request_count, 1)
        inference_metrics = router.describe_inference_metrics()
        self.assertEqual(inference_metrics["first_response_token_outcome"], "local_response_cache")
        self.assertEqual(inference_metrics["last_completion_outcome"], "local_response_cache")

    async def test_chat_stream_gui_streams_provider_response_content(self) -> None:
        tool_engine = _FakeToolEngine()
        router = LLMRouter(tool_engine, object())
        streaming_http_client = _FakeStreamingHttpClient(
            [
                'data: {"choices": [{"delta": {"content": "Hello"}}]}',
                'data: {"choices": [{"delta": {"content": " there"}}]}',
                "data: [DONE]",
            ]
        )
        router._http_client = lambda: streaming_http_client  # type: ignore[method-assign]

        chunks = [chunk async for chunk in router.chat_stream_gui("system", [], "hello")]

        self.assertEqual(
            chunks,
            [
                "*🔄 Thinking…*",
                "Hello",
                "Hello there",
            ],
        )

        metrics = router.describe_inference_metrics()
        self.assertEqual(metrics["first_response_token_outcome"], "success")
        self.assertEqual(metrics["last_completion_outcome"], "success")
        self.assertIsInstance(metrics["first_response_token_milliseconds"], float)
        self.assertIsInstance(metrics["last_completion_milliseconds"], float)

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
        self.assertEqual(metrics["first_response_token_outcome"], "not_streamed")
        self.assertEqual(metrics["last_completion_outcome"], "success")
        self.assertIsInstance(metrics["last_warmup_milliseconds"], float)
        self.assertIsInstance(metrics["last_completion_milliseconds"], float)


if __name__ == "__main__":
    unittest.main()
