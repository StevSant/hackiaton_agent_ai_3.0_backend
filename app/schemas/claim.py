"""Wire/API contract for claims — mirrors the frontend mock shape so generated
types drop into the existing Angular components with minimal churn.

`ClaimDetail` ≈ the frontend `Claim` interface, plus the explainability extras
(`ml_factors`, `similar`, `anomaly_score`) that feed the V8 accordions and aren't
in the FE mock yet. The deterministic scoring contract lives in `schemas/risk.py`.
"""

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.risk import FactorContribution, SimilarClaim, Tier

AlertSeverity = Literal["high", "med", "low"]
TimelineTone = Literal["ok", "warn", "danger"]


class ClaimAlert(BaseModel):
    """UI projection of a `RuleActivation`, rendered as a chip in the breakdown."""

    code: str
    puntos: int
    severidad: AlertSeverity
    detalle: str


class ClaimDocument(BaseModel):
    tipo: str
    estado: str
    falta: bool = False


class ClaimVehicle(BaseModel):
    marca: str
    modelo: str
    anio: int
    placa: str
    chasis: str | None = None


class ClaimTimelineEvent(BaseModel):
    date: str  # presentational label; the FE mock uses free-form date strings
    title: str
    tone: TimelineTone
    desc: str | None = None


class ReviewStatus(str, Enum):
    pendiente = "pendiente"
    escalado = "escalado"
    en_revision = "en_revision"
    dictaminado = "dictaminado"
    revisado_sin_escalar = "revisado_sin_escalar"


class DictamenOutcome(str, Enum):
    confirmado_sospecha = "confirmado_sospecha"
    descartado = "descartado"
    requiere_mas_info = "requiere_mas_info"


class ClaimReview(BaseModel):
    """1:1 audit trail of a claim's escalation workflow (5-state machine, §6 V2.6)."""

    status: ReviewStatus = ReviewStatus.pendiente
    escalated_by: str | None = None
    escalated_by_name: str | None = None
    escalated_at: datetime | None = None
    escalation_note: str | None = None
    assigned_to: str | None = None
    assigned_to_name: str | None = None
    taken_at: datetime | None = None
    dictamen_outcome: DictamenOutcome | None = None
    dictamen_justificacion: str | None = None
    dictaminado_by: str | None = None
    dictaminado_by_name: str | None = None
    dictaminado_at: datetime | None = None
    bounce_count: int = 0
    bounce_note: str | None = None
    closed_by: str | None = None
    closed_by_name: str | None = None
    closed_at: datetime | None = None
    closed_note: str | None = None


class ClaimSummary(BaseModel):
    """List-row projection returned by `GET /claims` (lighter than `ClaimDetail`)."""

    id: str
    ramo: str
    cobertura: str
    asegurado: str
    ciudad: str
    fecha_ocurrencia: date
    monto_reclamado: float
    estado: str
    score: int = Field(..., ge=0, le=100)
    nivel: Tier
    review_status: ReviewStatus = ReviewStatus.pendiente


class ClaimDetail(BaseModel):
    """Full claim returned by `GET /claims/{id}` — mirrors the FE `Claim` interface."""

    id: str
    ramo: str
    cobertura: str
    asegurado: str
    asegurado_id: str
    poliza: str
    ciudad: str
    fecha_ocurrencia: date
    fecha_reporte: date
    monto_reclamado: float
    suma_asegurada: float
    estado: str
    sucursal: str
    vehiculo: ClaimVehicle | None = None
    proveedor: str | None = None
    descripcion: str
    score: int = Field(..., ge=0, le=100)
    nivel: Tier
    alertas: list[ClaimAlert] = Field(default_factory=list)
    timeline: list[ClaimTimelineEvent] = Field(default_factory=list)
    documentos: list[ClaimDocument] = Field(default_factory=list)
    review: ClaimReview = Field(default_factory=ClaimReview)
    # explainability extras (not in the FE mock yet — feed the V8 accordions)
    ml_factors: list[FactorContribution] = Field(default_factory=list)
    similar: list[SimilarClaim] = Field(default_factory=list)
    anomaly_score: float | None = None


class ClaimPatch(BaseModel):
    """Debug fire-test patch — DEBUG_ENABLED-gated, antifraude only (§10)."""

    fecha_ocurrencia: date | None = None
    fecha_reporte: date | None = None
    monto_reclamado: float | None = None
    documentos_completos: bool | None = None
