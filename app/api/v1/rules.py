"""Rules catalog API — THIN router.

Routes:
    GET /rules/catalog   → list[RuleMetaOut]   (any authenticated user)
    GET /rules/{code}    → RuleMetaOut          (any authenticated user, 404 on unknown)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.domain.auth.user import User
from app.domain.rules.catalog import all_meta, get_meta
from app.schemas.rules import RuleMetaOut

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
