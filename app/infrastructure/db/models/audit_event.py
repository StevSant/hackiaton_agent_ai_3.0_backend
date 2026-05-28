"""ORM model for `audit_events` — append-only analyst + system activity log.

Persists every audited action (escalation, take, dictamen, close, AI query,
import, export) so the Auditoría page survives restarts / `--reload`. Mirrors
the ``AuditEventOut`` wire schema field-for-field; ``actor`` and ``action`` are
stored as their string enum values.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    actor: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    actor_name: Mapped[str] = mapped_column(String(160), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    target: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
