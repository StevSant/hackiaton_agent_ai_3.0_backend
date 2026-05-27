"""ORM model for `claim_reviews` — 5-state workflow audit trail per design spec §6 V2.6.

PK is `claim_id` (1:1 FK to siniestros).  The row is created on first escalation
or when the claim is first loaded (status=pendiente).

State machine:
    pendiente → escalado → en_revision → dictaminado → revisado_sin_escalar
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base

if TYPE_CHECKING:
    from app.infrastructure.db.models.siniestro import Siniestro


class ClaimReview(Base):
    __tablename__ = "claim_reviews"

    claim_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("siniestros.id_siniestro", ondelete="CASCADE"),
        primary_key=True,
    )

    # Allowed: pendiente / escalado / en_revision / dictaminado / revisado_sin_escalar
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="pendiente", index=True
    )

    # Escalation (analista action)
    escalated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    escalation_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Assignment / acceptance (antifraude action)
    assigned_to: Mapped[str | None] = mapped_column(String(128), nullable=True)
    taken_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Dictamen (antifraude resolution)
    # Allowed: confirmado_sospecha / descartado / requiere_mas_info
    dictamen_outcome: Mapped[str | None] = mapped_column(String(40), nullable=True)
    dictamen_justificacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    dictaminado_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dictaminado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Bounce / re-escalation tracking
    bounce_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bounce_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Close (final state, either side)
    closed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    siniestro: Mapped[Siniestro] = relationship(
        "Siniestro", back_populates="review", lazy="noload"
    )
