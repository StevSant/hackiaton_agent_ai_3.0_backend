"""FS-19  Perfil de riesgo alto del asegurado.

Soft signal: the insured's pre-assigned risk profile (from the dataset or
underwriting) explicitly marks them as 'alto'. Alone it does not prove anything,
but combined with other signals it tips the score.
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="FS-19",
    name="Perfil de riesgo alto del asegurado",
    tier_hint=Tier.amarillo,
    short_description=(
        "El perfil de riesgo del asegurado integra historial de pagos, "
        "frecuencia de reclamos pasados y comportamiento de mora. Cuando "
        "ese perfil está catalogado como alto, el siniestro recibe un "
        "punto extra de atención, especialmente si coincide con otras alertas."
    ),
    what_triggers=(
        "Aporta puntos cuando el campo perfil_riesgo del asegurado "
        "contiene la palabra 'alto' (sin distinguir mayúsculas)."
    ),
    max_points=3,
)


class FS19HighRiskProfile:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        if not ctx.perfil_riesgo:
            return None
        if "alto" not in ctx.perfil_riesgo.lower():
            return None

        cfg = rule_cfg("FS_19")
        return RuleActivation(
            code=META.code,
            points=cfg["points"],
            tier_hint=META.tier_hint,
            evidence={"perfil_riesgo": ctx.perfil_riesgo},
        )
