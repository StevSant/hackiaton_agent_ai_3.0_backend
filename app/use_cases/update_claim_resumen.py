"""Persist an analyst-edited case summary on a siniestro."""

from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.siniestro import Siniestro


async def update_claim_resumen(
    session: AsyncSession, claim_id: str, resumen_editado: str
) -> bool:
    """Set resumen_editado for a claim. Returns False if the claim doesn't exist."""
    result = await session.execute(
        update(Siniestro)
        .where(Siniestro.id_siniestro == claim_id)
        .values(resumen_editado=resumen_editado)
    )
    await session.commit()
    return result.rowcount > 0
