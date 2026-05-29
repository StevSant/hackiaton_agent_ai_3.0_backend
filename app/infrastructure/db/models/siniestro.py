"""ORM model for `siniestros` — insurance claim records.

Field names are Spanish snake_case per root CLAUDE.md §2.8 (verbatim contract).
`etiqueta_fraude_simulada` (0/1) is for training/eval only — never surface to users.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base

if TYPE_CHECKING:
    from app.infrastructure.db.models.asegurado import Asegurado
    from app.infrastructure.db.models.claim_narrative import ClaimNarrative
    from app.infrastructure.db.models.claim_review import ClaimReview
    from app.infrastructure.db.models.claim_score import ClaimScore
    from app.infrastructure.db.models.documento import Documento
    from app.infrastructure.db.models.poliza import Poliza


class Siniestro(Base):
    __tablename__ = "siniestros"

    id_siniestro: Mapped[str] = mapped_column(String(64), primary_key=True)
    id_poliza: Mapped[str] = mapped_column(
        String(64), ForeignKey("polizas.id_poliza"), nullable=False, index=True
    )
    id_asegurado: Mapped[str] = mapped_column(
        String(64), ForeignKey("asegurados.id_asegurado"), nullable=False, index=True
    )
    workspace_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )

    ramo: Mapped[str] = mapped_column(String(120), nullable=False)
    cobertura: Mapped[str] = mapped_column(String(120), nullable=False)

    fecha_ocurrencia: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_reporte: Mapped[date] = mapped_column(Date, nullable=False)

    monto_reclamado: Mapped[float] = mapped_column(Float, nullable=False)
    monto_estimado: Mapped[float | None] = mapped_column(Float, nullable=True)
    monto_pagado: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Allowed values: Reserva / Pago Total / Pago Parcial / Anticipo /
    #                 Negativa / Cierre Sin Consecuencia / Liquidado
    estado: Mapped[str] = mapped_column(String(60), nullable=False)
    sucursal: Mapped[str] = mapped_column(String(120), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    resumen_editado: Mapped[str | None] = mapped_column(Text, nullable=True)

    documentos_completos: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    beneficiario: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Pre-computed derived fields from ingestion (save repeated DB math in rules).
    dias_desde_inicio_poliza: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dias_desde_fin_poliza: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dias_entre_ocurrencia_reporte: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    historial_siniestros_asegurado: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # Investigator / NLP-provided ground-truth facts that can't be derived from
    # relationships (impossible dynamics, no third-party trace, falsification,
    # cloned narrative, etc.). Consumed by build_rule_context_from_db, where they
    # OVERLAY the values derived from dates / amounts / related rows so the rules
    # engine produces a genuine score instead of a hand-authored one.
    signals: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    # Training / eval label — 0=legítimo simulado, 1=fraude simulado.
    # NEVER surface this to users or the API response (§2.2).
    etiqueta_fraude_simulada: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # Ground-truth from the evento dataset (0021_evento_fields migration).
    # `similitud_narrativa_max` feeds FS-13 directly when not None, bypassing the
    # pgvector similarity lookup (which still serves as fallback).
    numero_parte_policial: Mapped[str | None] = mapped_column(String(80), nullable=True)
    similitud_narrativa_max: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Optional vehicle attributes (applicable when ramo="Vehículos")
    placa: Mapped[str | None] = mapped_column(String(20), nullable=True)
    chasis: Mapped[str | None] = mapped_column(String(40), nullable=True)
    motor: Mapped[str | None] = mapped_column(String(40), nullable=True)
    marca: Mapped[str | None] = mapped_column(String(80), nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # §2.8 field is "año"; Python identifiers can't contain ñ
    anio: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Per-claim coordinates (WGS84). Derived from the sucursal's city center
    # plus deterministic jitter so each claim renders at a stable spot on the
    # insights map. Nullable so older rows or rows with unknown cities are OK.
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships (lazy by default — explicit join when needed)
    poliza: Mapped[Poliza] = relationship(
        "Poliza", back_populates="siniestros", lazy="noload"
    )
    asegurado: Mapped[Asegurado] = relationship(
        "Asegurado", back_populates="siniestros", lazy="noload"
    )
    documentos: Mapped[list[Documento]] = relationship(
        "Documento",
        back_populates="siniestro",
        lazy="noload",
        cascade="all, delete-orphan",
    )
    score: Mapped[ClaimScore | None] = relationship(
        "ClaimScore",
        back_populates="siniestro",
        uselist=False,
        lazy="noload",
        cascade="all, delete-orphan",
    )
    review: Mapped[ClaimReview | None] = relationship(
        "ClaimReview",
        back_populates="siniestro",
        uselist=False,
        lazy="noload",
        cascade="all, delete-orphan",
    )
    narratives: Mapped[list[ClaimNarrative]] = relationship(
        "ClaimNarrative",
        back_populates="siniestro",
        lazy="noload",
        cascade="all, delete-orphan",
    )
