"""RF-05  Extreme claim near policy edge (<48 hours from policy start).

Hard rule → floor amarillo (any one fires → at least yellow).
Points: 0 (tier override via tier_hint=amarillo).
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="RF-05",
    name="Siniestro extremo al inicio de póliza",
    tier_hint=Tier.amarillo,
    short_description="Siniestro registrado dentro de las primeras 48 h de vigencia de la póliza.",
    what_triggers="Menos de 48 horas entre inicio de póliza y ocurrencia del siniestro.",
    max_points=0,
)


class RF05ExtremeClaimNearPolicyEdge:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        cfg = rule_cfg("RF_05")
        # dias_desde_inicio_poliza is in days; threshold_hours / 24 gives the day fraction
        threshold_days = cfg["threshold_hours"] / 24.0
        dias = ctx.dias_desde_inicio_poliza

        if dias > threshold_days:
            return None

        return RuleActivation(
            code=META.code,
            points=0,
            tier_hint=META.tier_hint,
            evidence={
                "dias_desde_inicio_poliza": dias,
                "threshold_horas": cfg["threshold_hours"],
            },
        )
