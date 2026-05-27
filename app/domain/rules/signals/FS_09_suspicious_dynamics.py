"""FS-09  Suspicious dynamics.

Points: illogical narrative → 6; midnight multi-event → 3.
Both can fire on the same claim (max 9, but spec shows max 6 for this signal —
we apply highest applicable tier, not additive, per §2.5 signal max=6).
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="FS-09",
    name="Dinámica sospechosa del siniestro",
    tier_hint=Tier.amarillo,
    short_description="La descripción del siniestro presenta inconsistencias o patrones atípicos.",
    what_triggers="Narrativa ilógica o evento multi-siniestro en horario nocturno.",
    max_points=6,
)


class FS09SuspiciousDynamics:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        cfg = rule_cfg("FS_09")
        pts = 0
        illogical = ctx.narrativa_ilógica
        midnight = ctx.evento_medianoche

        if illogical:
            pts = cfg["points_illogical"]
        elif midnight:
            pts = cfg["points_midnight"]

        if pts == 0:
            return None

        return RuleActivation(
            code=META.code,
            points=pts,
            tier_hint=META.tier_hint,
            evidence={
                "narrativa_ilógica": illogical,
                "evento_medianoche": midnight,
            },
        )
