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

from app.domain.rules.catalog import get_meta
from app.domain.similarity import NarrativeSimilarity
from app.infrastructure.db.models.asegurado import Asegurado
from app.infrastructure.db.models.claim_score import ClaimScore
from app.infrastructure.db.models.documento import Documento
from app.infrastructure.db.models.poliza import Poliza
from app.infrastructure.db.models.proveedor import Proveedor
from app.infrastructure.db.models.siniestro import Siniestro
from app.schemas.claim import ClaimAlert, ClaimDetail
from app.use_cases._signal_map import signals_from_activations
from app.use_cases.claim_score_persist import claim_detail_to_score_row, upsert_claim_score
from app.use_cases.load_dataset._mapping import rows_to_claim_detail
from app.use_cases.score_claim import score_claim
from app.use_cases.score_claim_from_db import build_rule_context_from_db

logger = logging.getLogger(__name__)

_SEVERITY_BY_TIER = {"rojo": "high", "amarillo": "med", "verde": "low"}


async def rescore_all(
    session: AsyncSession,
    *,
    similarity: NarrativeSimilarity | None = None,
    populate_signals_from_existing: bool = True,
) -> dict[str, int]:
    """Recompute and persist a genuine rules-engine score for every claim.

    Args:
        session:                          AsyncSession (committed at the end).
        similarity:                       NarrativeSimilarity port; narrative
                                          signals skipped when None.
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
        ctx = await build_rule_context_from_db(session, detail, similarity=similarity)
        risk = score_claim(detail, ctx=ctx)

        alertas = [
            ClaimAlert(
                code=activation.code,
                puntos=activation.points,
                severidad=_SEVERITY_BY_TIER.get(activation.tier_hint.value, "low"),
                detalle=(
                    meta.short_description
                    if (meta := get_meta(activation.code))
                    else activation.code
                ),
            )
            for activation in risk.activations
        ]
        scored = detail.model_copy(
            update={"score": risk.score, "nivel": risk.tier, "alertas": alertas}
        )
        await upsert_claim_score(session, claim_detail_to_score_row(scored))
        await session.flush()

        processed += 1
        if previous is None or previous.score != risk.score or previous.tier != risk.tier.value:
            changed += 1

    await session.commit()
    logger.info("rescore_all: processed=%d changed=%d", processed, changed)
    return {"processed": processed, "changed": changed}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


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


async def _main() -> None:
    """Run the rescore from the command line against the configured DATABASE_URL."""
    from app.infrastructure.db.engine import create_engine, create_session_factory

    engine = create_engine()
    factory = create_session_factory(engine)
    async with factory() as session:
        counts = await rescore_all(session)
    await engine.dispose()
    print(
        f"rescore_all: processed={counts['processed']} changed={counts['changed']}."
    )


if __name__ == "__main__":
    asyncio.run(_main())
