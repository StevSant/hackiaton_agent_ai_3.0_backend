"""sentence-transformers `EmbeddingsProvider` impl.

Default model: `paraphrase-multilingual-MiniLM-L12-v2` (384-dim, Spanish-aware).
Set via `settings.EMBEDDINGS_MODEL`. Model load is sync + CPU-heavy, so we push it
to `asyncio.to_thread` (root CLAUDE.md §2 "Use async end-to-end").

The encoder is cached on the adapter instance — load once at app startup via the
FastAPI lifespan.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.infrastructure.embeddings.ports import EmbeddingsProvider

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class SentenceTransformersAdapter(EmbeddingsProvider):
    """`EmbeddingsProvider` impl backed by sentence-transformers."""

    def __init__(self, model_name: str) -> None:
        # Lazy-import so the module is importable without the heavy ML deps loaded.
        from sentence_transformers import SentenceTransformer

        self._model: SentenceTransformer = SentenceTransformer(model_name)
        self._model_name = model_name

    @property
    def dimension(self) -> int:
        return int(self._model.get_sentence_embedding_dimension() or 0)

    @property
    def model_name(self) -> str:
        return self._model_name

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await asyncio.to_thread(self._encode_sync, texts)

    def _encode_sync(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,  # cosine == dot on normalized vectors
            show_progress_bar=False,
        )
        return vectors.tolist()
