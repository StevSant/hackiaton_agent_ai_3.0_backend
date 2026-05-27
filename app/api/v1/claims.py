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

from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.api.deps import get_claim_queries, get_current_user, require_role
from app.core.config import settings
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.domain.rules.catalog import get_meta
from app.domain.rules.context import RuleContext
from app.schemas.claim import ClaimAlert, ClaimDetail, ClaimPatch, ClaimSummary, ReviewStatus
from app.schemas.page import Page
from app.schemas.risk import ClaimRiskScore, Tier
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
    page_size: int = 25,
    queries: Annotated[ClaimQueries, Depends(get_claim_queries)] = ...,  # type: ignore[assignment]
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
    queries: Annotated[ClaimQueries, Depends(get_claim_queries)] = ...,  # type: ignore[assignment]
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> ClaimDetail:
    detail = await get_claim_detail(queries, claim_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Siniestro no encontrado"
        )
    return detail


@router.post("/{claim_id}/rescore", response_model=ClaimRiskScore)
async def rescore_claim_route(
    claim_id: str,
    queries: Annotated[ClaimQueries, Depends(get_claim_queries)] = ...,  # type: ignore[assignment]
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> ClaimRiskScore:
    claim = await queries.get_detail(claim_id)
    if claim is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Siniestro no encontrado"
        )
    ctx = RuleContext.from_claim(claim)
    return score_claim(claim, ctx=ctx)


@router.patch("/{claim_id}", response_model=ClaimDetail)
async def patch_claim_route(
    claim_id: str,
    patch: ClaimPatch,
    queries: Annotated[ClaimQueries, Depends(get_claim_queries)] = ...,  # type: ignore[assignment]
    _user: Annotated[User, Depends(require_role(Role.antifraude))] = ...,  # type: ignore[assignment]
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
    if patch.documentos_completos is not None:
        # Reflect on existing documentos list — clear falta flags when set to True
        if patch.documentos_completos:
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

    return patched.model_copy(
        update={
            "score": risk.score,
            "nivel": risk.tier,
            "alertas": alertas,
            "ml_factors": risk.ml_factors,
            "similar": risk.similar,
            "anomaly_score": risk.anomaly_score,
        }
    )
