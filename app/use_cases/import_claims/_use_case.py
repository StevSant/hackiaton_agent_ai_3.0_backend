"""import_claims — bulk-upsert use case.

For each ``ClaimDetail`` record:
1. Score it via the rules engine (score_claim).
2. Upsert asegurado → poliza → proveedor → siniestro → documentos → claim_score.
3. Collect per-row errors without aborting the whole batch.

Returns an ``ImportResult`` with counts and error messages.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.use_cases.claim_score_persist import (
    claim_detail_to_score_row,
    upsert_claim_score,
)
from app.schemas.claim import ClaimAlert, ClaimDetail
from app.schemas.imports import ImportResult
from app.use_cases.load_dataset._aggregates import compute_aggregates
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
    workspace_id: UUID | None = None,
) -> ImportResult:
    """Upsert every claim in *records* and return an ``ImportResult``."""
    imported = 0
    skipped = 0
    errors: list[str] = []
    claim_ids: list[str] = []

    for record in records:
        try:
            await _upsert_one(session, record, workspace_id=workspace_id)
            imported += 1
            claim_ids.append(record.id)
        except Exception as exc:  # collect, don't abort the batch
            skipped += 1
            errors.append(f"{record.id}: {exc}")
            logger.warning("import_claims: skipped %s — %s", record.id, exc)

    if imported:
        await compute_aggregates(session)
        await session.commit()

    logger.info(
        "import_claims: imported=%d skipped=%d errors=%d",
        imported,
        skipped,
        len(errors),
    )
    return ImportResult(
        imported=imported,
        skipped=skipped,
        errors=errors,
        claim_ids=claim_ids,
    )


async def _upsert_one(
    session: AsyncSession,
    claim: ClaimDetail,
    *,
    workspace_id: UUID | None,
) -> None:
    """Score and upsert a single claim into all relevant tables."""
    scored = _score_and_annotate(claim)

    await session.merge(claim_detail_to_asegurado(scored))
    await session.flush()

    await session.merge(claim_detail_to_poliza(scored))
    await session.flush()

    proveedor = claim_detail_to_proveedor(scored)
    if proveedor is not None:
        await session.merge(proveedor)
        await session.flush()

    await session.merge(
        claim_detail_to_siniestro(scored, workspace_id=workspace_id)
    )
    await session.flush()

    for doc in claim_detail_to_documentos(scored):
        await session.merge(doc)
    await session.flush()

    score_row = claim_detail_to_score_row(scored)
    await upsert_claim_score(session, score_row)
    await session.flush()


def _score_and_annotate(claim: ClaimDetail) -> ClaimDetail:
    """Run score_claim and fold results back into the ClaimDetail."""
    if claim.alertas:
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
            severidad=_sev.get(a.tier_hint.value, "low"),
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
