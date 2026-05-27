"""Wire schema for GET /network/providers — provider risk-network view."""

from __future__ import annotations

from pydantic import BaseModel


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
