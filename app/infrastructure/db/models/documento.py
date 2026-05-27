"""ORM model for `documentos` — documents attached to a claim.

Field names are Spanish snake_case per root CLAUDE.md §2.8 (verbatim contract).
`inconsistencia_detectada` feeds FS-11 (document inconsistency rule).
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base

if TYPE_CHECKING:
    from app.infrastructure.db.models.siniestro import Siniestro


class Documento(Base):
    __tablename__ = "documentos"

    id_documento: Mapped[str] = mapped_column(String(64), primary_key=True)
    id_siniestro: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("siniestros.id_siniestro", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    tipo_documento: Mapped[str] = mapped_column(String(120), nullable=False)
    entregado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    legible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_emision: Mapped[date | None] = mapped_column(Date, nullable=True)
    inconsistencia_detectada: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    observacion: Mapped[str | None] = mapped_column(Text, nullable=True)

    siniestro: Mapped[Siniestro] = relationship(
        "Siniestro", back_populates="documentos", lazy="noload"
    )
