"""In-memory `NarrativeSimilarity` impl — 2-hr fallback if pgvector blocks (spec §8).

Stores normalized embeddings in a plain numpy matrix; cosine == dot product on
normalized vectors. Excludes self from neighbor results.

Switched on via `settings.VECTOR_STORE = "in_memory"`.
"""

from __future__ import annotations

import asyncio

import numpy as np

from app.infrastructure.embeddings import EmbeddingsProvider
from app.schemas.risk import SimilarClaim


class InMemoryNarrativeSimilarity:
    """`NarrativeSimilarity` impl backed by an in-process numpy matrix."""

    def __init__(self, embeddings: EmbeddingsProvider) -> None:
        self._embeddings = embeddings
        self._claim_ids: list[str] = []
        self._descripciones: list[str] = []
        self._matrix: np.ndarray | None = None  # shape (N, D), normalized
        self._lock = asyncio.Lock()

    async def index(self, claim_id: str, descripcion: str) -> None:
        async with self._lock:
            vector = (await self._embeddings.embed([descripcion]))[0]
            arr = np.asarray(vector, dtype=np.float32)[None, :]
            if claim_id in self._claim_ids:
                idx = self._claim_ids.index(claim_id)
                self._descripciones[idx] = descripcion
                if self._matrix is not None:
                    self._matrix[idx] = arr[0]
            else:
                self._claim_ids.append(claim_id)
                self._descripciones.append(descripcion)
                if self._matrix is None:
                    self._matrix = arr
                else:
                    self._matrix = np.vstack([self._matrix, arr])

    async def nearest(self, claim_id: str, top_k: int = 3) -> list[SimilarClaim]:
        if self._matrix is None or claim_id not in self._claim_ids:
            return []
        idx = self._claim_ids.index(claim_id)
        sims = (self._matrix @ self._matrix[idx]).astype(float)
        # exclude self
        sims[idx] = -1.0
        order = np.argsort(-sims)[:top_k]
        return [
            SimilarClaim(
                claim_id=self._claim_ids[int(i)],
                similarity=float(np.clip(sims[int(i)], 0.0, 1.0)),
                snippet=self._descripciones[int(i)][:160],
            )
            for i in order
            if sims[int(i)] > 0
        ]

    async def max_similarity(self, claim_id: str) -> float:
        nearest = await self.nearest(claim_id, top_k=1)
        return nearest[0].similarity if nearest else 0.0
