"""ORM model for `asegurados` — insured persons.

Field names are Spanish snake_case per root CLAUDE.md §2.8 (verbatim contract).
`score_cliente_simulado` is a synthetic trust indicator — not from real data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base

if TYPE_CHECKING:
    from app.infrastructure.db.models.poliza import Poliza
    from app.infrastructure.db.models.siniestro import Siniestro


class Asegurado(Base):
    __tablename__ = "asegurados"

    id_asegurado: Mapped[str] = mapped_column(String(64), primary_key=True)

    nombre: Mapped[str | None] = mapped_column(String(160), nullable=True)
    segmento: Mapped[str | None] = mapped_column(String(80), nullable=True)
    antiguedad: Mapped[int | None] = mapped_column(Integer, nullable=True)  # years
    ciudad: Mapped[str] = mapped_column(String(100), nullable=False)
    num_polizas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reclamos_ultimos_12_meses: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    mora_actual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    score_cliente_simulado: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Ground-truth from the evento dataset (0021_evento_fields migration).
    # `reclamos_rc_sin_tercero` feeds FS-06 directly when not None.
    reclamos_historico_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reclamos_rc_sin_tercero: Mapped[int | None] = mapped_column(Integer, nullable=True)
    perfil_riesgo: Mapped[str | None] = mapped_column(String(80), nullable=True)

    polizas: Mapped[list[Poliza]] = relationship(
        "Poliza", back_populates="asegurado", lazy="noload"
    )
    siniestros: Mapped[list[Siniestro]] = relationship(
        "Siniestro", back_populates="asegurado", lazy="noload"
    )
