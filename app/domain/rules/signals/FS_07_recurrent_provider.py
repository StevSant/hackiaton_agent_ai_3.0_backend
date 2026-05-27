"""FS-07  Recurrent beneficiary / provider.

Points: provider in restrictive list → 10;
        >2 observed claims (not on list) → 5;
        otherwise → no fire.
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="FS-07",
    name="Proveedor o beneficiario recurrente",
    tier_hint=Tier.amarillo,
    short_description=(
        "El proveedor o beneficiario aparece en lista restrictiva o con alta frecuencia."
    ),
    what_triggers=(
        "Proveedor en lista restrictiva, o más de 2 casos observados para el mismo proveedor."
    ),
    max_points=10,
)


class FS07RecurrentProvider:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        cfg = rule_cfg("FS_07")
        proveedor_id = claim.proveedor or "N/A"

        if ctx.proveedor_en_lista_restrictiva or ctx.beneficiario_en_lista_restrictiva:
            pts: int = cfg["points_lista_restrictiva"]
            lista = True
        elif ctx.proveedor_casos_observados > cfg["threshold_observed"]:
            pts = cfg["points_observed"]
            lista = False
        else:
            return None

        return RuleActivation(
            code=META.code,
            points=pts,
            tier_hint=META.tier_hint,
            evidence={
                "proveedor_id": proveedor_id,
                "en_lista_restrictiva": lista,
                "casos_observados": ctx.proveedor_casos_observados,
            },
        )
