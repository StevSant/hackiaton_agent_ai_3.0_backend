"""Persist claim_scores rows — shared by import and live rescore paths."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.rules.catalog import get_meta
from app.domain.rules.context import RuleContext
from app.infrastructure.db.models.claim_score import ClaimScore
from app.infrastructure.db.models.documento import Documento
from app.infrastructure.db.models.poliza import Poliza
from app.infrastructure.db.models.proveedor import Proveedor
from app.infrastructure.db.models.siniestro import Siniestro
from app.infrastructure.reviews.db_reviews_store import DbReviewsStore
from app.schemas.claim import ClaimAlert, ClaimDetail
from app.use_cases.load_dataset._mapping import rows_to_claim_detail
from app.use_cases.reviews.auto_escalate_rojo import auto_escalate_rojo
from app.use_cases.score_claim import score_claim


async def upsert_claim_score(session: AsyncSession, score_row: ClaimScore) -> None:
    """Update an existing score row or insert when the claim is new."""
    existing = (
        await session.execute(
            select(ClaimScore).where(ClaimScore.claim_id == score_row.claim_id)
        )
    ).scalars().first()
    if existing is None:
        session.add(score_row)
        return

    existing.score = score_row.score
    existing.tier = score_row.tier
    existing.activations = score_row.activations
    existing.ml_probability = score_row.ml_probability
    existing.ml_factors = score_row.ml_factors
    existing.anomaly_score = score_row.anomaly_score
    existing.similar = score_row.similar
    existing.computed_at = score_row.computed_at


def claim_detail_to_score_row(claim: ClaimDetail) -> ClaimScore:
    """Build a ClaimScore ORM row from a scored ClaimDetail."""
    activations_json = [
        {
            "code": alerta.code,
            "puntos": alerta.puntos,
            "severidad": alerta.severidad,
            "detalle": alerta.detalle,
        }
        for alerta in claim.alertas
    ]
    ml_factors_json = [
        {
            "feature": factor.feature,
            "shap_value": factor.shap_value,
            "direction": factor.direction,
        }
        for factor in claim.ml_factors
    ]
    similar_json = [
        {
            "claim_id": similar.claim_id,
            "similarity": similar.similarity,
            "snippet": similar.snippet,
        }
        for similar in claim.similar
    ]
    return ClaimScore(
        claim_id=claim.id,
        score=claim.score,
        tier=claim.nivel.value,
        activations=activations_json,
        ml_probability=claim.ml_probability,
        ml_factors=ml_factors_json,
        anomaly_score=claim.anomaly_score,
        similar=similar_json,
        computed_at=datetime.now(tz=UTC),
    )


async def rescore_claim_persisted(session: AsyncSession, claim_id: str) -> ClaimDetail:
    """Re-run the rules engine from current DB rows and persist claim_scores."""
    sin = await session.get(Siniestro, claim_id)
    if sin is None:
        raise ValueError(f"Siniestro {claim_id!r} no encontrado")

    pol = await session.get(Poliza, sin.id_poliza)
    score_row = (
        await session.execute(
            select(ClaimScore).where(ClaimScore.claim_id == claim_id)
        )
    ).scalars().first()
    documentos = list(
        (
            await session.execute(
                select(Documento).where(Documento.id_siniestro == claim_id)
            )
        ).scalars().all()
    )
    proveedor = (
        await session.get(Proveedor, sin.beneficiario) if sin.beneficiario else None
    )

    detail = rows_to_claim_detail(sin, pol, score_row, documentos, proveedor)
    ctx = RuleContext.from_claim(detail)
    risk = score_claim(detail, ctx=ctx)

    _sev = {"rojo": "high", "amarillo": "med", "verde": "low"}
    alertas = [
        ClaimAlert(
            code=activation.code,
            puntos=activation.points,
            severidad=_sev.get(activation.tier_hint.value, "low"),
            detalle=(
                meta.short_description
                if (meta := get_meta(activation.code))
                else activation.code
            ),
        )
        for activation in risk.activations
    ]

    scored = detail.model_copy(
        update={
            "score": risk.score,
            "nivel": risk.tier,
            "alertas": alertas,
            # This path has no similarity port (score_claim leaves risk.similar
            # empty), so preserve the neighbours already persisted rather than
            # wiping the "Narrativas similares" panel on a document re-score.
            "similar": detail.similar,
        }
    )
    await upsert_claim_score(session, claim_detail_to_score_row(scored))

    # Auto-escalate rojos that are still pendiente. The reviews store reads /
    # writes in the same session so it shares the flush below.
    await auto_escalate_rojo(
        DbReviewsStore(session),
        claim_id,
        tier=risk.tier,
        score=risk.score,
    )

    await session.flush()
    return scored
