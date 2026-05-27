"""Request / response schemas for the V2.6 escalation workflow endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.claim import DictamenOutcome
from app.schemas.risk import Tier


class EscalateRequest(BaseModel):
    note: str | None = Field(None, description="Nota opcional para el equipo antifraude")


class CloseRequest(BaseModel):
    note: str | None = Field(None, description="Nota opcional al cerrar sin escalar")


class DictamenRequest(BaseModel):
    outcome: DictamenOutcome
    justificacion: str = Field(
        ...,
        min_length=20,
        description="Justificación mínima de 20 caracteres",
    )


class InboxRow(BaseModel):
    """Single row in the antifraude inbox (GET /antifraude/inbox)."""

    claim_id: str
    asegurado: str
    ramo: str
    score: int = Field(..., ge=0, le=100)
    nivel: Tier
    escalated_at: datetime | None = None
    escalation_note_preview: str | None = None  # first 120 chars
    assigned_to_name: str | None = None
    bounce_count: int = 0
