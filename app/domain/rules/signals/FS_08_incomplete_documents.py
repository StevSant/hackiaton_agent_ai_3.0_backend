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
    short_description=(
        "Un expediente de siniestro debe llegar con un conjunto mínimo de "
        "documentos (denuncia, peritaje, cédula, matrícula, licencia, "
        "proforma de taller). Cuando faltan piezas críticas, sea por descuido "
        "o por tratarse de un caso que no tiene respaldo real, el expediente "
        "no se puede evaluar completamente y el riesgo de pago indebido sube."
    ),
    what_triggers=(
        "Aporta 4 puntos cuando uno o más documentos obligatorios figuran "
        "como faltantes en el expediente."
    ),
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
