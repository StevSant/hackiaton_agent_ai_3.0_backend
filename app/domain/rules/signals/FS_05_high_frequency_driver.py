"""FS-05  High claim frequency — driver.

Points: ≥3 → 8; exactly 2 → 4; <2 → 0 (no fire).
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="FS-05",
    name="Alta frecuencia de siniestros — conductor",
    tier_hint=Tier.amarillo,
    short_description=(
        "Cuando el mismo conductor figura en múltiples siniestros — incluso "
        "bajo asegurados o vehículos distintos — puede tratarse de un perfil "
        "de alto riesgo, un conductor profesional no declarado, o un actor "
        "que opera coordinadamente entre pólizas. Esta regla mira el "
        "historial del conductor, no del titular de la póliza."
    ),
    what_triggers=(
        "Aporta 8 puntos si el conductor acumula 3 o más siniestros previos, "
        "y 4 puntos cuando acumula exactamente 2."
    ),
    max_points=8,
)


class FS05HighFrequencyDriver:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        cfg = rule_cfg("FS_05")
        n = ctx.frecuencia_conductor

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
            evidence={"asegurado_id": claim.asegurado_id, "siniestros_conductor": n},
        )
