"""ORM model for `claim_scores` — persisted output of the `score_claim` use case.

Stores the full explainability payload (activations, ml_factors, similar)
as JSON columns so the detail page can render without re-scoring.
`claim_id` is a 1:1 FK to siniestros (most-recent score wins; historical
scoring can use the `computed_at` field for audit).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base

if TYPE_CHECKING:
    from app.infrastructure.db.models.siniestro import Siniestro


class ClaimScore(Base):
    __tablename__ = "claim_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("siniestros.id_siniestro", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    score: Mapped[int] = mapped_column(Integer, nullable=False)
    # Tier string: "verde" | "amarillo" | "rojo"
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    # list[RuleActivation] serialised as JSONB — shape: list[{code, tier_hint, points, evidence}]
    activations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    ml_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    # list[FactorContribution] serialised as JSONB — shape: list[{feature, shap_value, direction}]
    ml_factors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    anomaly_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # list[SimilarClaim] serialised as JSONB — shape: list[{claim_id, similarity, excerpt}]
    similar: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    # NarrativeAnalysis serialised as JSONB (entidades + narrativa_ilogica +
    # incoherencias + resumen_narrativa). Null until the NLP analyzer has run.
    narrative_analysis: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, default=None
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    siniestro: Mapped[Siniestro] = relationship(
        "Siniestro", back_populates="score", lazy="noload"
    )
