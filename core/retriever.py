"""HybridRetriever — combines ChromaDB semantic search with Whoosh keyword search,
deduplicates results, and formats them with source metadata tags.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import config
from core import linker

log = logging.getLogger("uzephyr.retriever")


@dataclass
class SearchResult:
    """A single search hit."""
    text: str
    source: str
    source_name: str
    page: int | None
    score: float
    origin: str  # "entity" | "truth" | "timeline" | "semantic" | "keyword" | "archive" | combined tags


class HybridRetriever:
    """Merges vector (semantic) and keyword (exact-match) search results."""

    def __init__(self, indexer: Any, archive: Any | None = None) -> None:
        """Accept a fully-initialised LocalIndexer."""
        self._indexer = indexer
        self._collection = indexer.collection
        self._whoosh_index = indexer.whoosh_index
        self._archive = archive

    # ── Semantic search via ChromaDB ──────────────────────────────────────

    def semantic_search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        query_embedding = self._indexer.embed_model.encode([query]).tolist()
        results = self._collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        hits: list[SearchResult] = []
        if not results or not results.get("documents"):
            return hits

        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            # ChromaDB cosine distance: lower = closer; convert to similarity
            similarity = 1.0 - dist
            hits.append(SearchResult(
                text=doc,
                source=meta.get("source", ""),
                source_name=meta.get("source_name", ""),
                page=meta.get("page") or None,
                score=similarity,
                origin="semantic",
            ))
        return hits

    # ── Keyword search via Whoosh ─────────────────────────────────────────

    def keyword_search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        from whoosh.qparser import MultifieldParser

        hits: list[SearchResult] = []
        with self._whoosh_index.searcher() as searcher:
            parser = MultifieldParser(["content"], schema=self._whoosh_index.schema)
            parsed_query = parser.parse(query)
            whoosh_results = searcher.search(parsed_query, limit=top_k)

            for hit in whoosh_results:
                hits.append(SearchResult(
                    text=hit["content"],
                    source=hit.get("source", ""),
                    source_name=hit.get("source", "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1],
                    page=hit.get("page") or None,
                    score=float(hit.score),
                    origin="keyword",
                ))
        return hits

    # ── Entity memory injection (Truth-First) ─────────────────────────────

    def entity_search(self, query: str) -> list[SearchResult]:
        """Return entity-file context for any #Person or [[Project]] tokens in *query*.

        Returns a single high-priority SearchResult (score=1.0, origin="entity")
        when entity files exist, or an empty list otherwise.
        """
        context = linker.get_entity_context(query)
        if not context:
            return []
        return [
            SearchResult(
                text=context,
                source="knowledge/brain/entities",
                source_name="Entity Memory",
                page=None,
                score=1.0,
                origin="entity",
            )
        ]

    @staticmethod
    def _query_terms(query: str) -> list[str]:
        return [term for term in re.findall(r"[a-z0-9_]+", query.lower()) if len(term) >= 3]

    def _brain_file_search(
        self,
        path,
        *,
        source_name: str,
        origin: str,
        split_pattern: str,
        score_boost: float,
        top_k: int,
        query_terms: list[str],
    ) -> list[SearchResult]:
        if not path.exists() or not query_terms:
            return []

        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return []

        raw_chunks = [chunk.strip() for chunk in re.split(split_pattern, content) if chunk.strip()]
        scored_hits: list[tuple[float, str]] = []

        for chunk in raw_chunks:
            lowered = chunk.lower()
            matched_terms = [term for term in query_terms if term in lowered]
            if not matched_terms:
                continue
            score = score_boost + (len(set(matched_terms)) / len(set(query_terms)))
            scored_hits.append((score, chunk))

        scored_hits.sort(key=lambda item: item[0], reverse=True)
        results: list[SearchResult] = []
        for score, chunk in scored_hits[:top_k]:
            results.append(
                SearchResult(
                    text=chunk,
                    source=path.as_posix(),
                    source_name=source_name,
                    page=None,
                    score=score,
                    origin=origin,
                )
            )
        return results

    def truth_search(self, query: str, top_k: int = 2) -> list[SearchResult]:
        """Return executive-summary truth snippets before probabilistic retrieval paths."""
        return self._brain_file_search(
            config.TRUTH_FILE,
            source_name="Brain Truth",
            origin="truth",
            split_pattern=r"\n\s*\n",
            score_boost=2.0,
            top_k=top_k,
            query_terms=self._query_terms(query),
        )

    def timeline_search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        """Return matching timeline events as a deterministic local fallback."""
        return self._brain_file_search(
            config.TIMELINE_FILE,
            source_name="Brain Timeline",
            origin="timeline",
            split_pattern=r"\n+",
            score_boost=1.0,
            top_k=top_k,
            query_terms=self._query_terms(query),
        )

    async def archive_search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Query the external Claude-Mem archive layer when available."""
        if not config.MCP_ENABLED or self._archive is None:
            return []

        try:
            hits = await self._archive.search(query, limit=top_k)
        except Exception as exc:
            log.warning("Archive search failed: %s", exc)
            return []

        results: list[SearchResult] = []
        for rank, hit in enumerate(hits):
            title = str(hit.get("title") or f"Archive hit #{hit.get('id', rank + 1)}")
            text = str(hit.get("text") or title)
            observation_id = hit.get("id")
            source_name = "Claude-Mem Archive"
            if observation_id is not None:
                source_name = f"Claude-Mem Archive #{observation_id}"

            results.append(
                SearchResult(
                    text=text,
                    source="claude-mem",
                    source_name=source_name,
                    page=None,
                    score=max(0.05, 1.0 - (rank * 0.05)),
                    origin="archive",
                )
            )
        return results

    # ── Hybrid merge + deduplication ──────────────────────────────────────

    async def search(self, query: str, semantic_k: int = 5, keyword_k: int = 5, top_k: int = 5) -> list[SearchResult]:
        """Run entity, semantic, keyword, and archive searches; merge using RRF."""
        entity_hits = self.entity_search(query)
        truth_hits = self.truth_search(query, top_k=2)
        timeline_hits = self.timeline_search(query, top_k=3)
        semantic_hits = self.semantic_search(query, top_k=semantic_k)
        keyword_hits = self.keyword_search(query, top_k=keyword_k)
        archive_hits = await self.archive_search(query, top_k=top_k)

        seen_texts: set[str] = set()
        merged: list[SearchResult] =[]

        # 1. Deterministic brain results bypass RRF (Truth-First priority)
        priority_hits = entity_hits + truth_hits + timeline_hits
        for hit in priority_hits:
            key = hit.text[:200]
            if key not in seen_texts:
                seen_texts.add(key)
                merged.append(hit)

        # 2. Reciprocal Rank Fusion (RRF) for semantic & keyword hits
        RRF_K = 60
        rrf_scores: dict[str, float] = {}
        hit_map: dict[str, SearchResult] = {}

        def merge_origin(existing: str, new_origin: str) -> str:
            existing_parts = [part for part in existing.split("+") if part]
            if new_origin not in existing_parts:
                existing_parts.append(new_origin)
            return "+".join(existing_parts)

        def apply_rrf(hits: list[SearchResult], origin: str):
            for rank, hit in enumerate(hits):
                key = hit.text[:200]
                if key not in hit_map:
                    hit.origin = origin
                    hit_map[key] = hit
                    rrf_scores[key] = 0.0
                elif hit_map[key].origin != origin:
                    hit_map[key].origin = merge_origin(hit_map[key].origin, origin)
                
                # Standard RRF formula
                rrf_scores[key] += 1.0 / (RRF_K + rank + 1)

        apply_rrf(semantic_hits, "semantic")
        apply_rrf(keyword_hits, "keyword")
        apply_rrf(archive_hits, "archive")

        # 3. Sort by combined RRF score descending
        sorted_rrf_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)

        for key in sorted_rrf_keys:
            if key not in seen_texts:
                seen_texts.add(key)
                merged.append(hit_map[key])
                # Stop once we hit our desired top_k
                if len(merged) >= top_k + len(priority_hits):
                    break

        return merged

    # ── Formatting ────────────────────────────────────────────────────────

    @staticmethod
    def format_results(results: list[SearchResult]) -> str:
        """Wrap results in metadata tags: [Source: name | Page: X]."""
        if not results:
            return "No results found in the local or archive index."

        parts: list[str] = []
        for r in results:
            tag = f"[Source: {r.source_name}"
            if r.page:
                tag += f" | Page: {r.page}"
            tag += f" | Match: {r.origin}]"

            # Truncate very long chunks for the LLM context window
            snippet = r.text
            words = snippet.split()
            if len(words) > config.MAX_CONTEXT_TOKENS // 2:
                snippet = " ".join(words[: config.MAX_CONTEXT_TOKENS // 2]) + " …"

            parts.append(f"{tag}\n{snippet}")

        return "\n\n---\n\n".join(parts)
