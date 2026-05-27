"""RF-04  Physically impossible accident dynamics.

Hard rule → rojo regardless of additive score.
Points: 0 (tier override via tier_hint=rojo).
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="RF-04",
    name="Dinámica del accidente físicamente imposible",
    tier_hint=Tier.rojo,
    short_description=(
        "La descripción del accidente es físicamente incoherente"
        " — requiere investigación de campo."
    ),
    what_triggers="El análisis de la narrativa detecta una dinámica de accidente imposible.",
    max_points=0,
)


class RF04ImpossibleDynamics:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        if not ctx.dinamica_imposible:
            return None

        return RuleActivation(
            code=META.code,
            points=0,
            tier_hint=META.tier_hint,
            evidence={"dinamica_imposible": True},
        )
