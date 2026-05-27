"""RF-07  Identical (cloned) narrative.

Hard rule → floor amarillo.
Points: 0 (tier override via tier_hint=amarillo).

Fires when narrativa_similar_score >= RF_07.threshold_similarity (default 0.98).
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="RF-07",
    name="Narrativa idéntica (clonada)",
    tier_hint=Tier.amarillo,
    short_description=(
        "Mientras que FS-13 mide similitud progresiva (similar / muy similar), "
        "esta regla captura el extremo: narrativas prácticamente idénticas a "
        "un siniestro previo, indicando que dos o más reclamos están "
        "reciclando el mismo texto descriptivo. Es uno de los patrones más "
        "claros de coordinación entre asegurados o de cadenas de reclamos "
        "operadas por el mismo actor."
    ),
    what_triggers=(
        "Se activa cuando la similitud semántica con otro siniestro alcanza "
        "el 98% o más, o cuando el flag narrativa_clonada viene marcado "
        "desde la capa de similitud. Hard rule — fuerza piso amarillo."
    ),
    max_points=0,
)


class RF07ClonedNarrative:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        cfg = rule_cfg("RF_07")
        sim = ctx.narrativa_similar_score

        # narrativa_clonada can also be set directly by the similarity layer
        if not ctx.narrativa_clonada and sim < cfg["threshold_similarity"]:
            return None

        return RuleActivation(
            code=META.code,
            points=0,
            tier_hint=META.tier_hint,
            evidence={"similitud_narrativa": round(sim, 4)},
        )
