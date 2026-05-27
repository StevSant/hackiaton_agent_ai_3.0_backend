"""Network / providers API — THIN router.

Routes:
    GET /network/providers → list[ProviderOut]   (any authenticated user)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.domain.auth.user import User
from app.infrastructure.db.engine import get_session
from app.schemas.network import ProviderOut
from app.use_cases.list_providers import list_providers

router = APIRouter(prefix="/network", tags=["network"])


@router.get("/providers", response_model=list[ProviderOut])
async def list_providers_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> list[ProviderOut]:
    return await list_providers(session)
