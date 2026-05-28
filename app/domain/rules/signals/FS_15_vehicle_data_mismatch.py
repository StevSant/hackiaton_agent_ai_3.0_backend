"""FS-15  Vehicle data mismatch (chassis/VIN vs. declared vehicle).

Extension beyond §2.5's FS-01..FS-14. The claim DECLARES a vehicle (marca /
modelo / año); decoding its chassis/VIN against a registry (NHTSA vPIC for real
VINs, an offline deterministic registry for synthetic chassis) yields a canonical
spec. When the decoded spec contradicts the declared one, the identity does not
add up — a classic indicator of a swapped/cloned vehicle or an altered claim.

Points: 8 when ``ctx.vehiculo_inconsistente`` is set (filled by the decode step
in ``build_rule_context_from_db``). The discrepant fields ride in the evidence.
"""

from __future__ import annotations

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.rules.ports import RuleMeta
from app.schemas.claim import ClaimDetail
from app.schemas.risk import RuleActivation, Tier

META = RuleMeta(
    code="FS-15",
    name="Inconsistencia de datos del vehículo",
    tier_hint=Tier.amarillo,
    short_description=(
        "El chasis/VIN declarado en el siniestro se decodifica contra un "
        "registro vehicular (NHTSA vPIC para VINs reales, o el registro "
        "determinístico interno para chasis sintéticos) y se compara con la "
        "marca, modelo y año DECLARADOS en el reclamo. Cuando la identidad "
        "decodificada contradice la declarada, los datos del vehículo no "
        "cuadran — patrón típico de unidad sustituida/clonada o reclamo "
        "alterado."
    ),
    what_triggers=(
        "Aporta 8 puntos cuando la marca o el modelo decodificados difieren de "
        "los declarados, o cuando el año difiere en más de la tolerancia "
        "permitida. Los campos en conflicto se muestran en la evidencia."
    ),
    max_points=8,
)


class FS15VehicleDataMismatch:
    META = META

    def evaluate(self, claim: ClaimDetail, ctx: RuleContext) -> RuleActivation | None:
        if not ctx.vehiculo_inconsistente:
            return None

        cfg = rule_cfg("FS_15")
        return RuleActivation(
            code=META.code,
            points=cfg["points"],
            tier_hint=META.tier_hint,
            evidence={"campos_discrepantes": ctx.vehiculo_campos_discrepantes},
        )
