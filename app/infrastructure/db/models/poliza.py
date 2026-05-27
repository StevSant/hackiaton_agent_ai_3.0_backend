"""ORM model for `polizas` — insurance policies.

Field names are Spanish snake_case per root CLAUDE.md §2.8 (verbatim contract).
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base

if TYPE_CHECKING:
    from app.infrastructure.db.models.asegurado import Asegurado
    from app.infrastructure.db.models.siniestro import Siniestro


class Poliza(Base):
    __tablename__ = "polizas"

    id_poliza: Mapped[str] = mapped_column(String(64), primary_key=True)
    id_asegurado: Mapped[str] = mapped_column(
        String(64), ForeignKey("asegurados.id_asegurado"), nullable=False, index=True
    )

    ramo: Mapped[str] = mapped_column(String(120), nullable=False)
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[date] = mapped_column(Date, nullable=False)
    prima: Mapped[float] = mapped_column(Float, nullable=False)
    suma_asegurada: Mapped[float] = mapped_column(Float, nullable=False)
    deducible: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    canal_venta: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ciudad: Mapped[str] = mapped_column(String(100), nullable=False)
    estado_poliza: Mapped[str] = mapped_column(String(60), nullable=False)

    asegurado: Mapped[Asegurado] = relationship(
        "Asegurado", back_populates="polizas", lazy="noload"
    )
    siniestros: Mapped[list[Siniestro]] = relationship(
        "Siniestro", back_populates="poliza", lazy="noload"
    )
