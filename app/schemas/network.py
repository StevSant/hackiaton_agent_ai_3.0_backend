"""Wire schemas for the /network/providers endpoints — provider risk-network view.

`ProviderOut` is the read shape (with computed aggregates). `ProviderCreate` /
`ProviderUpdate` are the write shapes for single-record management. They are
grouped here because the codebase keeps an entity's wire DTOs in one module.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class NetworkNode(BaseModel):
    """A node in the relationship graph — a provider or an insured."""

    id: str
    label: str
    kind: Literal["proveedor", "asegurado"]
    ciudad: str
    casos: int
    alertas: int
    monto: float
    lista_restrictiva: bool = False  # only meaningful for proveedor nodes
    ramos: list[str] = []  # normalized ramo keys touched by this node's claims


class NetworkEdge(BaseModel):
    """A provider↔insured link built from the claims they share.

    A repeated pair (high `casos_compartidos`) is the core collusion signal —
    the same provider servicing the same insured across many claims.
    """

    proveedor_id: str
    asegurado_id: str
    casos_compartidos: int
    alertas: int
    monto: float


class NetworkRelations(BaseModel):
    """Bipartite relationship graph: provider + insured nodes joined by claims."""

    nodes: list[NetworkNode] = []
    edges: list[NetworkEdge] = []


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
