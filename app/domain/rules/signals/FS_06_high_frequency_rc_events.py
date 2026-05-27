"""FS-06  High frequency RC-only events.

Points: >2 prior RC events → 6; exactly 1 → 3; 0 → no fire.
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="FS-06",
    name="Alta frecuencia de eventos solo RC",
    tier_hint=Tier.amarillo,
    short_description=(
        "Los siniestros que solo afectan responsabilidad civil (sin daños "
        "propios) tienen un costo de detección bajo y por eso son terreno "
        "habitual para reclamos infundados o exagerados. Una concentración "
        "de eventos RC sobre el mismo asegurado o vehículo en un período "
        "corto sugiere uso recurrente de la cobertura para reclamar daños "
        "a terceros que no necesariamente ocurrieron."
    ),
    what_triggers=(
        "Aporta 6 puntos cuando hay más de 2 eventos RC previos, y 3 puntos "
        "cuando hay exactamente 1 evento RC previo."
    ),
    max_points=6,
)


class FS06HighFrequencyRCEvents:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        cfg = rule_cfg("FS_06")
        n = ctx.eventos_rc_previos

        if n > cfg["threshold_high"]:
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
                "eventos_rc_previos": n,
            },
        )
