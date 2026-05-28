"""Reviews API — THIN router: parse → use case → return.

Endpoints (§10 spec):
    POST /claims/{id}/escalate        analista   pendiente → escalado
    POST /claims/{id}/close           analista   pendiente → revisado_sin_escalar
    POST /claims/{id}/take            antifraude escalado  → en_revision
    POST /claims/{id}/dictamen        antifraude escalado|en_revision → dictaminado|pendiente
    GET  /antifraude/inbox            antifraude paginated active queue
    GET  /antifraude/historico        antifraude paginated own dictámenes
    GET  /claims/historico            analista   paginated own closed cases

All state-changing endpoints return the updated ClaimDetail (review field attached).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.api.deps import (
    get_audit_store,
    get_claim_queries_dep,
    get_current_user,
    get_reviews_store,
    require_role,
)
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.domain.reviews.state_machine import ConflictError, GuardError, ReviewTransitionError
from app.infrastructure.audit import AuditStore
from app.infrastructure.reviews.ports import ReviewsStore
from app.schemas.audit import AuditAction, AuditActor
from app.schemas.claim import ClaimDetail, ClaimReview, ClaimSummary, ReviewStatus
from app.schemas.page import Page
from app.schemas.reviews import CloseRequest, DictamenRequest, EscalateRequest, InboxRow
from app.use_cases.emit_audit_event import emit_audit_event
from app.use_cases.get_claim_detail import get_claim_detail
from app.use_cases.reviews.close_claim import close_claim
from app.use_cases.reviews.emit_dictamen import emit_dictamen
from app.use_cases.reviews.escalate_claim import escalate_claim
from app.use_cases.reviews.list_antifraude_inbox import list_antifraude_inbox
from app.use_cases.reviews.list_historico import list_analista_historico, list_antifraude_historico
from app.use_cases.reviews.take_claim import take_claim

# Two routers: one under /claims, one under /antifraude
claims_reviews_router = APIRouter(prefix="/claims", tags=["reviews"])
antifraude_router = APIRouter(prefix="/antifraude", tags=["antifraude"])


def _claim_or_404(claim: ClaimDetail | None) -> ClaimDetail:
    if claim is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Siniestro no encontrado"
        )
    return claim


def _attach_review(detail: ClaimDetail, review: ClaimReview) -> ClaimDetail:
    """Return a new ClaimDetail with the live review state attached."""
    return detail.model_copy(update={"review": review})


# ---------------------------------------------------------------------------
# Analista actions
# ---------------------------------------------------------------------------


@claims_reviews_router.post(
    "/{claim_id}/escalate",
    response_model=ClaimDetail,
    dependencies=[Depends(require_role(Role.analista))],
)
async def escalate_claim_route(
    claim_id: str,
    body: EscalateRequest,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[ReviewsStore, Depends(get_reviews_store)],
    audit: Annotated[AuditStore, Depends(get_audit_store)],
    queries: Annotated[ClaimQueries, Depends(get_claim_queries_dep)],
) -> ClaimDetail:
    detail = _claim_or_404(await get_claim_detail(queries, claim_id))
    try:
        review = await escalate_claim(store, claim_id, user=user, note=body.note)
    except ReviewTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "invalid_transition", "message": str(exc)},
        ) from exc
    await emit_audit_event(
        audit,
        user=user,
        action=AuditAction.escalamiento,
        title=f"Escaló {claim_id} a Unidad Antifraude",
        detail=(
            f"Score {detail.score}/100 · nivel {detail.nivel.value}"
            + (f" · nota: {body.note}" if body.note else "")
        ),
        target=claim_id,
    )
    return _attach_review(detail, review)


@claims_reviews_router.post(
    "/{claim_id}/close",
    response_model=ClaimDetail,
    dependencies=[Depends(require_role(Role.analista))],
)
async def close_claim_route(
    claim_id: str,
    body: CloseRequest,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[ReviewsStore, Depends(get_reviews_store)],
    audit: Annotated[AuditStore, Depends(get_audit_store)],
    queries: Annotated[ClaimQueries, Depends(get_claim_queries_dep)],
) -> ClaimDetail:
    detail = _claim_or_404(await get_claim_detail(queries, claim_id))
    try:
        review = await close_claim(store, claim_id, user=user, note=body.note)
    except ReviewTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "invalid_transition", "message": str(exc)},
        ) from exc
    except GuardError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "guard_failed", "message": str(exc)},
        ) from exc
    await emit_audit_event(
        audit,
        user=user,
        action=AuditAction.cierre,
        title=f"Cerró {claim_id} sin escalación",
        detail=(
            f"Score {detail.score}/100"
            + (f" · nota: {body.note}" if body.note else "")
        ),
        target=claim_id,
    )
    return _attach_review(detail, review)


@claims_reviews_router.get(
    "/historico",
    response_model=Page[ClaimSummary],
    dependencies=[Depends(require_role(Role.analista))],
)
async def claims_historico_route(
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[ReviewsStore, Depends(get_reviews_store)],
    queries: Annotated[ClaimQueries, Depends(get_claim_queries_dep)],
    page: int = 0,
    page_size: int = 25,
) -> Page[ClaimSummary]:
    """Analista's paginated history of closed cases."""
    return await list_analista_historico(
        store, queries, user_id=str(user.id), page=page, page_size=page_size
    )


