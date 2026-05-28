"""Use case: create a single provider / beneficiary."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationFailed
from app.infrastructure.db.models.proveedor import Proveedor
from app.repositories.proveedores_repo import ProveedoresRepo
from app.schemas.network import ProviderCreate, ProviderOut
from app.use_cases.provider_to_out import provider_to_out


async def create_provider(session: AsyncSession, data: ProviderCreate) -> ProviderOut:
    repo = ProveedoresRepo(session)
    prov_id = data.id_proveedor or f"PRV-{uuid4().hex[:8].upper()}"
    if await repo.get_by_id(prov_id) is not None:
        raise ValidationFailed(f"El proveedor {prov_id} ya existe")
    entity = Proveedor(
        id_proveedor=prov_id,
        nombre=data.nombre,
        tipo=data.tipo,
        ciudad=data.ciudad,
        antiguedad=data.antiguedad,
        reclamos_asociados=data.reclamos_asociados,
        monto_promedio_reclamado=data.monto_promedio_reclamado,
        porcentaje_casos_observados=1.0 if data.lista_restrictiva else 0.0,
    )
    saved = await repo.upsert(entity)
    await session.commit()
    return provider_to_out(saved)
