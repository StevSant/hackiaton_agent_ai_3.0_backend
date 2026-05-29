"""ORM model for `rule_overrides` — persisted runtime state of each fraud rule.

One row per rule code that has been edited from the dashboard. ``enabled``
captures pause/reactivate; ``thresholds`` holds a partial JSON overlay merged on
top of ``config.yaml`` at evaluation time. Rules with no row run with their
shipped defaults (see ``domain.rules.defaults``). Survives restarts so a paused
rule stays paused across ``--reload``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class RuleOverride(Base):
    __tablename__ = "rule_overrides"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Partial overlay on config.yaml (e.g. {"tier1_days": 7}); empty when only
    # the enabled flag was changed.
    thresholds: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    updated_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
