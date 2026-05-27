"""FS-02  Theft denouncement delay.

Applies only to theft-related coverages.
Points: >48 h -> 8 pts; 24-48 h -> 4 pts; <24 h -> 0 (no fire).
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="FS-02",
    name="Demora en denuncia por robo",
    tier_hint=Tier.amarillo,
    short_description=(
        "En coberturas de robo, la denuncia ante la autoridad debe presentarse "
        "lo más rápido posible — esa es la evidencia primaria del siniestro. "
        "Demoras atípicas suelen indicar que la denuncia se construyó después "
        "del hecho, o que se está cubriendo un evento que no fue realmente un "
        "robo. La regla solo aplica cuando la cobertura del siniestro es de "
        "tipo robo."
    ),
    what_triggers=(
        "Aporta 8 puntos si la denuncia se presentó más de 48 horas después "
        "de la ocurrencia, y 4 puntos entre 24 y 48 horas. Por debajo de las "
        "24 horas no se activa."
    ),
    max_points=8,
)


class FS02TheftDenouncementDelay:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        if not ctx.es_robo:
            return None

        cfg = rule_cfg("FS_02")
        horas = ctx.demora_denuncia_horas

        if horas > cfg["threshold_high_hours"]:
            pts: int = cfg["points_high"]
        elif horas >= cfg["threshold_mid_hours"]:
            pts = cfg["points_mid"]
        else:
            return None

        return RuleActivation(
            code=META.code,
            points=pts,
            tier_hint=META.tier_hint,
            evidence={"demora_denuncia_horas": round(horas, 1)},
        )
