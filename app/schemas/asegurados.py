"""Wire schema for GET /asegurados — insured-persons risk view."""

from __future__ import annotations

from pydantic import BaseModel


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
