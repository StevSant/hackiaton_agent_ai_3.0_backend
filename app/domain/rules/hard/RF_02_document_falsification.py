"""RF-02  Evident document falsification.

Hard rule → rojo regardless of additive score.
Points: 0 (tier override via tier_hint=rojo).
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="RF-02",
    name="Falsificación evidente de documentos",
    tier_hint=Tier.rojo,
    short_description=(
        "Se detectó falsificación evidente en los documentos del siniestro"
        " — requiere revisión urgente."
    ),
    what_triggers="Documentos con alteraciones confirmadas o inconsistencias graves detectadas.",
    max_points=0,
)


class RF02DocumentFalsification:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        if not ctx.falsificacion_evidente:
            return None

        return RuleActivation(
            code=META.code,
            points=0,
            tier_hint=META.tier_hint,
            evidence={"falsificacion_evidente": True},
        )
