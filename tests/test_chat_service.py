from __future__ import annotations

import unittest

from core.app_runtime import ChatContext
from core.chat_service import ChatService
from core.llm import StreamedTurnCancelled


class _FakeMemory:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, str]] = []

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        self.messages.append((session_id, role, content))


class _FakeLLM:
    async def chat(self, **kwargs: object) -> str:
        return "reply"

    async def chat_stream_gui(self, *args: object, **kwargs: object):
        yield "working"
        yield "reply"


class _CancelledStreamingLargeLanguageModel:
    async def chat(self, **kwargs: object) -> str:
        return "reply"

    async def chat_stream_gui(self, *args: object, **kwargs: object):
        yield "partial"
        raise StreamedTurnCancelled()


class _FakeRuntime:
    def __init__(self, large_language_model: object | None = None) -> None:
        self.memory = _FakeMemory()
        self.llm = large_language_model or _FakeLLM()
        self.deferred_refresh_starts = 0
        self.last_context_request: tuple[str, str, int] | None = None

    async def build_chat_context(self, session_id: str, *, user_message: str = "", history_limit: int = 20) -> ChatContext:
        self.last_context_request = (session_id, user_message, history_limit)
        return ChatContext(history=[], system_prompt="system")

    def require_llm(self) -> _FakeLLM:
        return self.llm

    def start_deferred_search_refresh(self) -> bool:
        self.deferred_refresh_starts += 1
        return True


class ChatServiceDeferredRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_turn_starts_deferred_search_refresh_after_persist(self) -> None:
        runtime = _FakeRuntime()
        service = ChatService(runtime)

        response = await service.run_turn("session", "hello", console=None)

        self.assertEqual(response, "reply")
        self.assertEqual(runtime.deferred_refresh_starts, 1)
        self.assertEqual(runtime.last_context_request, ("session", "hello", 20))
        self.assertEqual(
            runtime.memory.messages,
            [
                ("session", "user", "hello"),
                ("session", "assistant", "reply"),
            ],
        )

    async def test_stream_turn_starts_deferred_search_refresh_after_stream_completion(self) -> None:
        runtime = _FakeRuntime()
        service = ChatService(runtime)

        chunks = [chunk async for chunk in service.stream_turn("session", "hello")]

        self.assertEqual(chunks, ["working", "reply"])
        self.assertEqual(runtime.deferred_refresh_starts, 1)
        self.assertEqual(runtime.last_context_request, ("session", "hello", 20))
        self.assertEqual(
            runtime.memory.messages,
            [
                ("session", "user", "hello"),
                ("session", "assistant", "reply"),
            ],
        )

    async def test_stream_turn_skips_persisting_partial_reply_after_cancellation(self) -> None:
        runtime = _FakeRuntime(large_language_model=_CancelledStreamingLargeLanguageModel())
        service = ChatService(runtime)

        chunks = [chunk async for chunk in service.stream_turn("session", "hello")]

        self.assertEqual(chunks, ["partial"])
        self.assertEqual(runtime.deferred_refresh_starts, 0)
        self.assertEqual(
            runtime.memory.messages,
            [
                ("session", "user", "hello"),
            ],
        )


if __name__ == "__main__":
    unittest.main()