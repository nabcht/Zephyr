"""Session-scoped attachment storage and indexing for the hybrid backend."""

from __future__ import annotations

import asyncio
from pathlib import Path
import re
import shutil
import uuid

from fastapi import UploadFile

import config
from backend.runtime_gateway import ensure_memory_ready, ensure_runtime_ready
from backend.schemas.attachment import (
    SessionAttachmentDeleteResponse,
    SessionAttachmentListResponse,
    SessionAttachmentResponse,
)
from core.markdown_parser import parse_file


_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
_FILENAME_SANITIZER = re.compile(r"[^A-Za-z0-9._ -]+")


class SessionAttachmentService:
    """Persist, index, list, and delete web-session attachments."""

    @staticmethod
    def _sanitize_filename(raw_name: str) -> str:
        candidate = Path(raw_name or "").name.strip().replace("\x00", "")
        candidate = _FILENAME_SANITIZER.sub("_", candidate).strip(" .")
        if not candidate:
            return "attachment"
        return candidate

    @staticmethod
    def _response_from_record(record: dict[str, object]) -> SessionAttachmentResponse:
        return SessionAttachmentResponse(
            attachment_id=str(record["attachment_id"]),
            session_id=str(record["session_id"]),
            name=str(record["name"]),
            media_type=str(record["media_type"]),
            size_bytes=int(record["size_bytes"]),
            created_at=str(record["created_at"]),
        )

    async def list_attachments(self, session_id: str) -> SessionAttachmentListResponse:
        runtime = await ensure_memory_ready()
        records = await runtime.memory.get_session_attachments(session_id)
        return SessionAttachmentListResponse(
            session_id=session_id,
            attachments=[self._response_from_record(record) for record in records],
        )

    async def upload_attachment(self, session_id: str, upload: UploadFile) -> SessionAttachmentResponse:
        file_name = self._sanitize_filename(upload.filename or "")
        attachment_id = uuid.uuid4().hex[:12]
        attachment_dir = config.SESSION_ATTACHMENTS_DIR / session_id / attachment_id
        stored_path = attachment_dir / file_name
        size_bytes = 0
        runtime = None
        indexed = False

        attachment_dir.mkdir(parents=True, exist_ok=True)

        try:
            with stored_path.open("wb") as handle:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    size_bytes += len(chunk)
                    if size_bytes > _MAX_ATTACHMENT_BYTES:
                        raise ValueError(f"{file_name} exceeds the 10 MB session attachment limit.")
                    handle.write(chunk)
        finally:
            await upload.close()

        if size_bytes <= 0:
            self._cleanup_path(stored_path)
            raise ValueError("Uploaded attachment is empty.")

        parsed_blocks = await asyncio.get_running_loop().run_in_executor(None, parse_file, stored_path)
        if not parsed_blocks:
            self._cleanup_path(stored_path)
            raise ValueError(
                "Unsupported attachment or no readable text could be extracted. "
                "Supported session attachments currently require extractable text content."
            )

        try:
            runtime = await ensure_runtime_ready()
            search_ready = await runtime.ensure_search_runtime(wait_for_completion=True)
            if not search_ready or runtime.indexer is None:
                raise RuntimeError("Search runtime is not ready, so the attachment could not be indexed.")

            indexed = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: runtime.indexer.index_file(
                    stored_path,
                    extra_metadata={
                        "session_id": session_id,
                        "attachment_id": attachment_id,
                    },
                ),
            )
            if not indexed:
                raise RuntimeError("Attachment indexing failed.")

            record = await runtime.memory.add_session_attachment(
                session_id,
                attachment_id,
                name=file_name,
                stored_path=str(stored_path),
                media_type=upload.content_type or "application/octet-stream",
                size_bytes=size_bytes,
            )
            return self._response_from_record(record)
        except Exception:
            if indexed and runtime is not None and runtime.indexer is not None:
                await asyncio.get_running_loop().run_in_executor(None, runtime.indexer.remove_file, stored_path)
            self._cleanup_path(stored_path)
            raise

    async def delete_attachment(self, session_id: str, attachment_id: str) -> SessionAttachmentDeleteResponse:
        runtime = await ensure_memory_ready()
        existing = await runtime.memory.get_session_attachment(session_id, attachment_id)
        if existing is None:
            raise KeyError(attachment_id)

        runtime = await ensure_runtime_ready()
        search_ready = await runtime.ensure_search_runtime(wait_for_completion=True)
        if not search_ready or runtime.indexer is None:
            raise RuntimeError("Search runtime is not ready, so the attachment could not be removed cleanly.")

        stored_path = Path(str(existing["stored_path"]))
        await asyncio.get_running_loop().run_in_executor(None, runtime.indexer.remove_file, stored_path)
        await runtime.memory.remove_session_attachment(session_id, attachment_id)
        self._cleanup_path(stored_path)

        return SessionAttachmentDeleteResponse(
            session_id=session_id,
            attachment_id=attachment_id,
            deleted=True,
        )

    @staticmethod
    def _cleanup_path(stored_path: Path) -> None:
        with_context = stored_path.parent
        if stored_path.exists():
            stored_path.unlink(missing_ok=True)
        if with_context.exists():
            shutil.rmtree(with_context, ignore_errors=True)