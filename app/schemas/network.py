"""Wire schemas for the /network/providers endpoints — provider risk-network view.

`ProviderOut` is the read shape (with computed aggregates). `ProviderCreate` /
`ProviderUpdate` are the write shapes for single-record management. They are
grouped here because the codebase keeps an entity's wire DTOs in one module.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderOut(BaseModel):
    id_proveedor: str
    nombre: str
    tipo: str
    ciudad: str
    casos: int
    alertas: int
    monto: float
    lista_restrictiva: bool
    ramos: list[str] = []


class ProviderCreate(BaseModel):
    """Payload for adding a single provider / beneficiary by hand."""

    id_proveedor: str | None = Field(
        None, description="Opcional — se genera si no se envía"
    )
    nombre: str | None = None
    tipo: str = Field(..., min_length=1, description="Taller, clínica, beneficiario…")
    ciudad: str = Field(..., min_length=1)
    antiguedad: int | None = Field(None, ge=0, description="Antigüedad en meses")
    lista_restrictiva: bool = False
    reclamos_asociados: int = Field(0, ge=0)
    monto_promedio_reclamado: float = Field(0.0, ge=0)


class ProviderUpdate(BaseModel):
    """Partial update — only the provided fields are applied."""

    nombre: str | None = None
    tipo: str | None = Field(None, min_length=1)
    ciudad: str | None = Field(None, min_length=1)
    antiguedad: int | None = Field(None, ge=0)
    lista_restrictiva: bool | None = None
    reclamos_asociados: int | None = Field(None, ge=0)
    monto_promedio_reclamado: float | None = Field(None, ge=0)
