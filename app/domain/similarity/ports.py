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

    async def index_many(self, items: list[tuple[str, str]]) -> None:
        """Bulk-index ``(claim_id, descripcion)`` pairs in batched embedding
        requests. Idempotent (upsert), equivalent to calling ``index`` per item
        but with far fewer provider + DB round-trips."""

    async def nearest(self, claim_id: str, top_k: int = 3) -> list[SimilarClaim]:
        """Return top-k similar prior claims, excluding self."""

    async def nearest_by_text(
        self, descripcion: str, *, top_k: int = 3, exclude_claim_id: str | None = None
    ) -> list[SimilarClaim]:
        """Top-k similar claims for a raw narrative, without indexing it first.

        Embeds ``descripcion`` on the fly and queries existing neighbours. Lets a
        claim be scored for similarity before its own row exists (e.g. mid-import,
        before the ``siniestros`` row is committed)."""

    async def max_similarity(self, claim_id: str) -> float:
        """Highest similarity score against any other indexed claim. 0.0 if alone."""
