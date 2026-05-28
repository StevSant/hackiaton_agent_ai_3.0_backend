"""Domain value objects for vehicle-identity verification.

`VehicleSpec` is the canonical (marca, modelo, año) triple — the shape both the
declared vehicle and the decoded registry result are projected into so they can
be compared field-for-field. `VehicleMatchResult` is the verdict of that
comparison: whether the decode contradicts what was declared on the claim.

Field names are Spanish snake_case per root CLAUDE.md §2.8 (wire contract).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class VehicleSpec(BaseModel):
    """Canonical vehicle identity: brand, model, year.

    Both the DECLARED vehicle (from the claim) and the DECODED vehicle (from the
    chassis/VIN registry) are expressed as a `VehicleSpec` so the verifier can
    compare them without caring where each came from.
    """

    marca: str = Field(..., min_length=1)
    modelo: str = Field(..., min_length=1)
    anio: int = Field(..., ge=1900, le=2100)


class VehicleMatchResult(BaseModel):
    """Verdict of comparing a declared spec against a decoded spec.

    `inconsistente` is the signal FS-15 reads; `campos_discrepantes` lists which
    canonical fields disagree (``marca`` / ``modelo`` / ``anio``) so the evidence
    and the agent tool can be specific about *what* contradicts.
    """

    inconsistente: bool
    campos_discrepantes: list[str] = Field(default_factory=list)
    declarado: VehicleSpec | None = None
    decodificado: VehicleSpec | None = None
    fuente: str
