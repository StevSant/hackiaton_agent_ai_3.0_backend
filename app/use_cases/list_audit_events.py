"""Use case: return the audit log (ordered most-recent first)."""

from __future__ import annotations

from app.schemas.audit import AuditEventOut
from app.use_cases._seeds.audit_seed import AUDIT_EVENTS


async def list_audit_events(*, limit: int | None = None) -> list[AuditEventOut]:
    events = sorted(AUDIT_EVENTS, key=lambda e: e.ts, reverse=True)
    if limit is not None:
        events = events[:limit]
    return events
