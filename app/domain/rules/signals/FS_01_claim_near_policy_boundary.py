"""FS-01  Claim near policy boundary.

Points: <=10 days -> 8 pts; 11-30 days -> 4 pts; >30 days -> 0 (no fire).
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="FS-01",
    name="Siniestro cerca del inicio de póliza",
    tier_hint=Tier.amarillo,
    short_description="El siniestro ocurrió muy cerca del inicio de la póliza.",
    what_triggers="Menos de 30 días entre inicio de póliza y fecha de ocurrencia.",
    max_points=8,
)


class FS01ClaimNearPolicyBoundary:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        cfg = rule_cfg("FS_01")
        dias = ctx.dias_desde_inicio_poliza

        if dias <= cfg["tier1_days"]:
            pts: int = cfg["tier1_points"]
        elif dias <= cfg["tier2_days"]:
            pts = cfg["tier2_points"]
        else:
            return None

        return RuleActivation(
            code=META.code,
            points=pts,
            tier_hint=META.tier_hint,
            evidence={"dias_desde_inicio_poliza": dias},
        )
