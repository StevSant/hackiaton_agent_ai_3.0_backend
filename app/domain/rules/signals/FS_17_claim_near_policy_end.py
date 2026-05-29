"""FS-17  Siniestro cerca del fin de la póliza.

Points: mirrors FS-01's banding but for the END of coverage.
Claiming just before expiry can indicate intentional timing to capture
the remaining insured value before renewal is denied or re-priced.
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="FS-17",
    name="Siniestro cerca del fin de la póliza",
    tier_hint=Tier.amarillo,
    short_description=(
        "Cuando un siniestro ocurre en los últimos días de vigencia de la "
        "póliza, existe el riesgo de que el asegurado haya acelerado o "
        "fabricado el evento para aprovechar la cobertura antes de que "
        "expire. El patrón es el espejo del FS-01 (inicio de póliza) y "
        "ambos merecen revisión documental adicional."
    ),
    what_triggers=(
        "Aporta puntos según la proximidad al vencimiento: mayor puntaje "
        "cuando quedan 10 días o menos, menor cuando quedan entre 11 y 30 "
        "días. Más de 30 días antes del vencimiento no activa la señal."
    ),
    max_points=8,
)


class FS17ClaimNearPolicyEnd:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        cfg = rule_cfg("FS_17")
        dias = ctx.dias_desde_fin_poliza  # days from occurrence to policy end

        # 9999 is the safe default when policy end date is unknown — must not fire
        if dias > cfg["threshold_days_mid"] or dias < 0 or dias == 9999:
            return None

        if dias <= cfg["threshold_days_high"]:
            pts: int = cfg["points_high"]
        else:
            pts = cfg["points_mid"]

        return RuleActivation(
            code=META.code,
            points=pts,
            tier_hint=META.tier_hint,
            evidence={"dias_desde_fin_poliza": dias},
        )
