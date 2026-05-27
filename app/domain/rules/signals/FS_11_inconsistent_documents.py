"""FS-11  Inconsistent documents.

Points: confirmed alteration / pre-event dates → 10; suspected → 5.
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="FS-11",
    name="Documentos inconsistentes",
    tier_hint=Tier.amarillo,
    short_description="Se detectaron alteraciones o inconsistencias en la documentación.",
    what_triggers="Inconsistencia confirmada o sospecha de alteración en el expediente.",
    max_points=10,
)


class FS11InconsistentDocuments:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        if not ctx.inconsistencia_documental and not ctx.falsificacion_evidente:
            return None

        cfg = rule_cfg("FS_11")
        confirmed = ctx.falsificacion_evidente

        pts: int = cfg["points_confirmed"] if confirmed else cfg["points_suspected"]

        return RuleActivation(
            code=META.code,
            points=pts,
            tier_hint=META.tier_hint,
            evidence={
                "falsificacion_evidente": ctx.falsificacion_evidente,
                "inconsistencia_documental": ctx.inconsistencia_documental,
            },
        )
