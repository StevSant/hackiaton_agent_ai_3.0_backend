"""FS-03  High claim frequency — insured.

Points: ≥3 claims in 18 months → 8; exactly 2 → 4; <2 → 0 (no fire).
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="FS-03",
    name="Alta frecuencia de siniestros — asegurado",
    tier_hint=Tier.amarillo,
    short_description="El asegurado registra una cantidad inusualmente alta de siniestros.",
    what_triggers="2 o más siniestros del mismo asegurado en los últimos 18 meses.",
    max_points=8,
)


class FS03HighFrequencyInsured:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        cfg = rule_cfg("FS_03")
        n = ctx.historial_siniestros_asegurado

        if n >= cfg["threshold_high"]:
            pts: int = cfg["points_high"]
        elif n >= cfg["threshold_mid"]:
            pts = cfg["points_mid"]
        else:
            return None

        return RuleActivation(
            code=META.code,
            points=pts,
            tier_hint=META.tier_hint,
            evidence={
                "asegurado_id": claim.asegurado_id,
                "siniestros_18_meses": n,
            },
        )
