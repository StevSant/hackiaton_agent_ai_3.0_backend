"""RF-06  Atypical theft denouncement delay (>4 days).

Hard rule → floor amarillo (any one fires → at least yellow).
Points: 0 (tier override via tier_hint=amarillo).

Applies only to theft-related coverages.
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="RF-06",
    name="Demora atípica en denuncia de robo",
    tier_hint=Tier.amarillo,
    short_description="La denuncia por robo fue presentada más de 4 días después de la ocurrencia.",
    what_triggers="Más de 4 días entre ocurrencia y denuncia en coberturas de robo.",
    max_points=0,
)


class RF06AtypicalTheftDelay:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        if not ctx.es_robo:
            return None

        cfg = rule_cfg("RF_06")
        # threshold_days is in days; demora_denuncia_horas is in hours
        threshold_horas = cfg["threshold_days"] * 24.0
        horas = ctx.demora_denuncia_horas

        if horas <= threshold_horas:
            return None

        return RuleActivation(
            code=META.code,
            points=0,
            tier_hint=META.tier_hint,
            evidence={
                "demora_denuncia_horas": round(horas, 1),
                "threshold_dias": cfg["threshold_days"],
            },
        )
