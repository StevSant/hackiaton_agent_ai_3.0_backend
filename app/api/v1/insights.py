"""Insights API — THIN router.

Routes:
    GET /insights → InsightsBundleOut   (any authenticated user)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_db_session
from app.domain.auth.user import User
from app.schemas.insights import InsightsBundleOut
from app.use_cases.compute_insights import compute_insights

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("", response_model=InsightsBundleOut)
async def get_insights_route(
    session: Annotated[AsyncSession | None, Depends(get_optional_db_session)] = None,
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> InsightsBundleOut:
    return await compute_insights(session)
