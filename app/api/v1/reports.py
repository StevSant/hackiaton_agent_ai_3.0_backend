"""Reports API — THIN router.

Routes:
    GET /reports/savings-analysis → SavingsAnalysisOut   (any authenticated user)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.domain.auth.user import User
from app.infrastructure.db.engine import get_session
from app.schemas.reports import SavingsAnalysisOut
from app.use_cases.compute_savings_analysis import compute_savings_analysis

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/savings-analysis", response_model=SavingsAnalysisOut)
async def get_savings_analysis_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> SavingsAnalysisOut:
    return await compute_savings_analysis(session)
