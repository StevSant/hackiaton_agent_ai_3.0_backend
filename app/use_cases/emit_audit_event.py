"""Use case: append one audit event to the in-memory store.

Workflow routes (escalate / take / dictamen / close) call this after a state
change so the audit log reflects real activity. The signature deliberately
asks for the human-readable bits (title, detail) so each call site stays
the source of truth for its own wording — the use case just stamps the
timestamp, generates an id, and forwards to the store.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.domain.auth.user import User
from app.infrastructure.audit import AuditStore
from app.schemas.audit import AuditAction, AuditActor, AuditEventOut


async def emit_audit_event(
    store: AuditStore,
    *,
    user: User,
    action: AuditAction,
    title: str,
    detail: str,
    target: str | None = None,
    actor: AuditActor = AuditActor.analista,
) -> AuditEventOut:
    """Build and append an audit event; return the stored row."""
    event = AuditEventOut(
        id=f"ev_{uuid.uuid4().hex[:10]}",
        ts=datetime.now(tz=UTC),
        actor=actor,
        actor_name=user.full_name or user.email,
        action=action,
        title=title,
        detail=detail,
        target=target,
    )
    await store.append(event)
    return event
