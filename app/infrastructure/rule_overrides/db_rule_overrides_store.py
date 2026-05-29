"""DB-backed rule-overrides store — persists to the `rule_overrides` table.

Each read/write runs in its own short transaction via the session factory,
decoupled from the request session (same policy as ``DbAuditStore``).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.models.rule_override import RuleOverride
from app.infrastructure.rule_overrides.record import RuleOverrideRecord


class DbRuleOverridesStore:
    """``RuleOverridesStore`` implementation persisting to Postgres."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def list_all(self) -> list[RuleOverrideRecord]:
        async with self._sf() as session:
            rows = (await session.execute(select(RuleOverride))).scalars().all()
            return [_to_record(r) for r in rows]

    async def get(self, code: str) -> RuleOverrideRecord | None:
        async with self._sf() as session:
            row = await session.get(RuleOverride, code)
            return _to_record(row) if row is not None else None

    async def upsert(
        self,
        code: str,
        *,
        enabled: bool,
        thresholds: dict[str, Any],
        updated_by: str | None,
    ) -> RuleOverrideRecord:
        async with self._sf() as session:
            row = await session.get(RuleOverride, code)
            if row is None:
                row = RuleOverride(code=code)
                session.add(row)
            row.enabled = enabled
            row.thresholds = dict(thresholds)
            row.updated_by = updated_by
            await session.commit()
            return _to_record(row)


def _to_record(row: RuleOverride) -> RuleOverrideRecord:
    return RuleOverrideRecord(
        code=row.code,
        enabled=row.enabled,
        thresholds=dict(row.thresholds or {}),
    )
