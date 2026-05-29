"""ORM model for `beneficiarios_proveedores` — providers / beneficiaries.

Field names are Spanish snake_case per root CLAUDE.md §2.8 (verbatim contract).
`porcentaje_casos_observados` is a pre-aggregated signal used by FS-07.
`en_lista_restrictiva` is the ground-truth from the dataset (RF-03 prefers it
over the heuristic based on `porcentaje_casos_observados`).
"""

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class Proveedor(Base):
    __tablename__ = "beneficiarios_proveedores"

    id_proveedor: Mapped[str] = mapped_column(String(64), primary_key=True)

    nombre: Mapped[str | None] = mapped_column(String(160), nullable=True)
    tipo: Mapped[str] = mapped_column(String(80), nullable=False)  # Beneficiario / Proveedor
    ciudad: Mapped[str] = mapped_column(String(100), nullable=False)
    reclamos_asociados: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    monto_promedio_reclamado: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    porcentaje_casos_observados: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    antiguedad: Mapped[int | None] = mapped_column(Integer, nullable=True)  # months

    # Ground-truth from the evento dataset (0021_evento_fields migration).
    # Preferred by RF-03 + FS-07 over the heuristic when not None.
    en_lista_restrictiva: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    motivo_restriccion: Mapped[str | None] = mapped_column(String(255), nullable=True)
