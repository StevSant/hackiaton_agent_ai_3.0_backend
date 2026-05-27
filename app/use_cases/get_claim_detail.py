"""get_claim_detail — fetch one claim and attach live rules-engine scores.

Runs score_claim on the fly so the served scores reflect REAL rules-engine
output rather than the fixture's mock numbers.  ML factors, anomaly score, and
similar narratives are left at defaults until Layer 7 fills the respective ports.

Returns None when the claim is not found (caller maps to 404).
"""

from __future__ import annotations

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.domain.rules.catalog import get_meta
from app.domain.rules.context import RuleContext
from app.schemas.claim import ClaimAlert, ClaimDetail
from app.schemas.risk import Tier
from app.use_cases.score_claim import score_claim


def _tier_to_severidad(tier: Tier) -> str:
    """Map a rule tier_hint to the UI severidad literal."""
    return {"rojo": "high", "amarillo": "med", "verde": "low"}[tier.value]


async def get_claim_detail(queries: ClaimQueries, claim_id: str) -> ClaimDetail | None:
    """Return a ClaimDetail with live score/nivel/alertas, or None if not found."""
    claim = await queries.get_detail(claim_id)
    if claim is None:
        return None

    ctx = RuleContext.from_claim(claim)
    risk = score_claim(claim, ctx=ctx)

    # Project RuleActivation list → ClaimAlert list
    alertas: list[ClaimAlert] = []
    for activation in risk.activations:
        meta = get_meta(activation.code)
        detalle = meta.short_description if meta is not None else activation.code
        severidad = _tier_to_severidad(activation.tier_hint)
        alertas.append(
            ClaimAlert(
                code=activation.code,
                puntos=activation.points,
                severidad=severidad,
                detalle=detalle,
            )
        )

    return claim.model_copy(
        update={
            "score": risk.score,
            "nivel": risk.tier,
            "alertas": alertas,
            "ml_factors": risk.ml_factors,
            "similar": risk.similar,
            "anomaly_score": risk.anomaly_score,
        }
    )
