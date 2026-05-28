"""Use case: delete a single asegurado (insured person)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.repositories.asegurados_repo import AseguradosRepo


async def delete_asegurado(session: AsyncSession, id_asegurado: str) -> None:
    repo = AseguradosRepo(session)
    if not await repo.delete(id_asegurado):
        raise NotFound(f"Asegurado {id_asegurado} no encontrado")
    await session.commit()
