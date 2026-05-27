"""score_claim — pure synchronous use case: run all fraud rules → ClaimRiskScore.

ML probability, anomaly score, and similar narratives are left empty (None / []).
Layer 7 fills them via the respective ports before or after calling this function.

Usage:
    score = score_claim(claim)                         # derives ctx from claim
    score = score_claim(claim, ctx=enriched_context)   # use pre-built context
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.rules.aggregator import aggregate
from app.domain.rules.catalog import all_rules
from app.domain.rules.context import RuleContext
from app.schemas.claim import ClaimDetail
from app.schemas.risk import ClaimRiskScore, RuleActivation


def score_claim(
    claim: ClaimDetail,
    ctx: RuleContext | None = None,
) -> ClaimRiskScore:
    """Evaluate all 21 fraud rules against *claim* and return a ClaimRiskScore.

    Args:
        claim: Full claim detail (the canonical input shape for rules).
        ctx:   Pre-built RuleContext. When None, derived via RuleContext.from_claim(claim).

    Returns:
        ClaimRiskScore with score, tier, activations, and computed_at filled.
        ml_probability, ml_factors, anomaly_score, similar are left at defaults
        (None / []) — Layer 7 populates them.
    """
    if ctx is None:
        ctx = RuleContext.from_claim(claim)

    activations: list[RuleActivation] = []
    for rule in all_rules():
        result = rule.evaluate(claim, ctx)
        if result is not None:
            activations.append(result)

    score, tier = aggregate(activations)

    return ClaimRiskScore(
        score=score,
        tier=tier,
        activations=activations,
        computed_at=datetime.now(tz=UTC),
    )
