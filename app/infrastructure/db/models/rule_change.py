"""ORM model for `rule_changes` — append-only audit log of rule-config edits.

Every pause / reactivate / threshold change made from the dashboard appends one
row here so the "Historial de cambios" modal survives restarts. Mirrors the
``RuleChangeOut`` wire schema field-for-field; ``kind`` is stored as its string
enum value.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class RuleChange(Base):
    __tablename__ = "rule_changes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    actor: Mapped[str] = mapped_column(String(160), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    before_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
