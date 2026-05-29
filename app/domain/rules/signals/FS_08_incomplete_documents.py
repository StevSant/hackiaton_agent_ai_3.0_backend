"""FS-08  Incomplete legal documents.

Points: 4 when any required document is missing.

Extended: ramo-aware required-doc sets from config.yaml FS_08.ramo_required_docs.
When the claim's ramo matches a configured set, we check for each required doc
type by substring (accent/case-insensitive). Falls back to the original
ctx.documentos_incompletos check when the ramo is not mapped.
"""

from __future__ import annotations

import unicodedata

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
        "como faltantes en el expediente (evaluación por ramo cuando está "
        "configurada; genérica en caso contrario)."
    ),
    max_points=4,
)


def _normalize(text: str) -> str:
    """Lowercase + strip accents for accent/case-insensitive matching."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn"
    )


class FS08IncompleteDocuments:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        cfg = rule_cfg("FS_08")

        # Try ramo-aware check first
        ramo_map: dict[str, list[str]] = cfg.get("ramo_required_docs", {})
        claim_ramo_norm = _normalize(claim.ramo)

        # Find matching ramo key (also normalize keys for comparison)
        required_for_ramo: list[str] | None = None
        for ramo_key, docs in ramo_map.items():
            if _normalize(ramo_key) == claim_ramo_norm:
                required_for_ramo = docs
                break

        if required_for_ramo is not None:
            # Ramo-aware: check which required docs are absent
            present_doc_norms = [
                _normalize(d.tipo) for d in claim.documentos if not d.falta
            ]
            faltantes = [
                req
                for req in required_for_ramo
                if not any(_normalize(req) in norm for norm in present_doc_norms)
            ]
            if not faltantes:
                return None
            return RuleActivation(
                code=META.code,
                points=cfg["points"],
                tier_hint=META.tier_hint,
                evidence={
                    "documentos_faltantes": faltantes,
                    "cantidad_faltantes": len(faltantes),
                    "ramo": claim.ramo,
                },
            )

        # Fallback: original generic check
        if not ctx.documentos_incompletos:
            return None

        faltantes_generic = [d.tipo for d in claim.documentos if d.falta]
        return RuleActivation(
            code=META.code,
            points=cfg["points"],
            tier_hint=META.tier_hint,
            evidence={
                "documentos_faltantes": faltantes_generic,
                "cantidad_faltantes": len(faltantes_generic),
            },
        )
