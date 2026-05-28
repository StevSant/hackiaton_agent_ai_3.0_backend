"""Repository for `asegurados` — insured persons."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.asegurado import Asegurado


class AseguradosRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, id_asegurado: str) -> Asegurado | None:
        return await self._s.get(Asegurado, id_asegurado)

    async def upsert(self, asegurado: Asegurado) -> Asegurado:
        merged: Asegurado = await self._s.merge(asegurado)
        await self._s.flush()
        return merged

    async def delete(self, id_asegurado: str) -> bool:
        entity = await self._s.get(Asegurado, id_asegurado)
        if entity is None:
            return False
        await self._s.delete(entity)
        await self._s.flush()
        return True
