"""reanalyze_claim — on-demand single-claim re-analysis from the DB.

Recomputes one claim's risk with the GENUINE, relationship-driven pipeline
(``build_rule_context_from_db`` + ``score_claim``), persists the fresh
``claim_scores`` row, re-runs the rojo auto-escalation, and optionally enriches
ML / anomaly fields — all in one committed transaction.

This is the engine behind ``POST /claims/{id}/rescore`` ("Re-analizar caso").
It deliberately mirrors a single iteration of ``rescore_all`` (via the shared
``rescore_one`` core) so the on-demand button and the batch walk can never drift.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.anomaly import AnomalyDetector
from app.domain.ml import FraudClassifier
from app.domain.similarity import NarrativeSimilarity
from app.domain.vehicle_identity import VehicleDecoder
from app.infrastructure.db.models.asegurado import Asegurado
from app.infrastructure.db.models.claim_score import ClaimScore
from app.infrastructure.db.models.documento import Documento
from app.infrastructure.db.models.poliza import Poliza
from app.infrastructure.db.models.proveedor import Proveedor
from app.infrastructure.db.models.siniestro import Siniestro
from app.infrastructure.reviews.db_reviews_store import DbReviewsStore
from app.schemas.claim import ClaimDetail
from app.use_cases._rescore_one import rescore_one
from app.use_cases.enrich_claim_score import enrich_claim_score
from app.use_cases.load_dataset._mapping import rows_to_claim_detail
from app.use_cases.reviews.auto_escalate_rojo import auto_escalate_rojo

logger = logging.getLogger(__name__)


async def reanalyze_claim(
    session: AsyncSession,
    claim_id: str,
    *,
    similarity: NarrativeSimilarity | None = None,
    classifier: FraudClassifier | None = None,
    detector: AnomalyDetector | None = None,
    decoder: VehicleDecoder | None = None,
) -> ClaimDetail | None:
    """Re-score one claim from current DB state and persist the result.

    Args:
        session:    AsyncSession (committed here on success).
        claim_id:   The ``siniestros.id_siniestro`` to re-analyze.
        similarity: NarrativeSimilarity port; narrative signals skipped when None.
        classifier: Supervised fraud classifier; ML fields left default when None.
        detector:   Anomaly detector; anomaly fields left default when None.
        decoder:    VehicleDecoder port; FS-15 vehicle-identity check skipped
                    when None.

    Returns:
        The updated ClaimDetail (score / nivel / alertas + any ML enrichment), or
        None when the Siniestro does not exist (caller maps to 404).
    """
    sin: Siniestro | None = await session.get(Siniestro, claim_id)
    if sin is None:
        return None

    detail = await _hydrate(session, sin)
    scored, risk = await rescore_one(
        session, detail, similarity=similarity, decoder=decoder
    )

    # Auto-escalate rojos still in pendiente; the reviews store shares this session.
    await auto_escalate_rojo(
        DbReviewsStore(session),
        claim_id,
        tier=risk.tier,
        score=risk.score,
    )
    await session.commit()

    # ML / anomaly enrichment is pass-through when both ports are None.
    return await enrich_claim_score(scored, classifier=classifier, detector=detector)


async def _hydrate(session: AsyncSession, sin: Siniestro) -> ClaimDetail:
    """Assemble a ClaimDetail from a Siniestro + its related rows."""
    pol: Poliza | None = await session.get(Poliza, sin.id_poliza)
    score_row: ClaimScore | None = (
        await session.execute(
            select(ClaimScore).where(ClaimScore.claim_id == sin.id_siniestro)
        )
    ).scalars().first()
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
    return rows_to_claim_detail(sin, pol, score_row, docs, proveedor, asegurado=asegurado)
