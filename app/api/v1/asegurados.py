"""Asegurados API — THIN router.

Routes:
    GET /asegurados → list[AseguradoOut]   (any authenticated user)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.domain.auth.user import User
from app.infrastructure.db.engine import get_session
from app.schemas.asegurados import AseguradoOut
from app.use_cases.list_asegurados import list_asegurados

router = APIRouter(prefix="/asegurados", tags=["asegurados"])


@router.get("", response_model=list[AseguradoOut])
async def list_asegurados_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> list[AseguradoOut]:
    return await list_asegurados(session)
