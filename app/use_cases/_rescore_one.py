"""_rescore_one — shared per-claim re-scoring core.

Both the batch ``rescore_all`` walk and the on-demand ``reanalyze_claim`` route
need the same canonical sequence: build the relationship-driven RuleContext from
the database, run ``score_claim``, map the activations to canonical
``ClaimAlert`` rows, and persist the resulting ``claim_scores`` row. Centralising
it here keeps the two callers byte-for-byte consistent — neither hand-authors a
score, both go through ``build_rule_context_from_db`` + ``score_claim``.

The helper FLUSHES but never commits — the caller owns the transaction boundary
(``rescore_all`` commits once at the end of the walk; ``reanalyze_claim`` commits
after auto-escalation).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.rules.catalog import get_meta
from app.domain.similarity import NarrativeSimilarity
from app.domain.vehicle_identity import VehicleDecoder
from app.schemas.claim import ClaimAlert, ClaimDetail
from app.schemas.risk import ClaimRiskScore
from app.use_cases.claim_score_persist import (
    claim_detail_to_score_row,
    upsert_claim_score,
)
from app.use_cases.score_claim import score_claim
from app.use_cases.score_claim_from_db import build_rule_context_from_db

_SEVERITY_BY_TIER = {"rojo": "high", "amarillo": "med", "verde": "low"}


async def rescore_one(
    session: AsyncSession,
    detail: ClaimDetail,
    *,
    similarity: NarrativeSimilarity | None = None,
    decoder: VehicleDecoder | None = None,
) -> tuple[ClaimDetail, ClaimRiskScore]:
    """Re-score one hydrated claim from DB relationships and persist its row.

    Args:
        session:    AsyncSession (flushed here, NOT committed — caller commits).
        detail:     Hydrated ClaimDetail (source of the derivable context base).
        similarity: NarrativeSimilarity port; narrative signals skipped when None.
        decoder:    VehicleDecoder port; FS-15 vehicle-identity check skipped
                    when None.

    Returns:
        ``(scored_detail, risk)`` — the ClaimDetail with score/nivel/alertas set,
        and the raw ``ClaimRiskScore`` produced by the engine.
    """
    ctx = await build_rule_context_from_db(
        session, detail, similarity=similarity, decoder=decoder
    )
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
    return scored, risk
