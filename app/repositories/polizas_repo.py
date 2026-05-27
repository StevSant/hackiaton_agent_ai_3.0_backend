"""Repository for `polizas` — insurance policies."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.poliza import Poliza


class PolizasRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, id_poliza: str) -> Poliza | None:
        return await self._s.get(Poliza, id_poliza)

    async def list_by_asegurado(self, id_asegurado: str) -> list[Poliza]:
        stmt = select(Poliza).where(Poliza.id_asegurado == id_asegurado)
        result = await self._s.execute(stmt)
        return list(result.scalars().all())

    async def upsert(self, poliza: Poliza) -> Poliza:
        merged: Poliza = await self._s.merge(poliza)
        await self._s.flush()
        return merged
