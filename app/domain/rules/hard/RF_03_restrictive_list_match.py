"""RF-03  Insured / beneficiary / APS matches restrictive list.

Hard rule → rojo regardless of additive score.
Points: 0 (tier override via tier_hint=rojo).
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="RF-03",
    name="Coincidencia con lista restrictiva",
    tier_hint=Tier.rojo,
    short_description=(
        "La lista restrictiva interna registra actores (asegurados, "
        "beneficiarios, proveedores) con casos previos confirmados como "
        "sospechosos o con sanciones internas. Cuando alguno de los "
        "involucrados en el siniestro está en esa lista, el caso se escala "
        "directamente — no porque la persona sea culpable de nada en este "
        "siniestro, sino porque su historial requiere un nivel de "
        "verificación adicional."
    ),
    what_triggers=(
        "Se activa cuando el proveedor o beneficiario asociado al siniestro "
        "figura en la lista restrictiva. Hard rule — fuerza tier rojo."
    ),
    max_points=0,
)


class RF03RestrictiveListMatch:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        # Note: insured-level restrictive list check requires asegurado_id lookup (L7).
        # For now we rely on proveedor/beneficiario flags from RuleContext.
        if not (ctx.proveedor_en_lista_restrictiva or ctx.beneficiario_en_lista_restrictiva):
            return None

        return RuleActivation(
            code=META.code,
            points=0,
            tier_hint=META.tier_hint,
            evidence={
                "proveedor_en_lista": ctx.proveedor_en_lista_restrictiva,
                "beneficiario_en_lista": ctx.beneficiario_en_lista_restrictiva,
            },
        )
