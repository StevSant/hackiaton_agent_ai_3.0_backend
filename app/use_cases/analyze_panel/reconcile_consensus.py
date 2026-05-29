"""Reconcile the moderator's free-form consensus with the deterministic motor.

The moderator emits ``nivel_de_acuerdo`` and ``posible_falso_positivo`` as raw
LLM outputs — nothing forces them to agree with the engine's facts. That let the
panel stamp "posible falso positivo / 50%" onto a hard-rule ROJO (e.g. RF-03
lista restrictiva), contradicting both the motor and its own summary text.

This recomputes agreement from the specialists' actual votes and gates the
false-positive flag so it can only fire when the panel genuinely lands *below*
the motor with no hard rule in play. Advisory only — never touches the score.
"""

from __future__ import annotations

from app.schemas.claim import ClaimDetail
from app.schemas.panel import PanelConsensus, SpecialistRebuttal, SpecialistVerdict
from app.schemas.risk import Tier

_TIER_RANK = {Tier.verde: 0, Tier.amarillo: 1, Tier.rojo: 2}


def reconcile_consensus(
    consensus: PanelConsensus,
    claim: ClaimDetail,
    verdicts: dict[str, SpecialistVerdict],
    rebuttals: dict[str, SpecialistRebuttal],
) -> PanelConsensus:
    """Return a consensus whose agreement % and FP flag match deterministic facts."""
    # Each specialist's final stance: the R2 update if it replied, else its R1 vote.
    final_levels = [
        rebuttals[aid].nivel_actualizado if aid in rebuttals else v.nivel
        for aid, v in verdicts.items()
    ]

    update: dict[str, object] = {}

    # Agreement = share of specialists whose final level equals the consensus.
    if final_levels:
        matches = sum(1 for lvl in final_levels if lvl == consensus.nivel_final)
        update["nivel_de_acuerdo"] = matches / len(final_levels)

    # A confirmed/raised level — or any hard-rule case — can never be a false
    # positive. The flag only survives when the panel lands below the motor and
    # no hard RF rule fired (the genuine "engine may have over-marked" case).
    has_hard_rule = any(a.code.startswith("RF-") for a in claim.alertas)
    panel_below_motor = _TIER_RANK[consensus.nivel_final] < _TIER_RANK[claim.nivel]
    update["posible_falso_positivo"] = (
        consensus.posible_falso_positivo and not has_hard_rule and panel_below_motor
    )

    return consensus.model_copy(update=update)
