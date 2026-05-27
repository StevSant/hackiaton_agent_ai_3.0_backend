"""import_claims — bulk-upsert use case.

For each ``ClaimDetail`` record:
1. Score it via the rules engine (score_claim).
2. Upsert asegurado → poliza → proveedor → siniestro → documentos → claim_score.
3. Collect per-row errors without aborting the whole batch.

Returns an ``ImportResult`` with counts and error messages.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.claim import ClaimAlert, ClaimDetail
from app.schemas.imports import ImportResult
from app.use_cases.load_dataset._mapping import (
    claim_detail_to_asegurado,
    claim_detail_to_documentos,
    claim_detail_to_poliza,
    claim_detail_to_proveedor,
    claim_detail_to_siniestro,
)

logger = logging.getLogger(__name__)


async def import_claims(
    session: AsyncSession,
    *,
    records: list[ClaimDetail],
) -> ImportResult:
    """Upsert every claim in *records* and return an ``ImportResult``.

    Each record is scored independently; a failure on one record does NOT abort
    the batch — it is collected in ``errors`` and the row is counted in
    ``skipped``.
    """
    imported = 0
    skipped = 0
    errors: list[str] = []

    for record in records:
        try:
            await _upsert_one(session, record)
            imported += 1
        except Exception as exc:  # collect, don't abort the batch
            skipped += 1
            errors.append(f"{record.id}: {exc}")
            logger.warning("import_claims: skipped %s — %s", record.id, exc)

    if imported:
        await session.commit()

    logger.info(
        "import_claims: imported=%d skipped=%d errors=%d",
        imported, skipped, len(errors),
    )
    return ImportResult(imported=imported, skipped=skipped, errors=errors)


async def _upsert_one(session: AsyncSession, claim: ClaimDetail) -> None:
    """Score and upsert a single claim into all relevant tables."""
    # Score the claim so claim_score is populated at import time
    scored = _score_and_annotate(claim)

    # 1. Asegurado (FK parent of Poliza)
    await session.merge(claim_detail_to_asegurado(scored))
    await session.flush()

    # 2. Poliza (FK parent of Siniestro)
    await session.merge(claim_detail_to_poliza(scored))
    await session.flush()

    # 3. Proveedor (independent FK — no child depends on it)
    proveedor = claim_detail_to_proveedor(scored)
    if proveedor is not None:
        await session.merge(proveedor)
        await session.flush()

    # 4. Siniestro
    await session.merge(claim_detail_to_siniestro(scored))
    await session.flush()

    # 5. Documentos
    for doc in claim_detail_to_documentos(scored):
        await session.merge(doc)
    await session.flush()

    # 6. ClaimScore
    score_row = _build_claim_score(scored)
    await session.merge(score_row)
    await session.flush()


def _score_and_annotate(claim: ClaimDetail) -> ClaimDetail:
    """Run score_claim and fold results back into the ClaimDetail.

    If the incoming claim already has alertas (i.e. it was pre-scored), the
    existing score is preserved to avoid clobbering rich archetype scores.
    """
    if claim.alertas:
        # Already scored — trust the incoming data
        return claim

    from app.domain.rules.catalog import get_meta
    from app.domain.rules.context import RuleContext
    from app.use_cases.score_claim import score_claim

    ctx = RuleContext.from_claim(claim)
    risk = score_claim(claim, ctx=ctx)

    _sev = {"rojo": "high", "amarillo": "med", "verde": "low"}
    alertas = [
        ClaimAlert(
            code=a.code,
            puntos=a.points,
            severidad=_sev.get(a.tier_hint.value, "low"),  # AlertSeverity coercion via dict lookup
            detalle=(m.short_description if (m := get_meta(a.code)) else a.code),
        )
        for a in risk.activations
    ]

    return claim.model_copy(
        update={
            "score": risk.score,
            "nivel": risk.tier,
            "alertas": alertas,
        }
    )


def _build_claim_score(claim: ClaimDetail) -> object:
    """Build a ``ClaimScore`` ORM object from an annotated ``ClaimDetail``."""
    from typing import Any

    from app.infrastructure.db.models.claim_score import ClaimScore

    activations_json: list[dict[str, Any]] = [
        {
            "code": a.code,
            "puntos": a.puntos,
            "severidad": a.severidad,
            "detalle": a.detalle,
        }
        for a in claim.alertas
    ]
    ml_factors_json: list[dict[str, Any]] = [
        {
            "feature": f.feature,
            "shap_value": f.shap_value,
            "direction": f.direction,
        }
        for f in claim.ml_factors
    ]
    similar_json: list[dict[str, Any]] = [
        {
            "claim_id": s.claim_id,
            "similarity": s.similarity,
            "snippet": s.snippet,
        }
        for s in claim.similar
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
