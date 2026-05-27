from typing import Protocol, runtime_checkable

from app.schemas.risk import SimilarClaim


@runtime_checkable
class NarrativeSimilarity(Protocol):
    """Top-k narrative similarity over `siniestros.descripcion`.

    Primary impl: pgvector cosine over sentence-transformer embeddings.
    Fallback impl: in-memory numpy cosine. Both live under `app/infrastructure/vectorstore/`.

    Powers FS-13 (similar narratives) — fires when top-1 similarity > 0.85.
    """

    async def index(self, claim_id: str, descripcion: str) -> None:
        """Embed and store the narrative for a claim. Idempotent (upsert)."""

    async def nearest(self, claim_id: str, top_k: int = 3) -> list[SimilarClaim]:
        """Return top-k similar prior claims, excluding self."""

    async def max_similarity(self, claim_id: str) -> float:
        """Highest similarity score against any other indexed claim. 0.0 if alone."""
