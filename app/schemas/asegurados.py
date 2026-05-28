"""Wire schemas for the /asegurados endpoints — insured-persons risk view.

`AseguradoOut` is the read shape (with computed aggregates). `AseguradoCreate` /
`AseguradoUpdate` are the write shapes for single-record management, grouped here
following the codebase's per-entity DTO module convention.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AseguradoOut(BaseModel):
    id_asegurado: str
    nombre: str
    segmento: str | None = None
    ciudad: str
    antiguedad: int | None = None
    num_polizas: int = 0
    reclamos_ultimos_12_meses: int = 0
    mora_actual: bool = False
    score_cliente_simulado: float | None = None
    casos: int = 0
    alertas: int = 0
    monto: float = 0.0
    ramos: list[str] = []


class AseguradoCreate(BaseModel):
    """Payload for adding a single insured person by hand."""

    id_asegurado: str | None = Field(
        None, description="Opcional — se genera si no se envía"
    )
    nombre: str | None = None
    segmento: str | None = None
    ciudad: str = Field(..., min_length=1)
    antiguedad: int | None = Field(None, ge=0, description="Antigüedad en años")
    num_polizas: int = Field(0, ge=0)
    reclamos_ultimos_12_meses: int = Field(0, ge=0)
    mora_actual: bool = False
    score_cliente_simulado: float | None = Field(None, ge=0, le=100)


class AseguradoUpdate(BaseModel):
    """Partial update — only the provided fields are applied."""

    nombre: str | None = None
    segmento: str | None = None
    ciudad: str | None = Field(None, min_length=1)
    antiguedad: int | None = Field(None, ge=0)
    num_polizas: int | None = Field(None, ge=0)
    reclamos_ultimos_12_meses: int | None = Field(None, ge=0)
    mora_actual: bool | None = None
    score_cliente_simulado: float | None = Field(None, ge=0, le=100)
