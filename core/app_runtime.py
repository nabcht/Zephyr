"""Shared runtime lifecycle helpers for CLI and GUI entry points."""

from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
from dataclasses import dataclass
from typing import Any

import config
from core.claude_mem_worker import ensure_worker_started, stop_managed_worker
from core.indexer import LocalIndexer
from core.llm import InferenceRuntimePreparation, LLMRouter
from core.memory import MemoryManager
from core.retriever import HybridRetriever
from core.tool_engine import ToolEngine

log = logging.getLogger("zephyr.app_runtime")


@dataclass(frozen=True, slots=True)
class ChatContext:
    """Conversation context assembled for a single user turn."""

    history: list[dict[str, str]]
    system_prompt: str


class AppRuntime:
    """Owns shared subsystem lifecycle for the CLI and GUI frontends."""

    def __init__(self, *, console: Any | None = None) -> None:
        self.console = console
        self.memory = MemoryManager()
        self.tool_engine: ToolEngine | None = None
        self.llm: LLMRouter | None = None
        self.indexer: LocalIndexer | None = None
        self.retriever: HybridRetriever | None = None
        self.search_status = "[yellow]Starting[/]"
        self._memory_ready = False
        self._initialized = False
        self._inference_warmup_task: asyncio.Task[InferenceRuntimePreparation] | None = None
        self._search_runtime_task: asyncio.Task[None] | None = None
        self._search_refresh_task: asyncio.Future[int] | None = None
        self._search_refresh_deferred = False

    async def ensure_memory_ready(self) -> None:
        """Initialize durable/session storage without bootstrapping the full runtime."""
        if self._memory_ready:
            return

        await self.memory.initialize()
        self._memory_ready = True

    async def initialize(self) -> None:
        """Start all shared subsystems exactly once."""
        if self._initialized:
            return

        ensure_worker_started(self.console)

        try:
            await self.ensure_memory_ready()
            self.tool_engine = ToolEngine(self.memory)
            await self.tool_engine.load_all_skills()
            self.llm = LLMRouter(self.tool_engine, self.memory)
            self._bind_archive_bridge()
            self._configure_search_runtime()
            self._initialized = True
            self._configure_inference_runtime()
        except Exception:
            await self.shutdown()
            raise

    async def shutdown(self) -> None:
        """Tear down shared subsystems in reverse dependency order."""
        inference_warmup_task = self._inference_warmup_task
        self._inference_warmup_task = None
        if inference_warmup_task is not None:
            with suppress(asyncio.CancelledError, Exception):
                await inference_warmup_task

        search_runtime_task = self._search_runtime_task
        self._search_runtime_task = None
        if search_runtime_task is not None:
            with suppress(asyncio.CancelledError, Exception):
                await search_runtime_task

        search_refresh_task = self._search_refresh_task
        self._search_refresh_task = None
        if search_refresh_task is not None:
            with suppress(asyncio.CancelledError, Exception):
                await search_refresh_task

        if self.llm is not None:
            await self.llm.close()
            self.llm = None

        if self.tool_engine is not None:
            await self.tool_engine.aclose()
            self.tool_engine = None

        await self.memory.close()
        self.indexer = None
        self.retriever = None
        self.search_status = "[yellow]Stopped[/]"
        self._search_refresh_deferred = False
        self._memory_ready = False
        self._initialized = False
        stop_managed_worker()

    def require_llm(self) -> LLMRouter:
        """Return the active LLM router or raise a runtime error."""
        if self.llm is None:
            raise RuntimeError("App runtime is not initialized.")
        return self.llm

    def require_tool_engine(self) -> ToolEngine:
        """Return the active tool engine or raise a runtime error."""
        if self.tool_engine is None:
            raise RuntimeError("App runtime is not initialized.")
        return self.tool_engine

    async def build_chat_context(
        self,
        session_id: str,
        *,
        user_message: str = "",
        history_limit: int = 20,
    ) -> ChatContext:
        """Build message history and system prompt for the next chat turn."""
        history = await self.memory.get_session_history(session_id, limit=history_limit)
        durable_facts = await self.memory.get_durable_facts()
        attachment_context = await self.build_session_attachment_context(session_id, user_message)

        system_prompt = config.SYSTEM_PROMPT
        if durable_facts:
            system_prompt += f"\n\n## Durable Facts\n{durable_facts}"
        if attachment_context:
            system_prompt += f"\n\n## Session Attachments\n{attachment_context}"

        return ChatContext(history=history, system_prompt=system_prompt)

    async def build_session_attachment_context(self, session_id: str, query: str, *, top_k: int = 4) -> str:
        """Return retrieved attachment excerpts scoped to the active web session."""
        normalized_query = query.strip()
        if not normalized_query:
            return ""

        attachments = await self.memory.get_session_attachments(session_id)
        if not attachments:
            return ""

        search_ready = await self.ensure_search_runtime(wait_for_completion=True)
        if not search_ready or self.retriever is None:
            return ""

        source_allowlist = {str(item["stored_path"]) for item in attachments}
        if not source_allowlist:
            return ""

        results = await self.retriever.search(
            normalized_query,
            semantic_k=max(3, top_k),
            keyword_k=max(5, top_k * 2),
            top_k=top_k,
            include_brain=False,
            include_archive=False,
            semantic_where={"session_id": session_id},
            source_allowlist=source_allowlist,
        )

        attachment_names = ", ".join(str(item["name"]) for item in attachments[:5])
        if len(attachments) > 5:
            attachment_names += f", +{len(attachments) - 5} more"

        if not results:
            return f"Active files: {attachment_names}"

        return (
            f"Active files: {attachment_names}\n"
            "Retrieved excerpts from the active session attachments:\n\n"
            f"{self.retriever.format_results(results)}"
        )

    async def reload_skills(self) -> None:
        """Reload registered local and external tool definitions."""
        await self.require_tool_engine().load_all_skills()

    async def prepare_search_runtime(self) -> bool:
        """Explicitly settle search warm-up during prepare flows."""
        await self.initialize()
        search_ready = await self.ensure_search_runtime(wait_for_completion=True)
        if not search_ready:
            return False

        if self._search_refresh_deferred:
            try:
                await self._schedule_search_refresh()
            except Exception:
                return False

        refresh_task = self._search_refresh_task
        if refresh_task is not None:
            try:
                await refresh_task
            except Exception:
                return False

        return self.indexer is not None

    async def prepare_inference_runtime(self) -> InferenceRuntimePreparation:
        """Explicitly warm the active provider runtime during prepare flows."""
        await self.initialize()
        return await self._schedule_inference_warmup()

    async def refresh_search_index(self, *, wait_for_completion: bool) -> int | None:
        """Refresh the search index either in the background or inline."""
        search_ready = await self.ensure_search_runtime(wait_for_completion=wait_for_completion)
        if not search_ready or self.indexer is None:
            return None

        try:
            if wait_for_completion:
                refresh_task = self._schedule_search_refresh()
                count = await refresh_task
                return count

            self._schedule_search_refresh()
            self.search_status = "[green]Ready[/] (background re-index)"
            return None
        except Exception as exc:
            self.search_status = f"[yellow]Fallback[/] (refresh failed, {type(exc).__name__})"
            raise RuntimeError(str(exc)) from exc

    def start_deferred_search_refresh(self) -> bool:
        """Schedule the deferred initial search refresh after a user turn completes."""
        if not self._search_refresh_deferred or self.indexer is None:
            return False

        try:
            self._schedule_search_refresh()
        except Exception as exc:
            self.search_status = f"[yellow]Fallback[/] (refresh failed, {type(exc).__name__})"
            log.warning("Deferred search refresh failed to start: %s", exc)
            return False

        self.search_status = "[green]Ready[/] (background re-index)"
        return True

    async def ensure_search_runtime(self, *, wait_for_completion: bool) -> bool:
        """Start the search runtime if needed and optionally wait for it to finish."""
        if self.indexer is not None:
            return True

        self._configure_search_runtime()
        task = self._search_runtime_task
        if task is None:
            return self.indexer is not None

        if not wait_for_completion:
            return False

        try:
            await task
        except Exception:
            return False

        return self.indexer is not None

    def _bind_archive_bridge(self) -> None:
        try:
            from skills.archive_researcher import _set_archive_bridge

            _set_archive_bridge(self.memory.archive)
        except Exception as exc:
            log.debug("Archive bridge binding skipped: %s", exc)

    def _configure_search_runtime(self) -> None:
        if self.indexer is not None:
            return

        if self._search_runtime_task is not None and not self._search_runtime_task.done():
            return

        self.search_status = "[yellow]Warming[/] (search runtime loading in background)"
        self._search_runtime_task = asyncio.get_running_loop().create_task(self._initialize_search_runtime())

    def _cached_search_document_count(self) -> int:
        if self.indexer is None:
            return 0

        try:
            count = int(self.indexer.collection.count())
        except Exception:
            return 0

        return max(count, 0)

    def _configure_initial_search_refresh(self) -> None:
        cached_document_count = self._cached_search_document_count()
        if cached_document_count > 0:
            self._search_refresh_deferred = True
            self.search_status = f"[green]Ready[/] ({cached_document_count} cached doc(s), initial refresh deferred)"
            return

        self._schedule_search_refresh()
        self.search_status = "[green]Ready[/] (background re-index)"

    def _configure_inference_runtime(self) -> None:
        if self.llm is None:
            return

        self._schedule_inference_warmup()

    def _schedule_inference_warmup(self) -> asyncio.Task[InferenceRuntimePreparation]:
        llm = self.require_llm()
        existing_task = self._inference_warmup_task
        if existing_task is not None and not existing_task.done():
            return existing_task

        llm.mark_inference_warming("provider runtime warm-up in progress")
        warmup_task = asyncio.get_running_loop().create_task(self._warm_inference_runtime(llm))
        self._inference_warmup_task = warmup_task

        def _finalize_warmup(task: asyncio.Task[InferenceRuntimePreparation]) -> None:
            if self._inference_warmup_task is task:
                self._inference_warmup_task = None

        warmup_task.add_done_callback(_finalize_warmup)
        return warmup_task

    async def _warm_inference_runtime(self, llm: LLMRouter) -> InferenceRuntimePreparation:
        try:
            return await llm.prepare_inference_runtime()
        except Exception as exc:
            llm.mark_inference_degraded("warm-up failed")
            log.warning("Inference runtime warm-up failed: %s", exc)
            return InferenceRuntimePreparation(
                attempted=True,
                success=False,
                detail=f"Inference runtime warm-up failed: {exc}",
            )

    async def _initialize_search_runtime(self) -> None:
        current_task = asyncio.current_task()
        indexer = LocalIndexer()

        try:
            await asyncio.get_running_loop().run_in_executor(None, indexer.initialize)
        except Exception as exc:
            if self._search_runtime_task is current_task:
                self.indexer = None
                self.search_status = f"[yellow]Fallback[/] (grep only, {type(exc).__name__})"
                log.warning("Search indexer unavailable; grep fallback remains active: %s", exc)
                self._search_runtime_task = None
            return

        if self._search_runtime_task is not current_task:
            return

        try:
            retriever = HybridRetriever(indexer, archive=self.memory.archive)
            self.indexer = indexer
            self.retriever = retriever
            self._bind_search_tools(retriever)
            self._configure_initial_search_refresh()
        except Exception as exc:
            self.indexer = None
            self.retriever = None
            self._search_refresh_deferred = False
            self.search_status = f"[yellow]Fallback[/] (grep only, {type(exc).__name__})"
            log.warning("Search runtime warm-up failed; grep fallback remains active: %s", exc)
        finally:
            if self._search_runtime_task is current_task:
                self._search_runtime_task = None

    def _schedule_search_refresh(self) -> asyncio.Future[int]:
        if self.indexer is None:
            raise RuntimeError("Search runtime is not initialized.")

        existing_task = self._search_refresh_task
        if existing_task is not None and not existing_task.done():
            return existing_task

        self._search_refresh_deferred = False
        refresh_task = asyncio.get_running_loop().run_in_executor(None, self.indexer.index_all)
        self._search_refresh_task = refresh_task

        def _finalize_refresh(task: asyncio.Future[int]) -> None:
            if self._search_refresh_task is task:
                self._search_refresh_task = None

            if task.cancelled():
                return

            exc = task.exception()
            if exc is not None:
                self.search_status = f"[yellow]Fallback[/] (refresh failed, {type(exc).__name__})"
                log.warning("Search refresh failed; grep fallback remains active: %s", exc)
                return

            count = task.result()
            self.search_status = f"[green]Ready[/] ({count} file(s) refreshed)"

        refresh_task.add_done_callback(_finalize_refresh)
        return refresh_task

    def _bind_search_tools(self, retriever: HybridRetriever) -> None:
        try:
            from skills.search_personal_data import _set_retriever

            _set_retriever(retriever)
        except Exception as exc:
            log.debug("Retriever binding skipped: %s", exc)

        try:
            from skills.index_files import _set_indexer

            _set_indexer(self.indexer)
        except Exception as exc:
            log.debug("Indexer binding skipped: %s", exc)