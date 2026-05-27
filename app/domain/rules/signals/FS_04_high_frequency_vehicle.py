"""FS-04  High claim frequency — vehicle.

Points: ≥3 → 6; exactly 2 → 3; <2 → 0 (no fire).
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="FS-04",
    name="Alta frecuencia de siniestros — vehículo",
    tier_hint=Tier.amarillo,
    short_description=(
        "Un mismo vehículo (por placa o chasis) que aparece en varios "
        "siniestros recientes apunta a un activo problemático — alquileres "
        "informales, reventa de partes, daños pre-existentes que se "
        "re-reclaman, o un patrón de exposición compartida. La regla se "
        "evalúa sobre el historial del vehículo, independiente del asegurado."
    ),
    what_triggers=(
        "Aporta 6 puntos cuando el vehículo tiene 3 o más siniestros previos, "
        "y 3 puntos cuando tiene exactamente 2."
    ),
    max_points=6,
)


class FS04HighFrequencyVehicle:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        cfg = rule_cfg("FS_04")
        n = ctx.frecuencia_vehiculo

        if n >= cfg["threshold_high"]:
            pts: int = cfg["points_high"]
        elif n >= cfg["threshold_mid"]:
            pts = cfg["points_mid"]
        else:
            return None

        placa = claim.vehiculo.placa if claim.vehiculo else "N/A"
        return RuleActivation(
            code=META.code,
            points=pts,
            tier_hint=META.tier_hint,
            evidence={"placa": placa, "siniestros_vehiculo": n},
        )
