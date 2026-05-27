"""FS-08  Incomplete legal documents.

Points: 4 when any required document is missing.
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="FS-08",
    name="Documentos legales incompletos",
    tier_hint=Tier.amarillo,
    short_description="El siniestro presenta documentos requeridos faltantes.",
    what_triggers="Uno o más documentos marcados como faltantes en el expediente.",
    max_points=4,
)


class FS08IncompleteDocuments:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        if not ctx.documentos_incompletos:
            return None

        cfg = rule_cfg("FS_08")
        faltantes = [d.tipo for d in claim.documentos if d.falta]

        return RuleActivation(
            code=META.code,
            points=cfg["points"],
            tier_hint=META.tier_hint,
            evidence={"documentos_faltantes": faltantes, "cantidad_faltantes": len(faltantes)},
        )
