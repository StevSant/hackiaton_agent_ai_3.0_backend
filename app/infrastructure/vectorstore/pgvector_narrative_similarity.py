"""pgvector-backed `NarrativeSimilarity` impl — primary similarity store.

Schema (backend CLAUDE.md §8):

    create extension if not exists vector;
    create table claim_narratives (
        id          uuid primary key default gen_random_uuid(),
        claim_id    text not null references siniestros(id_siniestro) on delete cascade,
        content     text not null,
        embedding   vector(384) not null,
        created_at  timestamptz not null default now()
    );
    create index on claim_narratives using hnsw (embedding vector_cosine_ops);
    create index on claim_narratives (claim_id);

Migration creation lives in Miquel's lane (V1.4 + V6). This adapter assumes the
table exists; it operates purely through `AsyncSession`.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.similarity import NarrativeSimilarity
from app.infrastructure.embeddings import EmbeddingsProvider
from app.schemas.risk import SimilarClaim


class PgVectorNarrativeSimilarity(NarrativeSimilarity):
    """`NarrativeSimilarity` impl backed by pgvector + cosine HNSW index."""

    def __init__(self, embeddings: EmbeddingsProvider, session_factory: object) -> None:
        # session_factory is `async_sessionmaker[AsyncSession]` — kept as object
        # to avoid coupling import-time to SQLAlchemy specifics.
        self._embeddings = embeddings
        self._session_factory = session_factory

    def _session(self) -> AsyncSession:
        return self._session_factory()  # type: ignore[no-any-return,operator]

    async def index(self, claim_id: str, descripcion: str) -> None:
        vector = (await self._embeddings.embed([descripcion]))[0]
        async with self._session() as session:
            await session.execute(
                text(
                    """
                    insert into claim_narratives (claim_id, content, embedding)
                    values (:claim_id, :content, :embedding)
                    on conflict (claim_id) do update
                    set content = excluded.content,
                        embedding = excluded.embedding
                    """
                ),
                {"claim_id": claim_id, "content": descripcion, "embedding": vector},
            )
            await session.commit()

    async def nearest(self, claim_id: str, top_k: int = 3) -> list[SimilarClaim]:
        async with self._session() as session:
            result = await session.execute(
                text(
                    """
                    with anchor as (
                        select embedding from claim_narratives where claim_id = :claim_id
                    )
                    select n.claim_id,
                           1 - (n.embedding <=> (select embedding from anchor)) as similarity,
                           n.content
                    from claim_narratives n
                    where n.claim_id <> :claim_id
                      and exists (select 1 from anchor)
                    order by n.embedding <=> (select embedding from anchor) asc
                    limit :top_k
                    """
                ),
                {"claim_id": claim_id, "top_k": top_k},
            )
            return [
                SimilarClaim(
                    claim_id=row.claim_id,
                    similarity=max(0.0, min(1.0, float(row.similarity))),
                    snippet=(row.content or "")[:160],
                )
                for row in result
            ]

    async def max_similarity(self, claim_id: str) -> float:
        nearest = await self.nearest(claim_id, top_k=1)
        return nearest[0].similarity if nearest else 0.0
