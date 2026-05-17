"""Helpers for caching and preparing the local sentence-transformer model."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

import config


log = logging.getLogger("uzephyr.embedding_model")
_EMBEDDING_MODEL_MARKER = "modules.json"


@dataclass(frozen=True, slots=True)
class EmbeddingModelPreparation:
    """Preparation result for local embedding-model assets."""

    attempted: bool
    success: bool
    detail: str


def embedding_model_is_cached() -> bool:
    """Return whether the app-managed local embedding model is present on disk."""
    return (config.EMBEDDING_MODEL_DIR / _EMBEDDING_MODEL_MARKER).is_file()


def cache_embedding_model(model: Any | None = None) -> Path:
    """Persist the configured sentence-transformer model into the app-managed cache dir."""
    from sentence_transformers import SentenceTransformer

    model_dir = config.EMBEDDING_MODEL_DIR
    model_dir.parent.mkdir(parents=True, exist_ok=True)

    if model is None:
        log.info("Caching embedding model '%s' into %s", config.EMBEDDING_MODEL_NAME, model_dir)
        model = SentenceTransformer(config.EMBEDDING_MODEL_NAME)

    model.save(str(model_dir))
    return model_dir


async def prepare_embedding_model() -> EmbeddingModelPreparation:
    """Ensure the configured embedding model is cached in the app-managed local dir."""
    if embedding_model_is_cached():
        return EmbeddingModelPreparation(
            attempted=False,
            success=True,
            detail=f"Embedding model is already cached at {config.EMBEDDING_MODEL_DIR}.",
        )

    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, cache_embedding_model)
    except Exception as exc:
        return EmbeddingModelPreparation(
            attempted=True,
            success=False,
            detail=f"Embedding model preparation failed: {exc}",
        )

    if embedding_model_is_cached():
        return EmbeddingModelPreparation(
            attempted=True,
            success=True,
            detail=f"Embedding model cached at {config.EMBEDDING_MODEL_DIR}.",
        )

    return EmbeddingModelPreparation(
        attempted=True,
        success=False,
        detail=(
            f"Expected embedding model cache at {config.EMBEDDING_MODEL_DIR}, "
            "but it is still missing after preparation."
        ),
    )


def describe_embedding_model_preparation(preparation: EmbeddingModelPreparation) -> list[str]:
    """Render embedding-model preparation in a compact CLI-friendly format."""
    return [f"Embedding model: {preparation.detail}"]