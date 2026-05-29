"""FS-18  Concentración o colusión de proveedor.

Two sub-signals:
- Repeated provider+insured pairing → strong collusion signal (points_pair).
- Provider over-concentration across all claims (points_provider).

Both can fire independently; the rule returns the highest applicable points.
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="FS-18",
    name="Concentración o colusión de proveedor",
    tier_hint=Tier.amarillo,
    short_description=(
        "Cuando el mismo proveedor interviene reiteradamente con el mismo "
        "asegurado, o cuando un proveedor acumula un número inusualmente "
        "alto de reclamos en toda la cartera, se eleva la probabilidad de "
        "acuerdos irregulares entre partes. Puede indicar sobrevaluación "
        "sistemática de daños o fabricación coordinada de siniestros."
    ),
    what_triggers=(
        "Aporta puntos altos cuando la misma pareja proveedor-asegurado "
        "aparece en más reclamos que el umbral configurado. Aporta puntos "
        "bajos cuando el proveedor supera el total de reclamos asociados "
        "permitido en toda la cartera."
    ),
    max_points=8,
)


class FS18ProviderConcentration:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        cfg = rule_cfg("FS_18")

        fires_pair = ctx.pareja_proveedor_asegurado > cfg["threshold_pair"]
        fires_provider = ctx.proveedor_total_siniestros > cfg["threshold_provider"]

        if not fires_pair and not fires_provider:
            return None

        # Collusion pairing is the stronger signal
        pts: int = cfg["points_pair"] if fires_pair else cfg["points_provider"]

        return RuleActivation(
            code=META.code,
            points=pts,
            tier_hint=META.tier_hint,
            evidence={
                "proveedor": claim.proveedor,
                "pareja_proveedor_asegurado": ctx.pareja_proveedor_asegurado,
                "proveedor_total_siniestros": ctx.proveedor_total_siniestros,
            },
        )
