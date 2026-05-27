"""ORM model for `claim_narratives` — sentence embeddings of siniestros.descripcion.

Used by FS-13 (narrative similarity) via pgvector HNSW cosine index.
Per backend CLAUDE.md §8: embedding dimension = 384 (EMBEDDINGS_DIM).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base

if TYPE_CHECKING:
    from app.infrastructure.db.models.siniestro import Siniestro


class ClaimNarrative(Base):
    __tablename__ = "claim_narratives"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    claim_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("siniestros.id_siniestro", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)  # siniestros.descripcion copy
    embedding: Mapped[list[float]] = mapped_column(
        Vector(384), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    siniestro: Mapped[Siniestro] = relationship(
        "Siniestro", back_populates="narratives", lazy="noload"
    )
