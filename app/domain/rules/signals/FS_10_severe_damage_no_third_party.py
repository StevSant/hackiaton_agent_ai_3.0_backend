"""FS-10  Severe damage with no third-party trace.

Points: 6 when damage is severe but no third-party witness/trace exists.
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="FS-10",
    name="Daño grave sin rastro de tercero",
    tier_hint=Tier.amarillo,
    short_description=(
        "Un daño material significativo casi siempre deja rastros físicos "
        "de la otra parte involucrada — restos en la calzada, daños "
        "compatibles entre vehículos, testigos. Cuando el daño declarado es "
        "alto pero no hay ningún elemento que confirme un tercero, el caso "
        "puede estar reciclando un daño preexistente o autoinfligido."
    ),
    what_triggers=(
        "Aporta 6 puntos cuando el peritaje registra daño grave pero el "
        "expediente no contiene evidencia de tercero (testigos, contra-parte, "
        "rastros en escena)."
    ),
    max_points=6,
)


class FS10SevereDamageNoThirdParty:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        if not ctx.sin_rastro_tercero:
            return None

        cfg = rule_cfg("FS_10")
        return RuleActivation(
            code=META.code,
            points=cfg["points"],
            tier_hint=META.tier_hint,
            evidence={
                "monto_reclamado": claim.monto_reclamado,
                "sin_rastro_tercero": True,
            },
        )
