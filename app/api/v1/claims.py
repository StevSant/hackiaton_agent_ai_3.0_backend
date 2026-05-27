"""Claims API — THIN router: parse → use case → return.

Routes:
    GET  /claims                → Page[ClaimSummary]   (any authenticated user)
    GET  /claims/{id}           → ClaimDetail          (any authenticated user)
    POST /claims/{id}/rescore   → ClaimRiskScore        (any authenticated user)
    PATCH /claims/{id}          → ClaimDetail          (DEBUG_ENABLED + antifraude only)
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.api.deps import (
    get_anomaly_detector,
    get_audit_store,
    get_claim_queries_dep,
    get_current_user,
    get_fraud_classifier,
    get_reviews_store,
    require_role,
)
from app.core.config import settings
from app.domain.anomaly import AnomalyDetector
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.domain.ml import FraudClassifier
from app.domain.rules.catalog import get_meta
from app.domain.rules.context import RuleContext
from app.infrastructure.audit import InMemoryAuditStore
from app.infrastructure.reviews.in_memory_reviews_store import InMemoryReviewsStore
from app.schemas.audit import AuditAction
from app.schemas.claim import ClaimAlert, ClaimDetail, ClaimPatch, ClaimSummary, ReviewStatus
from app.schemas.page import Page
from app.schemas.risk import ClaimRiskScore, Tier
from app.use_cases.emit_audit_event import emit_audit_event
from app.use_cases.enrich_claim_score import enrich_claim_score
from app.use_cases.get_claim_detail import _tier_to_severidad, get_claim_detail
from app.use_cases.list_claims import list_claims
from app.use_cases.score_claim import score_claim

router = APIRouter(prefix="/claims", tags=["claims"])


@router.get("", response_model=Page[ClaimSummary])
async def list_claims_route(
    tier: Tier | None = None,
    ramo: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    status_filter: ReviewStatus | None = None,
    q: str | None = None,
    page: int = 0,
    page_size: Annotated[int, Query(ge=1, le=500)] = 25,
    queries: Annotated[ClaimQueries, Depends(get_claim_queries_dep)] = ...,  # type: ignore[assignment]
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> Page[ClaimSummary]:
    return await list_claims(
        queries,
        tier=tier,
        ramo=ramo,
        from_date=from_date,
        to_date=to_date,
        status=status_filter,
        q=q,
        page=page,
        page_size=page_size,
    )


@router.get("/{claim_id}", response_model=ClaimDetail)
async def get_claim_detail_route(
    claim_id: str,
    queries: Annotated[ClaimQueries, Depends(get_claim_queries_dep)] = ...,  # type: ignore[assignment]
    reviews_store: Annotated[InMemoryReviewsStore, Depends(get_reviews_store)] = ...,  # type: ignore[assignment]
    classifier: Annotated[FraudClassifier | None, Depends(get_fraud_classifier)] = None,
    detector: Annotated[AnomalyDetector | None, Depends(get_anomaly_detector)] = None,
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> ClaimDetail:
    detail = await get_claim_detail(
        queries,
        claim_id,
        reviews_store=reviews_store,
        classifier=classifier,
        detector=detector,
    )
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Siniestro no encontrado"
        )
    return detail


@router.post("/{claim_id}/rescore", response_model=ClaimRiskScore)
async def rescore_claim_route(
    claim_id: str,
    queries: Annotated[ClaimQueries, Depends(get_claim_queries_dep)] = ...,  # type: ignore[assignment]
    classifier: Annotated[FraudClassifier | None, Depends(get_fraud_classifier)] = None,
    detector: Annotated[AnomalyDetector | None, Depends(get_anomaly_detector)] = None,
    audit: Annotated[InMemoryAuditStore, Depends(get_audit_store)] = ...,  # type: ignore[assignment]
    user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> ClaimRiskScore:
    claim = await queries.get_detail(claim_id)
    if claim is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Siniestro no encontrado"
        )
    ctx = RuleContext.from_claim(claim)
    risk = score_claim(claim, ctx=ctx)
    enriched = await enrich_claim_score(claim, classifier=classifier, detector=detector)
    emit_audit_event(
        audit,
        user=user,
        action=AuditAction.apertura,
        title=f"Recalculó el score de {claim_id}",
        detail=f"Nuevo score {risk.score}/100 · nivel {risk.tier.value}",
        target=claim_id,
    )
    return risk.model_copy(
        update={
            "ml_probability": enriched.ml_probability,
            "ml_factors": enriched.ml_factors,
            "anomaly_score": enriched.anomaly_score,
            "nearest_normal_claim_id": enriched.nearest_normal_claim_id,
        }
    )


@router.patch("/{claim_id}", response_model=ClaimDetail)
async def patch_claim_route(
    claim_id: str,
    patch: ClaimPatch,
    queries: Annotated[ClaimQueries, Depends(get_claim_queries_dep)] = ...,  # type: ignore[assignment]
    classifier: Annotated[FraudClassifier | None, Depends(get_fraud_classifier)] = None,
    detector: Annotated[AnomalyDetector | None, Depends(get_anomaly_detector)] = None,
    audit: Annotated[InMemoryAuditStore, Depends(get_audit_store)] = ...,  # type: ignore[assignment]
    user: Annotated[User, Depends(require_role(Role.antifraude))] = ...,  # type: ignore[assignment]
) -> ClaimDetail:
    """Debug fire-test endpoint — gated by DEBUG_ENABLED (§10).

    Patches mutable fields then rescores.  Only available when DEBUG_ENABLED=true
    and the caller holds the antifraude role.
    """
    if not settings.DEBUG_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    claim = await queries.get_detail(claim_id)
    if claim is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Siniestro no encontrado"
        )

    updates: dict[str, object] = {}
    if patch.fecha_ocurrencia is not None:
        updates["fecha_ocurrencia"] = patch.fecha_ocurrencia
    if patch.fecha_reporte is not None:
        updates["fecha_reporte"] = patch.fecha_reporte
    if patch.monto_reclamado is not None:
        updates["monto_reclamado"] = patch.monto_reclamado
    if patch.documentos_completos is not None and patch.documentos_completos:
        # Reflect on existing documentos list — clear falta flags when set to True
        new_docs = [d.model_copy(update={"falta": False}) for d in claim.documentos]
        updates["documentos"] = new_docs

    patched = claim.model_copy(update=updates)

    ctx = RuleContext.from_claim(patched)
    risk = score_claim(patched, ctx=ctx)
    alertas = [
        ClaimAlert(
            code=a.code,
            puntos=a.points,
            severidad=_tier_to_severidad(a.tier_hint),
            detalle=(m.short_description if (m := get_meta(a.code)) else a.code),
        )
        for a in risk.activations
    ]

    rescored = patched.model_copy(
        update={
            "score": risk.score,
            "nivel": risk.tier,
            "alertas": alertas,
            "similar": risk.similar,
        }
    )
    fields = ", ".join(sorted(updates.keys())) or "(sin cambios)"
    emit_audit_event(
        audit,
        user=user,
        action=AuditAction.cambio_regla,
        title=f"Editó manualmente {claim_id} (fire-test)",
        detail=f"Campos modificados: {fields} · nuevo score {risk.score}/100",
        target=claim_id,
    )
    return await enrich_claim_score(rescored, classifier=classifier, detector=detector)
