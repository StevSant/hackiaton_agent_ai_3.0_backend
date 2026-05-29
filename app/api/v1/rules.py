"""Rules catalog API — THIN router.

Routes:
    GET   /rules/catalog        → list[RuleMetaOut]   (any authenticated user)
    GET   /rules/config         → list[RuleConfigOut] (any authenticated user)
    GET   /rules/changes        → list[RuleChangeOut] (any authenticated user)
    POST  /rules/rescore        → 202 RescoreStatusOut (antifraude — start background job)
    GET   /rules/rescore/status → RescoreStatusOut    (poll the job's progress)
    GET   /rules/{code}         → RuleMetaOut         (any authenticated user, 404 on unknown)
    PATCH /rules/{code}         → RuleConfigOut        (antifraude — pause / retune, NO rescore)

Fixed paths (/catalog, /config, /changes, /rescore) MUST be registered before
/{code} — FastAPI matches routes in registration order, and /{code} would
otherwise shadow them.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cache_control import cache_for
from app.api.deps import (
    get_current_user,
    get_narrative_similarity,
    get_optional_db_session,
    get_rule_changes_store,
    get_rule_overrides_store,
    get_vehicle_decoder,
    require_role,
)
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.domain.rules.catalog import all_meta, get_meta
from app.domain.similarity import NarrativeSimilarity
from app.domain.vehicle_identity import VehicleDecoder
from app.infrastructure.db.engine import get_session, get_session_factory
from app.infrastructure.rescore_jobs import (
    RescoreJobSnapshot,
    get_rescore_job_manager,
)
from app.infrastructure.rule_changes import RuleChangesStore
from app.infrastructure.rule_overrides import RuleOverridesStore
from app.schemas.rescore_status import RescoreStatusOut
from app.schemas.rule_changes import RuleChangeOut
from app.schemas.rules import RuleMetaOut
from app.schemas.rules_config import RuleConfigOut, RuleConfigPatch
from app.use_cases.list_rule_changes import list_rule_changes
from app.use_cases.list_rules_config import list_rules_config
from app.use_cases.rescore_all import rescore_all
from app.use_cases.update_rule_config import update_rule_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rules", tags=["rules"])


def _to_out(meta: object) -> RuleMetaOut:
    """Convert domain RuleMeta dataclass to the wire schema."""
    from app.domain.rules.ports import RuleMeta

    assert isinstance(meta, RuleMeta)
    return RuleMetaOut(
        code=meta.code,
        name=meta.name,
        tier_hint=meta.tier_hint,
        short_description=meta.short_description,
        what_triggers=meta.what_triggers,
        max_points=meta.max_points,
    )


@router.get(
    "/catalog",
    response_model=list[RuleMetaOut],
    dependencies=[Depends(cache_for(300))],
)
async def list_catalog(
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> list[RuleMetaOut]:
    return [_to_out(m) for m in all_meta()]


# NOTE: deliberately NOT cached — this payload is mutable (PATCH /rules/{code}
# flips enabled/thresholds) and the dashboard refetches right after a PATCH; a
# browser-cached stale copy would visually revert the toggle.
@router.get(
    "/config",
    response_model=list[RuleConfigOut],
)
async def list_rules_config_route(
    session: Annotated[AsyncSession | None, Depends(get_optional_db_session)] = None,
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> list[RuleConfigOut]:
    return await list_rules_config(session)


@router.get("/changes", response_model=list[RuleChangeOut])
async def list_rule_changes_route(
    store: Annotated[RuleChangesStore, Depends(get_rule_changes_store)],
    limit: int | None = None,
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> list[RuleChangeOut]:
    return await list_rule_changes(store, limit=limit)


def _to_status(snapshot: RescoreJobSnapshot) -> RescoreStatusOut:
    return RescoreStatusOut(
        status=snapshot.status,
        processed=snapshot.processed,
        total=snapshot.total,
        changed=snapshot.changed,
        error=snapshot.error,
    )


@router.post("/rescore", response_model=RescoreStatusOut, status_code=status.HTTP_202_ACCEPTED)
async def start_rescore(
    similarity: Annotated[
        NarrativeSimilarity | None, Depends(get_narrative_similarity)
    ] = None,
    decoder: Annotated[VehicleDecoder, Depends(get_vehicle_decoder)] = ...,  # type: ignore[assignment]
    _user: Annotated[User, Depends(require_role(Role.antifraude))] = ...,  # type: ignore[assignment]
) -> RescoreStatusOut:
    """Kick off a background rescore of every claim and return immediately.

    Antifraude-only. This is the explicit counterpart of PATCH /rules/{code}:
    edits accumulate cheaply, then one rescore applies them all at once. The job
    runs as a detached task with its OWN session (no request stays open — a
    long-lived request is what froze the app under uvicorn's reload drain).
    Idempotent: if a job is already running, returns its current snapshot.
    """
    manager = get_rescore_job_manager()
    factory = get_session_factory()

    async def runner(
        on_progress: Callable[[int, int, int], Awaitable[None]],
    ) -> dict[str, int]:
        async with factory() as session:
            return await rescore_all(
                session, similarity=similarity, decoder=decoder, on_progress=on_progress
            )

    manager.start(runner)
    return _to_status(manager.snapshot())


@router.get("/rescore/status", response_model=RescoreStatusOut)
async def rescore_status(
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> RescoreStatusOut:
    """Snapshot of the background rescore job — polled by the dashboard."""
    return _to_status(get_rescore_job_manager().snapshot())


@router.get(
    "/{code}",
    response_model=RuleMetaOut,
    dependencies=[Depends(cache_for(300))],
)
async def get_rule(
    code: str,
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> RuleMetaOut:
    meta = get_meta(code)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Regla '{code}' no encontrada",
        )
    return _to_out(meta)


@router.patch("/{code}", response_model=RuleConfigOut)
async def patch_rule(
    code: str,
    patch: RuleConfigPatch,
    session: Annotated[AsyncSession, Depends(get_session)] = ...,  # type: ignore[assignment]
    overrides_store: Annotated[
        RuleOverridesStore, Depends(get_rule_overrides_store)
    ] = ...,  # type: ignore[assignment]
    changes_store: Annotated[
        RuleChangesStore, Depends(get_rule_changes_store)
    ] = ...,  # type: ignore[assignment]
    user: Annotated[User, Depends(require_role(Role.antifraude))] = ...,  # type: ignore[assignment]
) -> RuleConfigOut:
    """Pause/reactivate a rule or retune its thresholds — WITHOUT rescoring.

    Antifraude-only. Persists the edit, re-hydrates the engine and logs the
    change; edits accumulate cheaply and the analyst triggers ONE explicit
    ``POST /rules/rescore`` when done batching changes.
    """
    return await update_rule_config(
        session,
        code=code,
        patch=patch,
        overrides_store=overrides_store,
        changes_store=changes_store,
        actor=user.full_name or user.email,
    )
