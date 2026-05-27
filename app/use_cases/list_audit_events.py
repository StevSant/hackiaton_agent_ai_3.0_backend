"""Use case: return the audit log (ordered most-recent first).

Reads from the in-memory audit store. Events are appended by the
escalate / take / dictamen / close use cases as they run — the store
starts empty so the log reflects real activity rather than seeded mocks.
"""

from __future__ import annotations

from app.infrastructure.audit import InMemoryAuditStore
from app.schemas.audit import AuditEventOut


async def list_audit_events(
    store: InMemoryAuditStore,
    *,
    limit: int | None = None,
) -> list[AuditEventOut]:
    if limit is not None:
        return store.list_recent(limit)
    return store.list_all()
