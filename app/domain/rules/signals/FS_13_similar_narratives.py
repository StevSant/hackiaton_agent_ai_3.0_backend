"""FS-13  Similar narratives (pgvector cosine similarity).

Points: >85% similarity -> 8 (clone-level); 70-84% -> 4 (similar); <70% -> 0.
The narrativa_similar_score is populated by the similarity layer (L7).
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="FS-13",
    name="Narrativas similares detectadas",
    tier_hint=Tier.amarillo,
    short_description=(
        "El motor de similitud por embeddings compara la narrativa del "
        "siniestro contra todas las narrativas previas registradas. Cuando "
        "encuentra coincidencias semánticas muy altas, suele tratarse de "
        "reclamos coordinados con el mismo \"libreto\" — distintas pólizas "
        "describiendo el mismo hecho con variaciones mínimas. La regla "
        "distingue \"similar\" (70-85%) de \"clonado\" (>85%) por peso."
    ),
    what_triggers=(
        "Aporta 8 puntos cuando la similitud supera el 85% (nivel \"clon\"), "
        "y 4 puntos en el rango 70-85% (\"similar\"). El ID y el porcentaje "
        "del caso más cercano se muestran en la evidencia."
    ),
    max_points=8,
)


class FS13SimilarNarratives:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        cfg = rule_cfg("FS_13")
        sim = ctx.narrativa_similar_score

        if sim > cfg["threshold_clone"]:
            pts: int = cfg["points_clone"]
        elif sim >= cfg["threshold_similar"]:
            pts = cfg["points_similar"]
        else:
            return None

        return RuleActivation(
            code=META.code,
            points=pts,
            tier_hint=META.tier_hint,
            evidence={"similitud_narrativa": round(sim, 4)},
        )
