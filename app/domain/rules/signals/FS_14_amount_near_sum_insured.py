"""FS-14  Amount near or above sum insured.

Points: 5 when monto_reclamado / suma_asegurada ≥ 95%,
        or when monto_reclamado > 150% of average repair cost for that vehicle class.
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="FS-14",
    name="Monto cercano o superior a la suma asegurada",
    tier_hint=Tier.amarillo,
    short_description="El monto reclamado es inusualmente alto en relación con la suma asegurada.",
    what_triggers="Monto reclamado ≥95% de la suma asegurada o >150% del promedio de reparación.",
    max_points=5,
)


class FS14AmountNearSumInsured:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        cfg = rule_cfg("FS_14")

        fires_sum = ctx.monto_vs_suma_pct >= cfg["threshold_pct_high"]
        # monto_vs_reparacion_avg_pct is filled by L7; default 0 → won't fire here
        fires_repair = (
            ctx.monto_vs_reparacion_avg_pct >= cfg["threshold_repair_pct"]
            if ctx.monto_vs_reparacion_avg_pct > 0
            else False
        )

        if not fires_sum and not fires_repair:
            return None

        return RuleActivation(
            code=META.code,
            points=cfg["points"],
            tier_hint=META.tier_hint,
            evidence={
                "monto_reclamado": claim.monto_reclamado,
                "suma_asegurada": claim.suma_asegurada,
                "monto_vs_suma_pct": round(ctx.monto_vs_suma_pct, 4),
            },
        )
