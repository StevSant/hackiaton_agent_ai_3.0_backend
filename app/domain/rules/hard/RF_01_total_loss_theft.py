"""RF-01  Coverage "Total Loss for Theft" (PTxRB).

Hard rule → rojo regardless of additive score.
Points: 0 (tier override via tier_hint=rojo).
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="RF-01",
    name="Cobertura Pérdida Total por Robo",
    tier_hint=Tier.rojo,
    short_description="Cobertura de pérdida total por robo activa — requiere revisión inmediata.",
    what_triggers="La cobertura del siniestro corresponde a Pérdida Total por Robo (PTxRB).",
    max_points=0,
)


class RF01TotalLossTheft:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        if not ctx.es_cobertura_ptxrb:
            # Double-check against the config list for any coverage variant not caught by from_claim
            cfg = rule_cfg("RF_01")
            cobertura_lower = claim.cobertura.lower()
            hits = [c for c in cfg["coberturas_ptxrb"] if c.lower() in cobertura_lower]
            if not hits:
                return None

        return RuleActivation(
            code=META.code,
            points=0,
            tier_hint=META.tier_hint,
            evidence={"cobertura": claim.cobertura},
        )
