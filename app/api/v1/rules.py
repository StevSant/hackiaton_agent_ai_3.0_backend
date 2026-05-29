"""Rules catalog API — THIN router.

Routes:
    GET   /rules/catalog   → list[RuleMetaOut]    (any authenticated user)
    GET   /rules/config    → list[RuleConfigOut]  (any authenticated user)
    GET   /rules/changes   → list[RuleChangeOut]  (any authenticated user)
    GET   /rules/{code}    → RuleMetaOut          (any authenticated user, 404 on unknown)
    PATCH /rules/{code}    → RuleConfigOut         (antifraude — pause / retune)

Fixed paths (/catalog, /config, /changes) MUST be registered before /{code} —
FastAPI matches routes in registration order, and /{code} would otherwise shadow them.
"""

from __future__ import annotations

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
from app.infrastructure.db.engine import get_session
from app.infrastructure.rule_changes import RuleChangesStore
from app.infrastructure.rule_overrides import RuleOverridesStore
from app.schemas.rule_changes import RuleChangeOut
from app.schemas.rules import RuleMetaOut
from app.schemas.rules_config import RuleConfigOut, RuleConfigPatch
from app.use_cases.list_rule_changes import list_rule_changes
from app.use_cases.list_rules_config import list_rules_config
from app.use_cases.update_rule_config import update_rule_config

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


@router.get(
    "/config",
    response_model=list[RuleConfigOut],
    dependencies=[Depends(cache_for(60))],
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
    similarity: Annotated[
        NarrativeSimilarity | None, Depends(get_narrative_similarity)
    ] = None,
    decoder: Annotated[VehicleDecoder, Depends(get_vehicle_decoder)] = ...,  # type: ignore[assignment]
    user: Annotated[User, Depends(require_role(Role.antifraude))] = ...,  # type: ignore[assignment]
) -> RuleConfigOut:
    """Pause/reactivate a rule or retune its thresholds, then rescore all claims.

    Antifraude-only. Persists the edit, re-hydrates the engine, logs the change to
    the history, and runs a full rescore so existing claims reflect the change.
    """
    return await update_rule_config(
        session,
        code=code,
        patch=patch,
        overrides_store=overrides_store,
        changes_store=changes_store,
        actor=user.full_name or user.email,
        similarity=similarity,
        decoder=decoder,
    )
