"""Claims API — THIN router: parse → use case → return.

Routes:
    GET  /claims                        → Page[ClaimSummary]   (any authenticated user)
    GET  /claims/{id}                   → ClaimDetail          (any authenticated user)
    POST /claims/{id}/rescore           → ClaimDetail          (any authenticated user)
    GET  /claims/{id}/report.docx       → bytes (docx)         (any authenticated user)
    POST /claims/{id}/resumen/improve   → {resumen: str}       (any authenticated user)
    PATCH /claims/{id}/resumen          → ClaimDetail          (any authenticated user)
    PATCH /claims/{id}                  → ClaimDetail          (DEBUG_ENABLED + antifraude only)
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.api.deps import (
    _get_optional_session,
    get_anomaly_detector,
    get_audit_store,
    get_claim_queries_dep,
    get_current_user,
    get_fraud_classifier,
    get_llm,
    get_narrative_similarity,
    get_prompt_loader,
    get_reviews_store,
    get_vehicle_decoder,
    require_role,
)
from app.core.config import settings
from app.domain.anomaly import AnomalyDetector
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.domain.ml import FraudClassifier
from app.domain.rules.catalog import get_meta
from app.domain.rules.context import RuleContext
from app.domain.similarity import NarrativeSimilarity
from app.domain.vehicle_identity import VehicleDecoder
from app.infrastructure.audit import AuditStore
from app.infrastructure.db.engine import get_session
from app.infrastructure.llm import LLMProvider, PromptLoader
from app.infrastructure.reviews.ports import ReviewsStore
from app.schemas.audit import AuditAction
from app.schemas.claim import (
    ClaimAlert,
    ClaimDetail,
    ClaimPatch,
    ClaimSummary,
    ResumenPatch,
    ReviewStatus,
)
from app.schemas.page import Page
from app.schemas.risk import Tier
from app.use_cases.analyze_claim_narrative_persisted import (
    analyze_claim_narrative_persisted,
)
from app.use_cases.emit_audit_event import emit_audit_event
from app.use_cases.enrich_claim_score import enrich_claim_score
from app.use_cases.generate_claim_report_docx import generate_claim_report_docx
from app.use_cases.get_claim_detail import _tier_to_severidad, get_claim_detail
from app.use_cases.improve_claim_resumen import improve_claim_resumen
from app.use_cases.list_claims import list_claims
from app.use_cases.reanalyze_claim import reanalyze_claim
from app.use_cases.score_claim import score_claim
from app.use_cases.update_claim_resumen import update_claim_resumen


class _ImproveResumenRequest(BaseModel):
    instrucciones: str | None = None


class _ImproveResumenResponse(BaseModel):
    resumen: str


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
    reviews_store: Annotated[ReviewsStore, Depends(get_reviews_store)] = ...,  # type: ignore[assignment]
    classifier: Annotated[FraudClassifier | None, Depends(get_fraud_classifier)] = None,
    detector: Annotated[AnomalyDetector | None, Depends(get_anomaly_detector)] = None,
    similarity: Annotated[
        NarrativeSimilarity | None, Depends(get_narrative_similarity)
    ] = None,
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> ClaimDetail:
    detail = await get_claim_detail(
        queries,
        claim_id,
        reviews_store=reviews_store,
        classifier=classifier,
        detector=detector,
        similarity=similarity,
    )
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Siniestro no encontrado"
        )
    return detail


@router.get("/{claim_id}/report.docx")
async def download_claim_report_docx(
    claim_id: str,
    queries: Annotated[ClaimQueries, Depends(get_claim_queries_dep)] = ...,  # type: ignore[assignment]
    reviews_store: Annotated[ReviewsStore, Depends(get_reviews_store)] = ...,  # type: ignore[assignment]
    classifier: Annotated[FraudClassifier | None, Depends(get_fraud_classifier)] = None,
    detector: Annotated[AnomalyDetector | None, Depends(get_anomaly_detector)] = None,
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> Response:
    """Generate and download a Word report (.docx) for a single claim."""
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
    docx_bytes = await generate_claim_report_docx(detail)
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="reporte-{claim_id}.docx"'
        },
    )


@router.post("/{claim_id}/resumen/improve", response_model=_ImproveResumenResponse)
async def improve_claim_resumen_route(
    claim_id: str,
    body: _ImproveResumenRequest,
    queries: Annotated[ClaimQueries, Depends(get_claim_queries_dep)] = ...,  # type: ignore[assignment]
    reviews_store: Annotated[ReviewsStore, Depends(get_reviews_store)] = ...,  # type: ignore[assignment]
    classifier: Annotated[FraudClassifier | None, Depends(get_fraud_classifier)] = None,
    detector: Annotated[AnomalyDetector | None, Depends(get_anomaly_detector)] = None,
    llm: Annotated[LLMProvider, Depends(get_llm)] = ...,  # type: ignore[assignment]
    _prompts: Annotated[PromptLoader, Depends(get_prompt_loader)] = ...,  # type: ignore[assignment]
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> _ImproveResumenResponse:
    """Use the LLM to improve/regenerate the case summary.

    Does NOT persist — the frontend calls PATCH /resumen to save after review.
    """
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
    resumen = await improve_claim_resumen(
        detail,
        llm=llm,
        llm_model=settings.LLM_DEFAULT_MODEL,
        instrucciones=body.instrucciones,
    )
    return _ImproveResumenResponse(resumen=resumen)


@router.post("/{claim_id}/rescore", response_model=ClaimDetail)
async def rescore_claim_route(
    claim_id: str,
    session: Annotated[AsyncSession, Depends(get_session)] = ...,  # type: ignore[assignment]
    similarity: Annotated[
        NarrativeSimilarity | None, Depends(get_narrative_similarity)
    ] = None,
    classifier: Annotated[FraudClassifier | None, Depends(get_fraud_classifier)] = None,
    detector: Annotated[AnomalyDetector | None, Depends(get_anomaly_detector)] = None,
    decoder: Annotated[VehicleDecoder, Depends(get_vehicle_decoder)] = ...,  # type: ignore[assignment]
    audit: Annotated[AuditStore, Depends(get_audit_store)] = ...,  # type: ignore[assignment]
    user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> ClaimDetail:
    """Re-analyze one claim with the genuine relationship-driven pipeline.

    Rebuilds the RuleContext from DB relationships + stored signal facts, runs
    the rules engine (incl. FS-15 chassis/VIN identity check), persists the fresh
    score, auto-escalates rojos, and enriches ML / anomaly fields when wired.
    """
    detail = await reanalyze_claim(
        session,
        claim_id,
        similarity=similarity,
        classifier=classifier,
        detector=detector,
        decoder=decoder,
    )
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Siniestro no encontrado"
        )
    await emit_audit_event(
        audit,
        user=user,
        action=AuditAction.apertura,
        title=f"Re-analizó el caso {claim_id}",
        detail=f"Nuevo score {detail.score}/100 · nivel {detail.nivel.value}",
        target=claim_id,
    )
    return detail


@router.post("/{claim_id}/narrative-analysis", response_model=ClaimDetail)
async def analyze_claim_narrative_route(
    claim_id: str,
    force: Annotated[bool, Query()] = False,
    queries: Annotated[ClaimQueries, Depends(get_claim_queries_dep)] = ...,  # type: ignore[assignment]
    reviews_store: Annotated[ReviewsStore, Depends(get_reviews_store)] = ...,  # type: ignore[assignment]
    session: Annotated[AsyncSession, Depends(get_session)] = ...,  # type: ignore[assignment]
    llm: Annotated[LLMProvider, Depends(get_llm)] = ...,  # type: ignore[assignment]
    similarity: Annotated[
        NarrativeSimilarity | None, Depends(get_narrative_similarity)
    ] = None,
    classifier: Annotated[FraudClassifier | None, Depends(get_fraud_classifier)] = None,
    detector: Annotated[AnomalyDetector | None, Depends(get_anomaly_detector)] = None,
    decoder: Annotated[VehicleDecoder, Depends(get_vehicle_decoder)] = ...,  # type: ignore[assignment]
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> ClaimDetail:
    """Run (or return cached) NLP analysis of the claim narrative.

    Extracts entities, judges narrative coherence (the genuine source for FS-09),
    and writes a short summary. Cached in ``claim_scores`` — a second call returns
    the cached result without hitting the LLM. When the feature is disabled the
    claim is returned unchanged.
    """
    if not settings.NARRATIVE_ANALYSIS_ENABLED:
        detail = await get_claim_detail(
            queries,
            claim_id,
            reviews_store=reviews_store,
            classifier=classifier,
            detector=detector,
            similarity=similarity,
        )
        if detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Siniestro no encontrado"
            )
        return detail

    detail = await analyze_claim_narrative_persisted(
        session,
        claim_id,
        llm=llm,
        llm_model=settings.LLM_DEFAULT_MODEL,
        force=force,
        similarity=similarity,
        classifier=classifier,
        detector=detector,
        decoder=decoder,
    )
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Siniestro no encontrado"
        )
    # Attach live workflow state so the returned detail matches GET /claims/{id}.
    if reviews_store is not None:
        detail = detail.model_copy(update={"review": await reviews_store.get(claim_id)})
    return detail


@router.patch("/{claim_id}/resumen", response_model=ClaimDetail)
async def patch_claim_resumen_route(
    claim_id: str,
    patch: ResumenPatch,
    queries: Annotated[ClaimQueries, Depends(get_claim_queries_dep)] = ...,  # type: ignore[assignment]
    reviews_store: Annotated[ReviewsStore, Depends(get_reviews_store)] = ...,  # type: ignore[assignment]
    session: Annotated[AsyncSession | None, Depends(_get_optional_session)] = None,
    classifier: Annotated[FraudClassifier | None, Depends(get_fraud_classifier)] = None,
    detector: Annotated[AnomalyDetector | None, Depends(get_anomaly_detector)] = None,
    similarity: Annotated[
        NarrativeSimilarity | None, Depends(get_narrative_similarity)
    ] = None,
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> ClaimDetail:
    """Persist an analyst-edited case summary override on a claim."""
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "db_unavailable", "message": "DB no disponible"},
        )
    ok = await update_claim_resumen(session, claim_id, patch.resumen_editado)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Siniestro no encontrado"
        )
    detail = await get_claim_detail(
        queries,
        claim_id,
        reviews_store=reviews_store,
        classifier=classifier,
        detector=detector,
        similarity=similarity,
    )
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Siniestro no encontrado"
        )
    return detail


@router.patch("/{claim_id}", response_model=ClaimDetail)
async def patch_claim_route(
    claim_id: str,
    patch: ClaimPatch,
    queries: Annotated[ClaimQueries, Depends(get_claim_queries_dep)] = ...,  # type: ignore[assignment]
    classifier: Annotated[FraudClassifier | None, Depends(get_fraud_classifier)] = None,
    detector: Annotated[AnomalyDetector | None, Depends(get_anomaly_detector)] = None,
    audit: Annotated[AuditStore, Depends(get_audit_store)] = ...,  # type: ignore[assignment]
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
    await emit_audit_event(
        audit,
        user=user,
        action=AuditAction.cambio_regla,
        title=f"Editó manualmente {claim_id} (fire-test)",
        detail=f"Campos modificados: {fields} · nuevo score {risk.score}/100",
        target=claim_id,
    )
    return await enrich_claim_score(rescored, classifier=classifier, detector=detector)
