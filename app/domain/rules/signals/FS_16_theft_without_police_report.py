"""FS-16  Robo sin parte policial.

Points: fires when the claim is a theft (es_robo) but has no police report number.
A theft without a formal police report is a strong procedural gap — legitimate
theft victims almost always file one for insurance purposes.
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="FS-16",
    name="Robo sin parte policial",
    tier_hint=Tier.amarillo,
    short_description=(
        "Un robo de vehículo o bien asegurado debería siempre acompañarse de "
        "un parte policial. La ausencia de ese número es un vacío procedimental "
        "que dificulta la verificación del evento y eleva el riesgo de que el "
        "siniestro sea fabricado o exagerado."
    ),
    what_triggers=(
        "Aporta puntos cuando la cobertura involucra robo "
        "y no existe número de parte policial registrado en el expediente."
    ),
    max_points=6,
)


class FS16TheftWithoutPoliceReport:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        # Only applies to theft claims; no police report → signal fires
        if not ctx.es_robo or ctx.tiene_parte_policial:
            return None

        cfg = rule_cfg("FS_16")
        return RuleActivation(
            code=META.code,
            points=cfg["points"],
            tier_hint=META.tier_hint,
            evidence={
                "es_robo": True,
                "tiene_parte_policial": False,
            },
        )
