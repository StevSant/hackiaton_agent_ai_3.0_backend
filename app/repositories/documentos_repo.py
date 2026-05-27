"""Repository for `documentos` — claim documents."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.documento import Documento


class DocumentosRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, id_documento: str) -> Documento | None:
        return await self._s.get(Documento, id_documento)

    async def list_by_siniestro(self, id_siniestro: str) -> list[Documento]:
        stmt = select(Documento).where(Documento.id_siniestro == id_siniestro)
        result = await self._s.execute(stmt)
        return list(result.scalars().all())

    async def upsert(self, documento: Documento) -> Documento:
        merged: Documento = await self._s.merge(documento)
        await self._s.flush()
        return merged
