"""DB-backed rule-change log — persists to the `rule_changes` table.

Each append/read runs in its own short transaction via the session factory
(same policy as ``DbAuditStore``) so the "Historial de cambios" modal survives
restarts / ``--reload``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.models.rule_change import RuleChange
from app.schemas.rule_changes import RuleChangeKind, RuleChangeOut


class DbRuleChangesStore:
    """``RuleChangesStore`` implementation persisting to Postgres."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def append(self, change: RuleChangeOut) -> None:
        async with self._sf() as session:
            session.add(_to_row(change))
            await session.commit()

    async def list_all(self) -> list[RuleChangeOut]:
        async with self._sf() as session:
            rows = (
                (await session.execute(select(RuleChange).order_by(RuleChange.ts.desc())))
                .scalars()
                .all()
            )
            return [_to_out(r) for r in rows]

    async def list_recent(self, limit: int) -> list[RuleChangeOut]:
        async with self._sf() as session:
            rows = (
                (
                    await session.execute(
                        select(RuleChange).order_by(RuleChange.ts.desc()).limit(limit)
                    )
                )
                .scalars()
                .all()
            )
            return [_to_out(r) for r in rows]


def _to_row(change: RuleChangeOut) -> RuleChange:
    return RuleChange(
        id=change.id,
        ts=change.ts,
        actor=change.actor,
        rule_code=change.rule_code,
        rule_name=change.rule_name,
        kind=change.kind.value,
        summary=change.summary,
        before_value=change.before_value,
        after_value=change.after_value,
    )


def _to_out(row: RuleChange) -> RuleChangeOut:
    return RuleChangeOut(
        id=row.id,
        ts=row.ts,
        actor=row.actor,
        rule_code=row.rule_code,
        rule_name=row.rule_name,
        kind=RuleChangeKind(row.kind),
        summary=row.summary,
        before_value=row.before_value,
        after_value=row.after_value,
    )
