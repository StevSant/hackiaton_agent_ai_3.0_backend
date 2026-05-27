"""Insights API — THIN router.

Routes:
    GET /insights → InsightsBundleOut   (any authenticated user)

The endpoint requires a live DB session via `app.infrastructure.db.engine.get_session`
(the same one `network.py` and `conversations.py` use). When the DB is unreachable
the session factory raises and FastAPI returns 503 — we never fabricate insights.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.domain.auth.user import User
from app.infrastructure.db.engine import get_session
from app.schemas.insights import InsightsBundleOut
from app.use_cases.compute_insights import compute_insights

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("", response_model=InsightsBundleOut)
async def get_insights_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> InsightsBundleOut:
    return await compute_insights(session)
