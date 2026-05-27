"""Rules catalog API — THIN router.

Routes:
    GET /rules/catalog   → list[RuleMetaOut]    (any authenticated user)
    GET /rules/config    → list[RuleConfigOut]  (any authenticated user)
    GET /rules/changes   → list[RuleChangeOut]  (any authenticated user)
    GET /rules/{code}    → RuleMetaOut          (any authenticated user, 404 on unknown)

Fixed paths (/catalog, /config, /changes) MUST be registered before /{code} —
FastAPI matches routes in registration order, and /{code} would otherwise shadow them.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_optional_db_session,
    get_rule_changes_store,
)
from app.domain.auth.user import User
from app.domain.rules.catalog import all_meta, get_meta
from app.infrastructure.rule_changes import InMemoryRuleChangesStore
from app.schemas.rule_changes import RuleChangeOut
from app.schemas.rules import RuleMetaOut
from app.schemas.rules_config import RuleConfigOut
from app.use_cases.list_rule_changes import list_rule_changes
from app.use_cases.list_rules_config import list_rules_config

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


@router.get("/catalog", response_model=list[RuleMetaOut])
async def list_catalog(
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> list[RuleMetaOut]:
    return [_to_out(m) for m in all_meta()]


@router.get("/config", response_model=list[RuleConfigOut])
async def list_rules_config_route(
    session: Annotated[AsyncSession | None, Depends(get_optional_db_session)] = None,
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> list[RuleConfigOut]:
    return await list_rules_config(session)


@router.get("/changes", response_model=list[RuleChangeOut])
async def list_rule_changes_route(
    store: Annotated[InMemoryRuleChangesStore, Depends(get_rule_changes_store)],
    limit: int | None = None,
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> list[RuleChangeOut]:
    return await list_rule_changes(store, limit=limit)


@router.get("/{code}", response_model=RuleMetaOut)
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