# ---------------------------------------------------------------------------
# Antifraude actions
# ---------------------------------------------------------------------------


@claims_reviews_router.post(
    "/{claim_id}/take",
    response_model=ClaimDetail,
    dependencies=[Depends(require_role(Role.antifraude))],
)
async def take_claim_route(
    claim_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[ReviewsStore, Depends(get_reviews_store)],
    audit: Annotated[AuditStore, Depends(get_audit_store)],
    queries: Annotated[ClaimQueries, Depends(get_claim_queries_dep)],
) -> ClaimDetail:
    detail = _claim_or_404(await get_claim_detail(queries, claim_id))
    try:
        review, idempotent = await take_claim(store, claim_id, user=user)
    except ReviewTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "invalid_transition", "message": str(exc)},
        ) from exc
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "already_taken", "message": str(exc)},
        ) from exc
    if not idempotent:
        await emit_audit_event(
            audit,
            user=user,
            action=AuditAction.apertura,
            title=f"Tomó el caso {claim_id} para revisión antifraude",
            detail=f"Score {detail.score}/100 · nivel {detail.nivel.value}",
            target=claim_id,
        )
    return _attach_review(detail, review)


@claims_reviews_router.post(
    "/{claim_id}/dictamen",
    response_model=ClaimDetail,
    dependencies=[Depends(require_role(Role.antifraude))],
)
async def dictamen_route(
    claim_id: str,
    body: DictamenRequest,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[ReviewsStore, Depends(get_reviews_store)],
    audit: Annotated[AuditStore, Depends(get_audit_store)],
    queries: Annotated[ClaimQueries, Depends(get_claim_queries_dep)],
) -> ClaimDetail:
    detail = _claim_or_404(await get_claim_detail(queries, claim_id))
    try:
        review = await emit_dictamen(
            store,
            claim_id,
            user=user,
            outcome=body.outcome,
            justificacion=body.justificacion,
        )
    except ReviewTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "invalid_transition", "message": str(exc)},
        ) from exc
    except GuardError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "guard_failed", "message": str(exc)},
        ) from exc
    await emit_audit_event(
        audit,
        user=user,
        action=AuditAction.dictamen,
        title=f"Dictaminó {claim_id} · {body.outcome.value}",
        detail=body.justificacion,
        target=claim_id,
        actor=AuditActor.analista,
    )
    return _attach_review(detail, review)


# ---------------------------------------------------------------------------
# Antifraude read endpoints
# ---------------------------------------------------------------------------


@antifraude_router.get(
    "/inbox",
    response_model=Page[InboxRow],
    dependencies=[Depends(require_role(Role.antifraude))],
)
async def antifraude_inbox_route(
    store: Annotated[ReviewsStore, Depends(get_reviews_store)],
    queries: Annotated[ClaimQueries, Depends(get_claim_queries_dep)],
    status_filter: ReviewStatus | None = None,
    page: int = 0,
    page_size: int = 25,
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> Page[InboxRow]:
    """Paginated active queue for antifraude (escalado + en_revision by default)."""
    return await list_antifraude_inbox(
        store,
        queries,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )


@antifraude_router.get(
    "/historico",
    response_model=Page[ClaimSummary],
    dependencies=[Depends(require_role(Role.antifraude))],
)
async def antifraude_historico_route(
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[ReviewsStore, Depends(get_reviews_store)],
    queries: Annotated[ClaimQueries, Depends(get_claim_queries_dep)],
    page: int = 0,
    page_size: int = 25,
) -> Page[ClaimSummary]:
    """Antifraude's paginated history of own dictámenes."""
    return await list_antifraude_historico(
        store, queries, user_id=str(user.id), page=page, page_size=page_size
    )
