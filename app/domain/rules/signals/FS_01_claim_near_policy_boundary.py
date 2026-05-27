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
    short_description=(
        "Cuando un siniestro ocurre pocos días después de emitida la póliza, "
        "es una de las señales más correlacionadas con manipulación temporal: "
        "el asegurado puede haber suscrito la cobertura sabiendo que el evento "
        "ya había ocurrido o estaba por ocurrir. No es prueba de fraude — es un "
        "patrón que merece confirmación documental antes de liquidar."
    ),
    what_triggers=(
        "Aporta 8 puntos cuando el siniestro ocurre dentro de los primeros "
        "10 días de vigencia, y 4 puntos entre los días 11 y 30. A partir "
        "del día 31 deja de activarse."
    ),
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
