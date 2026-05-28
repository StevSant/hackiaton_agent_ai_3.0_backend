"""Pure comparison of a declared vehicle spec against a decoded one.

This is the heart of the vehicle-identity signal: a claim DECLARES a vehicle,
the chassis/VIN DECODES to a canonical spec from a registry, and a contradiction
between the two is a fraud signal. ``compare_vehicle`` is pure (no I/O) so it is
trivially testable and reused by both the scoring path and the agent tool.

A small year tolerance is allowed because model-year vs. registry-year off-by-one
is common and benign (a unit registered in December of the prior model year).
"""

from __future__ import annotations

from app.domain.vehicle_identity.models import VehicleMatchResult, VehicleSpec

# Registry vs. declared model-year may legitimately differ by up to this many
# years (December registration of the next model year, etc.). Beyond it, the
# year is treated as a genuine discrepancy.
ANIO_TOLERANCE = 2


def compare_vehicle(
    declarado: VehicleSpec | None,
    decodificado: VehicleSpec | None,
    *,
    fuente: str,
) -> VehicleMatchResult:
    """Compare declared vs. decoded vehicle specs into a match verdict.

    Marca or modelo mismatch (case-insensitive) or ``|anio diff| > ANIO_TOLERANCE``
    makes the result ``inconsistente`` and records which fields disagree. When
    either side is missing there is nothing to contradict, so the result is
    consistent (the signal does not fire on absent data).
    """
    if declarado is None or decodificado is None:
        return VehicleMatchResult(
            inconsistente=False,
            campos_discrepantes=[],
            declarado=declarado,
            decodificado=decodificado,
            fuente=fuente,
        )

    discrepantes: list[str] = []
    if declarado.marca.strip().lower() != decodificado.marca.strip().lower():
        discrepantes.append("marca")
    if declarado.modelo.strip().lower() != decodificado.modelo.strip().lower():
        discrepantes.append("modelo")
    if abs(declarado.anio - decodificado.anio) > ANIO_TOLERANCE:
        discrepantes.append("anio")

    return VehicleMatchResult(
        inconsistente=bool(discrepantes),
        campos_discrepantes=discrepantes,
        declarado=declarado,
        decodificado=decodificado,
        fuente=fuente,
    )
