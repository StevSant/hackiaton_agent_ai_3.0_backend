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
        "El perito o la auditoría técnica determinó que la dinámica del "
        "accidente declarada por el asegurado es físicamente imposible — "
        "trayectorias, velocidades, ángulos de impacto o secuencias "
        "temporales que no pueden haber ocurrido como se describen. Esto es "
        "un indicio fuerte de un evento simulado o reconstruido, y demanda "
        "revisión de campo antes de cualquier liquidación."
    ),
    what_triggers=(
        "Se activa cuando el flag dinamica_imposible está marcado en el "
        "contexto, generalmente derivado de un peritaje técnico. Hard rule "
        "— fuerza tier rojo."
    ),
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
