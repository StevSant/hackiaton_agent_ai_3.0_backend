"""Map a `Proveedor` entity to `ProviderOut` (best-effort, no aggregation).

Used by the single-record create/update endpoints. The aggregate fields
(`alertas`, `ramos`) require the grouped query in `list_providers`; here we fall
back to the provider's own pre-aggregated columns, mirroring that use case's
zero-claims branch. The frontend reloads the full list after a mutation, so this
response is just an optimistic echo.
"""

from __future__ import annotations

from app.infrastructure.db.models.proveedor import Proveedor
from app.schemas.network import ProviderOut

# Same threshold list_providers uses to flag a provider as restrictive.
_RESTRICTIVE_THRESHOLD = 0.5


def provider_to_out(p: Proveedor) -> ProviderOut:
    return ProviderOut(
        id_proveedor=p.id_proveedor,
        nombre=p.nombre or f"{p.tipo} {p.id_proveedor}",
        tipo=p.tipo,
        ciudad=p.ciudad,
        casos=p.reclamos_asociados,
        alertas=0,
        monto=p.monto_promedio_reclamado * max(p.reclamos_asociados, 1),
        lista_restrictiva=p.porcentaje_casos_observados >= _RESTRICTIVE_THRESHOLD,
        ramos=[],
    )
