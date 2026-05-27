"""FS-12  Late report.

Points: >7 days between occurrence and report -> 5; 4-7 days -> 3; <=3 days -> 0.
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="FS-12",
    name="Reporte tardío",
    tier_hint=Tier.amarillo,
    short_description=(
        "Los siniestros típicos se reportan a la aseguradora en cuestión de "
        "horas o pocos días. Un retraso prolongado puede indicar que el "
        "asegurado intentó resolver el daño por su cuenta y solo recurrió a "
        "la póliza cuando no lo logró, o que el evento mismo está siendo "
        "reconstruido a posteriori. Mientras más tarde llegue el reporte, "
        "más difícil es verificar la versión original del hecho."
    ),
    what_triggers=(
        "Aporta 5 puntos cuando hay más de 7 días entre ocurrencia y reporte, "
        "y 3 puntos cuando el rango es de 4 a 7 días. Hasta 3 días se "
        "considera normal."
    ),
    max_points=5,
)


class FS12LateReport:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        cfg = rule_cfg("FS_12")
        dias = ctx.dias_entre_ocurrencia_reporte

        if dias > cfg["threshold_high_days"]:
            pts: int = cfg["points_high"]
        elif dias >= cfg["threshold_mid_days"]:
            pts = cfg["points_mid"]
        else:
            return None

        return RuleActivation(
            code=META.code,
            points=pts,
            tier_hint=META.tier_hint,
            evidence={"dias_entre_ocurrencia_reporte": dias},
        )
