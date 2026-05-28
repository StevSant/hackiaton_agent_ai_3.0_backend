"""Use case: delete a single provider / beneficiary."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.repositories.proveedores_repo import ProveedoresRepo


async def delete_provider(session: AsyncSession, id_proveedor: str) -> None:
    repo = ProveedoresRepo(session)
    if not await repo.delete(id_proveedor):
        raise NotFound(f"Proveedor {id_proveedor} no encontrado")
    await session.commit()
