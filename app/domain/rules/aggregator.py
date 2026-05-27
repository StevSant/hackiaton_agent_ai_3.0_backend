"""Aggregator: combines rule activations → (score, tier).

Algorithm:
1. Sum FS-* points (additive signals); cap at 100.
2. Derive base tier from score via score_to_tier.
3. Apply hard-rule overrides:
   - Any RF-01..04 → force tier = rojo (regardless of score).
   - Any RF-05..07 → floor tier at amarillo (only if base < amarillo).
4. Final tier = max(hard_floor, score_to_tier(score)).
"""

from __future__ import annotations

from app.domain.rules.tier import score_to_tier
from app.schemas.risk import RuleActivation, Tier

# Codes that force rojo
_ROJO_HARD: frozenset[str] = frozenset({"RF-01", "RF-02", "RF-03", "RF-04"})
# Codes that floor at amarillo
_AMARILLO_HARD: frozenset[str] = frozenset({"RF-05", "RF-06", "RF-07"})

_TIER_ORDER: dict[Tier, int] = {Tier.verde: 0, Tier.amarillo: 1, Tier.rojo: 2}


def _higher_tier(a: Tier, b: Tier) -> Tier:
    """Return whichever tier is higher risk."""
    return a if _TIER_ORDER[a] >= _TIER_ORDER[b] else b


def aggregate(activations: list[RuleActivation]) -> tuple[int, Tier]:
    """Compute final (score, tier) from a list of activations.

    Returns:
        score: int in [0, 100]
        tier: Tier (verde / amarillo / rojo)
    """
    # 1. Sum additive FS points, cap at 100
    raw_score = sum(a.points for a in activations if a.code.startswith("FS-"))
    score = min(raw_score, 100)

    # 2. Base tier from score
    tier = score_to_tier(score)

    # 3. Hard-rule overrides
    fired_codes = {a.code for a in activations}

    if fired_codes & _ROJO_HARD:
        tier = Tier.rojo
    elif fired_codes & _AMARILLO_HARD:
        tier = _higher_tier(tier, Tier.amarillo)

    return score, tier
