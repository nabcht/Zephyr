from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from backend.api.routes import chat as chat_routes
from backend.schemas.chat import ChatTurnRequest


class _FakeStreamingRequest:
    def __init__(self, disconnection_results: list[bool]) -> None:
        self.is_disconnected = AsyncMock(side_effect=disconnection_results)


class ChatRouteStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_chat_turn_forwards_disconnect_check_and_omits_done_event_after_disconnect(self) -> None:
        fake_request = _FakeStreamingRequest([False, False, True, True])

        async def fake_stream_turn(
            session_identifier: str,
            message: str,
            *,
            allow_sensitive_tools: bool | None = None,
            client_disconnect_check=None,
        ):
            self.assertEqual(session_identifier, "route-regression")
            self.assertEqual(message, "hello")
            self.assertIsNone(allow_sensitive_tools)
            self.assertIsNotNone(client_disconnect_check)
            self.assertFalse(await client_disconnect_check())

            yield "partial output"

            self.assertTrue(await client_disconnect_check())

        with patch.object(chat_routes.service, "stream_turn", new=fake_stream_turn):
            streaming_response = await chat_routes.stream_chat_turn(
                ChatTurnRequest(session_id="route-regression", message="hello"),
                fake_request,  # type: ignore[arg-type]
            )

            collected_chunks: list[str] = []
            async for chunk in streaming_response.body_iterator:
                if isinstance(chunk, bytes):
                    collected_chunks.append(chunk.decode("utf-8"))
                else:
                    collected_chunks.append(str(chunk))

        streamed_body = "".join(collected_chunks)
        self.assertIn("event: snapshot", streamed_body)
        self.assertIn("partial output", streamed_body)
        self.assertNotIn("event: done", streamed_body)
        self.assertGreaterEqual(fake_request.is_disconnected.await_count, 4)


if __name__ == "__main__":
    unittest.main()