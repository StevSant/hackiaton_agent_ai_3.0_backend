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
    short_description=(
        "La cobertura de Pérdida Total por Robo (PTxRB) es históricamente "
        "la de mayor exposición a manipulación: el bien desaparece, no hay "
        "evidencia física directa, y el pago es el 100% de la suma asegurada. "
        "Por eso, cualquier siniestro activando PTxRB es escalado automáticamente "
        "a la Unidad Antifraude para verificación documental — esto NO implica "
        "fraude, implica que el caso amerita revisión especializada."
    ),
    what_triggers=(
        "Se activa cuando la cobertura del siniestro corresponde a Pérdida "
        "Total por Robo (PTxRB) o variantes equivalentes listadas en la "
        "configuración de la regla. Hard rule — fuerza tier rojo."
    ),
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
