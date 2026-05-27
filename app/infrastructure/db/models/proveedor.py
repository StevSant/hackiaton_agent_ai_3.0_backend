"""ORM model for `beneficiarios_proveedores` — providers / beneficiaries.

Field names are Spanish snake_case per root CLAUDE.md §2.8 (verbatim contract).
`porcentaje_casos_observados` is a pre-aggregated signal used by FS-07.
"""

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class Proveedor(Base):
    __tablename__ = "beneficiarios_proveedores"

    id_proveedor: Mapped[str] = mapped_column(String(64), primary_key=True)

    tipo: Mapped[str] = mapped_column(String(80), nullable=False)  # Beneficiario / Proveedor
    ciudad: Mapped[str] = mapped_column(String(100), nullable=False)
    reclamos_asociados: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    monto_promedio_reclamado: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    porcentaje_casos_observados: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    antiguedad: Mapped[int | None] = mapped_column(Integer, nullable=True)  # months
