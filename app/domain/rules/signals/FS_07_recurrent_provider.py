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
        "Un proveedor (taller, clínica) o beneficiario que aparece "
        "repetidamente en siniestros — sea porque ya está en la lista interna "
        "de actores observados por la Unidad Antifraude, o porque acumula "
        "varios casos previos sin estar formalmente listado — es uno de los "
        "patrones más correlacionados con manipulación coordinada de reclamos."
    ),
    what_triggers=(
        "Aporta 10 puntos cuando el proveedor o beneficiario figura en la "
        "lista restrictiva, y 5 puntos cuando acumula más de 2 casos "
        "observados sin estar listado."
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
