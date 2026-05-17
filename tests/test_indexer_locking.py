from __future__ import annotations

from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from whoosh.index import LockError

from core.indexer import LocalIndexer


class _RetryingIndex:
    def __init__(self) -> None:
        self.calls = 0

    def writer(self) -> str:
        self.calls += 1
        if self.calls == 1:
            raise LockError
        return "writer"


class _BusyIndex:
    def writer(self) -> str:
        raise LockError


class _FakeCollection:
    def delete(self, *, where: dict[str, str]) -> None:
        raise AssertionError("delete should not be called while the writer is locked")


class IndexerLockingTests(unittest.TestCase):
    def test_open_whoosh_writer_retries_after_lock_error(self) -> None:
        indexer = LocalIndexer()
        retrying_index = _RetryingIndex()
        indexer._whoosh_index = retrying_index

        with patch("core.indexer.time.sleep"):
            writer = indexer._open_whoosh_writer(max_attempts=2, retry_delay=0.01)

        self.assertEqual(writer, "writer")
        self.assertEqual(retrying_index.calls, 2)

    def test_process_deletes_requeues_when_writer_is_busy(self) -> None:
        indexer = LocalIndexer()
        indexer._whoosh_index = _BusyIndex()
        indexer._collection = _FakeCollection()
        indexer._watch_lock = threading.Lock()
        delete_path = Path("E:/project/Zephyr-hybrid/tmp.py")

        with patch("core.indexer.time.sleep"):
            indexer._process_deletes([delete_path])

        self.assertIn(delete_path, indexer._delete_queue)


if __name__ == "__main__":
    unittest.main()