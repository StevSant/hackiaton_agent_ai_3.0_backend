"""rescore_all — recompute every claim's risk score from the rules engine.

Walks every ``Siniestro`` and replaces its persisted ``claim_scores`` row with a
GENUINE output of ``score_claim`` computed from the claim's data + relationships
+ stored ``signals`` facts — never a hand-authored score.

When ``populate_signals_from_existing`` is set and a claim's ``signals`` is still
empty, the curated scenario is preserved by back-filling ``signals`` from the
facts implied by the existing activations (see ``_signal_map``). This lets the
canonical engine reproduce the demo cases from facts before the curated codes
are discarded.

Usage (CLI):
    uv run python -m app.use_cases.rescore_all

Usage (programmatic):
    await rescore_all(session, similarity=similarity_port)
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.similarity import NarrativeSimilarity
from app.domain.vehicle_identity import VehicleDecoder
from app.infrastructure.db.models.asegurado import Asegurado
from app.infrastructure.db.models.claim_score import ClaimScore
from app.infrastructure.db.models.documento import Documento
from app.infrastructure.db.models.poliza import Poliza
from app.infrastructure.db.models.proveedor import Proveedor
from app.infrastructure.db.models.siniestro import Siniestro
from app.schemas.claim import ClaimDetail
from app.use_cases._rescore_one import rescore_one
from app.use_cases._signal_map import signals_from_activations
from app.use_cases.load_dataset._mapping import rows_to_claim_detail

logger = logging.getLogger(__name__)


async def rescore_all(
    session: AsyncSession,
    *,
    similarity: NarrativeSimilarity | None = None,
    decoder: VehicleDecoder | None = None,
    populate_signals_from_existing: bool = True,
) -> dict[str, int]:
    """Recompute and persist a genuine rules-engine score for every claim.

    Args:
        session:                          AsyncSession (committed at the end).
        similarity:                       NarrativeSimilarity port; narrative
                                          signals skipped when None.
        decoder:                          VehicleDecoder port; FS-15
                                          vehicle-identity check skipped when None.
        populate_signals_from_existing:   When True, back-fill an empty
                                          ``signals`` from the claim's current
                                          activations before re-scoring so the
                                          curated scenario is preserved as facts.

    Returns:
        ``{"processed": N, "changed": M}`` — total claims and how many ended up
        with a different (score, tier) than before.
    """
    sins: list[Siniestro] = list(
        (await session.execute(select(Siniestro))).scalars().all()
    )

    # Index every narrative FIRST so the similarity corpus exists before any
    # nearest() lookup runs. Without this pre-pass, the very first claims scored
    # would compare against a half-built (or empty) index and FS-13 / the
    # "Narrativas similares" panel would be unreliable for the whole batch.
    await _index_narratives(sins, similarity)

    processed = 0
    changed = 0
    for sin in sins:
        previous = await _existing_score(session, sin.id_siniestro)

        if populate_signals_from_existing and not (sin.signals or {}):
            existing_activations = previous.activations if previous else []
            backfilled = signals_from_activations(existing_activations)
            if backfilled:
                sin.signals = backfilled
                await session.flush()

        detail = await _hydrate(session, sin, previous)
        _scored, risk = await rescore_one(
            session, detail, similarity=similarity, decoder=decoder
        )

        processed += 1
        if previous is None or previous.score != risk.score or previous.tier != risk.tier.value:
            changed += 1

    await session.commit()
    logger.info("rescore_all: processed=%d changed=%d", processed, changed)
    return {"processed": processed, "changed": changed}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Narratives shorter than this are too thin to embed meaningfully — mirrors the
# import-stream / score_from_db guard so all paths index the same population.
_MIN_NARRATIVE_LEN = 30


async def _index_narratives(
    sins: list[Siniestro], similarity: NarrativeSimilarity | None
) -> None:
    """Embed + store every claim's narrative so the corpus exists before scoring."""
    if similarity is None:
        return
    indexed = 0
    for sin in sins:
        descripcion = sin.descripcion or ""
        if len(descripcion) < _MIN_NARRATIVE_LEN:
            continue
        try:
            await similarity.index(sin.id_siniestro, descripcion)
            indexed += 1
        except Exception as exc:
            logger.warning(
                "rescore_all: narrative index failed for %s: %s", sin.id_siniestro, exc
            )
    logger.info("rescore_all: indexed %d narratives", indexed)


async def _existing_score(session: AsyncSession, claim_id: str) -> ClaimScore | None:
    return (
        await session.execute(
            select(ClaimScore).where(ClaimScore.claim_id == claim_id)
        )
    ).scalars().first()


async def _hydrate(
    session: AsyncSession, sin: Siniestro, score_row: ClaimScore | None
) -> ClaimDetail:
    """Assemble a ClaimDetail from a Siniestro + its related rows."""
    pol: Poliza | None = await session.get(Poliza, sin.id_poliza)
    docs = list(
        (
            await session.execute(
                select(Documento).where(Documento.id_siniestro == sin.id_siniestro)
            )
        ).scalars().all()
    )
    proveedor: Proveedor | None = (
        await session.get(Proveedor, sin.beneficiario) if sin.beneficiario else None
    )
    asegurado: Asegurado | None = await session.get(Asegurado, sin.id_asegurado)
    return rows_to_claim_detail(
        sin, pol, score_row, docs, proveedor, asegurado=asegurado
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_similarity(session_factory: object) -> NarrativeSimilarity:
    """Construct the pgvector similarity port for the CLI rebuild.

    Mirrors ``main.lifespan`` / ``deps._fallback_embeddings``: OpenAI embeddings
    when configured, else the local sentence-transformers model. Building it here
    (rather than importing from ``api.deps``) keeps the use-case layer free of an
    upward dependency on the API layer.
    """
    from app.core.config import settings
    from app.infrastructure.embeddings import (
        EmbeddingsProvider,
        SentenceTransformersAdapter,
        build_openai_embeddings_adapter,
    )
    from app.infrastructure.vectorstore.pgvector_narrative_similarity import (
        PgVectorNarrativeSimilarity,
    )

    embeddings: EmbeddingsProvider
    if settings.EMBEDDINGS_PROVIDER == "openai" and settings.OPENAI_API_KEY is not None:
        embeddings = build_openai_embeddings_adapter()
    else:
        embeddings = SentenceTransformersAdapter(model_name=settings.EMBEDDINGS_MODEL)
    return PgVectorNarrativeSimilarity(embeddings, session_factory)


async def _main() -> None:
    """Run the rescore from the command line against the configured DATABASE_URL.

    The CLI uses the offline ``RegistryVehicleDecoder`` so the batch walk decodes
    synthetic chassis locally (FS-15) without any network call, and builds the
    pgvector similarity port so the narrative corpus is indexed and FS-13 / the
    "Narrativas similares" panel get genuine matches.
    """
    from app.infrastructure.db.engine import create_engine, create_session_factory
    from app.infrastructure.vehicle_decoder import RegistryVehicleDecoder

    engine = create_engine()
    factory = create_session_factory(engine)
    decoder = RegistryVehicleDecoder()
    similarity = _build_similarity(factory)
    async with factory() as session:
        counts = await rescore_all(session, similarity=similarity, decoder=decoder)
    await engine.dispose()
    print(
        f"rescore_all: processed={counts['processed']} changed={counts['changed']}."
    )


if __name__ == "__main__":
    asyncio.run(_main())
