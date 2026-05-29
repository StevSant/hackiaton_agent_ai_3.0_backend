"""In-memory `NarrativeSimilarity` impl — 2-hr fallback if pgvector blocks (spec §8).

Stores normalized embeddings in a plain numpy matrix; cosine == dot product on
normalized vectors. Excludes self from neighbor results.

Switched on via `settings.VECTOR_STORE = "in_memory"`.
"""

from __future__ import annotations

import asyncio

import numpy as np

from app.domain.similarity import NarrativeSimilarity
from app.infrastructure.embeddings import EmbeddingsProvider
from app.schemas.risk import SimilarClaim


class InMemoryNarrativeSimilarity(NarrativeSimilarity):
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
            self._upsert(claim_id, descripcion, np.asarray(vector, dtype=np.float32))

    async def index_many(self, items: list[tuple[str, str]]) -> None:
        if not items:
            return
        async with self._lock:
            # Single batched embed call, then upsert each row.
            vectors = await self._embeddings.embed([d for _, d in items])
            for (claim_id, descripcion), vector in zip(items, vectors, strict=True):
                self._upsert(claim_id, descripcion, np.asarray(vector, dtype=np.float32))

    def _upsert(self, claim_id: str, descripcion: str, arr: np.ndarray) -> None:
        if claim_id in self._claim_ids:
            idx = self._claim_ids.index(claim_id)
            self._descripciones[idx] = descripcion
            if self._matrix is not None:
                self._matrix[idx] = arr
        else:
            self._claim_ids.append(claim_id)
            self._descripciones.append(descripcion)
            row = arr[None, :]
            self._matrix = row if self._matrix is None else np.vstack([self._matrix, row])

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

    async def nearest_by_text(
        self, descripcion: str, *, top_k: int = 3, exclude_claim_id: str | None = None
    ) -> list[SimilarClaim]:
        if self._matrix is None:
            return []
        vector = (await self._embeddings.embed([descripcion]))[0]
        query = np.asarray(vector, dtype=np.float32)
        sims = (self._matrix @ query).astype(float)
        order = np.argsort(-sims)
        out: list[SimilarClaim] = []
        for i in order:
            cid = self._claim_ids[int(i)]
            if cid == exclude_claim_id or sims[int(i)] <= 0:
                continue
            out.append(
                SimilarClaim(
                    claim_id=cid,
                    similarity=float(np.clip(sims[int(i)], 0.0, 1.0)),
                    snippet=self._descripciones[int(i)][:160],
                )
            )
            if len(out) >= top_k:
                break
        return out

    async def max_similarity(self, claim_id: str) -> float:
        nearest = await self.nearest(claim_id, top_k=1)
        return nearest[0].similarity if nearest else 0.0
