"""Use case: create a single asegurado (insured person)."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationFailed
from app.infrastructure.db.models.asegurado import Asegurado
from app.repositories.asegurados_repo import AseguradosRepo
from app.schemas.asegurados import AseguradoCreate, AseguradoOut
from app.use_cases.asegurado_to_out import asegurado_to_out


async def create_asegurado(session: AsyncSession, data: AseguradoCreate) -> AseguradoOut:
    repo = AseguradosRepo(session)
    ase_id = data.id_asegurado or f"ASG-{uuid4().hex[:8].upper()}"
    if await repo.get_by_id(ase_id) is not None:
        raise ValidationFailed(f"El asegurado {ase_id} ya existe")
    entity = Asegurado(
        id_asegurado=ase_id,
        nombre=data.nombre,
        segmento=data.segmento,
        ciudad=data.ciudad,
        antiguedad=data.antiguedad,
        num_polizas=data.num_polizas,
        reclamos_ultimos_12_meses=data.reclamos_ultimos_12_meses,
        mora_actual=data.mora_actual,
        score_cliente_simulado=data.score_cliente_simulado,
    )
    saved = await repo.upsert(entity)
    await session.commit()
    return asegurado_to_out(saved)
