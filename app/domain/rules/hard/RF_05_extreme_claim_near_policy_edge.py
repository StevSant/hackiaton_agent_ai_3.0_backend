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
    short_description=(
        "Un siniestro que ocurre en las primeras 48 horas de vigencia es "
        "estadísticamente extremo — gran parte de los casos de antifraude "
        "confirmados en años recientes encajan en esta ventana. La regla "
        "actúa como piso de amarillo: el caso no puede quedar en verde, "
        "pero tampoco sube automáticamente a rojo sin más señales que lo "
        "respalden."
    ),
    what_triggers=(
        "Se activa cuando hay menos de 48 horas entre el inicio de vigencia "
        "de la póliza y la ocurrencia del siniestro. Hard rule — fuerza "
        "piso amarillo (sin sumar puntos)."
    ),
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
