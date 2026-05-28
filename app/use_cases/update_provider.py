"""Use case: update a single provider / beneficiary (partial)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.repositories.proveedores_repo import ProveedoresRepo
from app.schemas.network import ProviderOut, ProviderUpdate
from app.use_cases.provider_to_out import provider_to_out


async def update_provider(
    session: AsyncSession, id_proveedor: str, data: ProviderUpdate
) -> ProviderOut:
    repo = ProveedoresRepo(session)
    entity = await repo.get_by_id(id_proveedor)
    if entity is None:
        raise NotFound(f"Proveedor {id_proveedor} no encontrado")

    payload = data.model_dump(exclude_unset=True)
    if "lista_restrictiva" in payload:
        restrictive = payload.pop("lista_restrictiva")
        entity.porcentaje_casos_observados = 1.0 if restrictive else 0.0
    for field, value in payload.items():
        setattr(entity, field, value)

    saved = await repo.upsert(entity)
    await session.commit()
    return provider_to_out(saved)
