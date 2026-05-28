"""DB-backed audit store — persists events to the `audit_events` table.

Each append/read runs in its OWN short transaction (via the session factory),
independent of the request/SSE session. That keeps audit durability decoupled
from the surrounding request — the agent's SSE route can emit a `consulta_ia`
event without entangling it in the long-lived streaming response, and an audit
write never rolls back just because some later step in the request failed.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.models.audit_event import AuditEvent
from app.schemas.audit import AuditAction, AuditActor, AuditEventOut


class DbAuditStore:
    """`AuditStore` implementation persisting to Postgres `audit_events`."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def append(self, event: AuditEventOut) -> None:
        async with self._sf() as session:
            session.add(_to_row(event))
            await session.commit()

    async def list_all(self) -> list[AuditEventOut]:
        async with self._sf() as session:
            rows = (
                (await session.execute(select(AuditEvent).order_by(AuditEvent.ts.desc())))
                .scalars()
                .all()
            )
            return [_to_out(r) for r in rows]

    async def list_recent(self, limit: int) -> list[AuditEventOut]:
        async with self._sf() as session:
            rows = (
                (
                    await session.execute(
                        select(AuditEvent).order_by(AuditEvent.ts.desc()).limit(limit)
                    )
                )
                .scalars()
                .all()
            )
            return [_to_out(r) for r in rows]


def _to_row(event: AuditEventOut) -> AuditEvent:
    return AuditEvent(
        id=event.id,
        ts=event.ts,
        actor=event.actor.value,
        actor_name=event.actor_name,
        action=event.action.value,
        title=event.title,
        detail=event.detail,
        target=event.target,
    )


def _to_out(row: AuditEvent) -> AuditEventOut:
    return AuditEventOut(
        id=row.id,
        ts=row.ts,
        actor=AuditActor(row.actor),
        actor_name=row.actor_name,
        action=AuditAction(row.action),
        title=row.title,
        detail=row.detail,
        target=row.target,
    )
