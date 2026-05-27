"""Repository for `siniestros` — typed, async, no business logic.

All methods take an `AsyncSession` injected by the caller (use case layer).
The `id` used here is `id_siniestro` (DB column); the wire DTO uses `id` —
that mapping lives in the use-case / projection layer.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.siniestro import Siniestro

# Allowed scalar types for partial-update fields (no bare Any in public signatures — §2).
_FieldValue = str | int | float | bool | date | None


class ClaimsRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, id_siniestro: str) -> Siniestro | None:
        result = await self._s.get(Siniestro, id_siniestro)
        return result

    async def list_paginated(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Siniestro], int]:
        """Return (rows, total_count).

        tier and ciudad filters are deferred to L4 (require joins to claim_scores
        and polizas respectively).  Removed from signature to avoid silent no-ops.
        """
        stmt = select(Siniestro)
        count_stmt = select(func.count()).select_from(Siniestro)

        total: int = (await self._s.execute(count_stmt)).scalar_one()
        rows_result = await self._s.execute(stmt.offset(offset).limit(limit))
        rows: list[Siniestro] = list(rows_result.scalars().all())
        return rows, total

    async def upsert(self, siniestro: Siniestro) -> Siniestro:
        """Merge (insert-or-update) a siniestro and return the persisted instance."""
        merged: Siniestro = await self._s.merge(siniestro)
        await self._s.flush()
        return merged

    async def update_fields(
        self, id_siniestro: str, fields: dict[str, _FieldValue]
    ) -> Siniestro | None:
        """Partial update — used by the PATCH debug endpoint (antifraude, §6b)."""
        instance = await self.get_by_id(id_siniestro)
        if instance is None:
            return None
        for key, value in fields.items():
            setattr(instance, key, value)
        await self._s.flush()
        return instance
