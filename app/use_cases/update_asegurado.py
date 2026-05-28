"""Use case: update a single asegurado (insured person) — partial."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.repositories.asegurados_repo import AseguradosRepo
from app.schemas.asegurados import AseguradoOut, AseguradoUpdate
from app.use_cases.asegurado_to_out import asegurado_to_out


async def update_asegurado(
    session: AsyncSession, id_asegurado: str, data: AseguradoUpdate
) -> AseguradoOut:
    repo = AseguradosRepo(session)
    entity = await repo.get_by_id(id_asegurado)
    if entity is None:
        raise NotFound(f"Asegurado {id_asegurado} no encontrado")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(entity, field, value)

    saved = await repo.upsert(entity)
    await session.commit()
    return asegurado_to_out(saved)
