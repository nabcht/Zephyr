from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import UploadFile

from backend.services.session_attachment_service import SessionAttachmentService


class _FakeMemory:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    async def get_session_attachments(self, session_id: str) -> list[dict[str, object]]:
        return [record for record in self.records if record["session_id"] == session_id]

    async def add_session_attachment(
        self,
        session_id: str,
        attachment_id: str,
        *,
        name: str,
        stored_path: str,
        media_type: str,
        size_bytes: int,
    ) -> dict[str, object]:
        record = {
            "attachment_id": attachment_id,
            "session_id": session_id,
            "name": name,
            "stored_path": stored_path,
            "media_type": media_type,
            "size_bytes": size_bytes,
            "created_at": "2026-05-20T12:00:00+00:00",
        }
        self.records.append(record)
        return record

    async def get_session_attachment(self, session_id: str, attachment_id: str) -> dict[str, object] | None:
        for record in self.records:
            if record["session_id"] == session_id and record["attachment_id"] == attachment_id:
                return record
        return None

    async def remove_session_attachment(self, session_id: str, attachment_id: str) -> dict[str, object] | None:
        existing = await self.get_session_attachment(session_id, attachment_id)
        if existing is None:
            return None
        self.records = [
            record for record in self.records
            if not (record["session_id"] == session_id and record["attachment_id"] == attachment_id)
        ]
        return existing


class _FakeIndexer:
    def __init__(self) -> None:
        self.index_calls: list[tuple[str, dict[str, object] | None]] = []
        self.remove_calls: list[str] = []

    def index_file(self, path: Path, *, extra_metadata: dict[str, object] | None = None) -> bool:
        self.index_calls.append((str(path), extra_metadata))
        return True

    def remove_file(self, path: Path) -> bool:
        self.remove_calls.append(str(path))
        return True


class _FakeRuntime:
    def __init__(self) -> None:
        self.memory = _FakeMemory()
        self.indexer = _FakeIndexer()

    async def ensure_search_runtime(self, *, wait_for_completion: bool) -> bool:
        return wait_for_completion


class SessionAttachmentServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_list_and_delete_attachment(self) -> None:
        runtime = _FakeRuntime()
        service = SessionAttachmentService()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            upload = UploadFile(file=BytesIO(b"hello attachment"), filename="notes.md")

            with (
                patch("backend.services.session_attachment_service.config.SESSION_ATTACHMENTS_DIR", temp_root),
                patch("backend.services.session_attachment_service.ensure_runtime_ready", AsyncMock(return_value=runtime)),
                patch("backend.services.session_attachment_service.ensure_memory_ready", AsyncMock(return_value=runtime)),
                patch("backend.services.session_attachment_service.parse_file", return_value=[{"text": "hello", "source": "notes.md", "page": None}]),
            ):
                created = await service.upload_attachment("sess-1", upload)
                listed = await service.list_attachments("sess-1")
                deleted = await service.delete_attachment("sess-1", created.attachment_id)

        self.assertEqual(created.name, "notes.md")
        self.assertEqual(created.session_id, "sess-1")
        self.assertEqual(len(listed.attachments), 1)
        self.assertTrue(deleted.deleted)
        self.assertEqual(len(runtime.indexer.index_calls), 1)
        self.assertEqual(len(runtime.indexer.remove_calls), 1)
        self.assertEqual(runtime.memory.records, [])