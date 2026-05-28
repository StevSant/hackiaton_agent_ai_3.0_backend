"""Tool — verifica la identidad del vehículo de un siniestro.

Decodifica un chasis/VIN contra el registro vehicular (NHTSA vPIC para VINs
reales, o el registro determinístico interno para chasis sintéticos) y lo compara
con el vehículo DECLARADO en el siniestro. Si la identidad decodificada
contradice la declarada, es una señal de posible fraude (la regla FS-15).

Dos modos:
- ``claim_id`` → toma el vehículo declarado (marca/modelo/año) y el chasis del
  siniestro vía el puerto ``ClaimQueries``, decodifica y compara.
- sólo ``chassis`` → decodifica el chasis suelto (sin vehículo declarado contra
  el cual comparar; ``inconsistente`` queda en False).
"""

from __future__ import annotations

from pydantic import BaseModel

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.domain.vehicle_identity import (
    VehicleDecoder,
    VehicleSpec,
    compare_vehicle,
)


class VerifyVehicleInput(BaseModel):
    claim_id: str | None = None
    chassis: str | None = None


class VerifyVehicleOutput(BaseModel):
    found: bool
    decodificado: VehicleSpec | None = None
    declarado: VehicleSpec | None = None
    inconsistente: bool = False
    campos_discrepantes: list[str] = []
    fuente: str = "decoder"


class VerifyVehicleTool:
    name = "verify_vehicle"
    description = (
        "Verifica la identidad del vehículo: decodifica el chasis/VIN contra el "
        "registro vehicular (NHTSA vPIC para VINs reales, registro interno para "
        "chasis sintéticos) y lo compara con el vehículo declarado en el "
        "siniestro. Úsalo cuando el usuario pregunte si los datos del vehículo "
        "cuadran, o por qué se activó la alerta de inconsistencia del vehículo "
        "(FS-15). Acepta un claim_id (compara contra lo declarado) o un chassis "
        "suelto (solo decodifica)."
    )

    def __init__(self, queries: ClaimQueries, decoder: VehicleDecoder) -> None:
        self._queries = queries
        self._decoder = decoder

    @property
    def input_schema(self) -> dict[str, object]:
        return VerifyVehicleInput.model_json_schema()

    async def run(self, args: VerifyVehicleInput) -> VerifyVehicleOutput:
        if args.claim_id:
            return await self._verify_by_claim(args.claim_id)
        if args.chassis:
            return await self._verify_by_chassis(args.chassis)
        return VerifyVehicleOutput(found=False)

    async def _verify_by_claim(self, claim_id: str) -> VerifyVehicleOutput:
        detail = await self._queries.get_detail(claim_id)
        vehiculo = detail.vehiculo if detail is not None else None
        if detail is None or vehiculo is None or not vehiculo.chasis:
            return VerifyVehicleOutput(found=False)

        decoded = await self._decoder.decode(vehiculo.chasis)
        declarado = VehicleSpec(
            marca=vehiculo.marca,
            modelo=vehiculo.modelo,
            anio=vehiculo.anio,
        )
        match = compare_vehicle(declarado, decoded, fuente="decoder")
        return VerifyVehicleOutput(
            found=True,
            decodificado=match.decodificado,
            declarado=match.declarado,
            inconsistente=match.inconsistente,
            campos_discrepantes=match.campos_discrepantes,
            fuente=match.fuente,
        )

    async def _verify_by_chassis(self, chassis: str) -> VerifyVehicleOutput:
        decoded = await self._decoder.decode(chassis)
        match = compare_vehicle(None, decoded, fuente="decoder")
        return VerifyVehicleOutput(
            found=decoded is not None,
            decodificado=match.decodificado,
            declarado=None,
            inconsistente=match.inconsistente,
            campos_discrepantes=match.campos_discrepantes,
            fuente=match.fuente,
        )
