"""get_claim_detail — fetch one claim and attach rules-engine scores.

**Scoring strategy (double-scoring guard)**:
- If the claim already has ``alertas`` populated (i.e. it came from the
  synthetic dataset, where scores are baked at generation time), return it
  as-is.  Re-running ``score_claim`` via the context-poor
  ``RuleContext.from_claim`` path would clobber the rich demo scores because
  many signal flags (frequency, restrictive lists, similarity) can only be
  derived from the full DB context, not from ``ClaimDetail`` alone.
- If ``alertas`` is empty (un-scored DB claim, future path), run the live
  rules engine as before so new claims always get fresh scores.

ML factors, anomaly score, and similar narratives are left at defaults until
Layer 7 fills the respective ports.

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
    """Return a ClaimDetail with score/nivel/alertas, or None if not found.

    Claims already scored at generation time (non-empty ``alertas``) are
    returned as-is (double-scoring guard).  Un-scored claims are scored live
    via the rules engine.
    """
    claim = await queries.get_detail(claim_id)
    if claim is None:
        return None

    # Double-scoring guard: skip live re-scoring for pre-scored claims.
    # Pre-scored claims have alertas populated by the generator with a full
    # RuleContext; re-scoring here would use only the context-poor from_claim
    # path and would clobber the rich demo scores.
    if claim.alertas:
        return claim

    # Live-scoring path for un-scored DB claims (post-hackathon).
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
