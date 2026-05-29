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


class NetworkClaim(BaseModel):
    """A claim (siniestro) that links a provider to an insured.

    Surfaced so the frontend can render case-centric relationship views
    (provider↔caso, asegurado↔caso, and the tripartite provider—caso—insured
    chain) without a second round-trip. Only claims belonging to a surfaced
    suspicious provider↔insured pair are included, capped for readability.
    """

    id: str
    label: str
    proveedor_id: str | None = None
    asegurado_id: str
    ramo: str  # normalized ramo key
    ciudad: str
    monto: float
    score: int
    tier: str  # "verde" | "amarillo" | "rojo"
    alerta: bool  # tier in {amarillo, rojo}


class NetworkRelations(BaseModel):
    """Relationship graph: provider + insured nodes joined by claims, plus the
    claims themselves so the UI can pivot between provider, insured and case views."""

    nodes: list[NetworkNode] = []
    edges: list[NetworkEdge] = []
    casos: list[NetworkClaim] = []


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
