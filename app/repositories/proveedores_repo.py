"""Repository for `beneficiarios_proveedores`."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.proveedor import Proveedor


class ProveedoresRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, id_proveedor: str) -> Proveedor | None:
        return await self._s.get(Proveedor, id_proveedor)

    async def upsert(self, proveedor: Proveedor) -> Proveedor:
        merged: Proveedor = await self._s.merge(proveedor)
        await self._s.flush()
        return merged
