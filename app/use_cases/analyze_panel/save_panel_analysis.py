"""Persist a completed panel debate onto its claim_scores row (advisory only)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.claim_score import ClaimScore
from app.schemas.panel import PanelAnalysis


async def save_panel_analysis(
    session: AsyncSession, claim_id: str, analysis: PanelAnalysis
) -> bool:
    """Cache the panel result on the claim's score row. No rescore — advisory only.

    Returns False (no-op) when the claim has no score row yet.
    """
    score_row = (
        await session.execute(
            select(ClaimScore).where(ClaimScore.claim_id == claim_id)
        )
    ).scalars().first()
    if score_row is None:
        return False

    score_row.panel_analysis = analysis.model_dump(mode="json")
    await session.commit()
    return True
