"""Multi-agent fraud panel SSE endpoint — streams PanelStreamEvent for one claim.

Thin: holds no business logic, delegates to AnalyzePanel (which goes through the
LLMProvider port). Mirrors the SSE framing of app/api/v1/agent.py.
"""

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_analyze_panel, get_current_user
from app.domain.auth.user import User
from app.use_cases.analyze_panel import AnalyzePanel

router = APIRouter(prefix="/claims", tags=["panel"])


async def _stream(panel: AnalyzePanel, claim_id: str) -> AsyncIterator[str]:
    async for event in panel.run(claim_id):
        payload = event.model_dump(mode="json")
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/{claim_id}/panel")
async def claim_panel(
    claim_id: str,
    panel: Annotated[AnalyzePanel, Depends(get_analyze_panel)],
    _user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    return StreamingResponse(
        _stream(panel, claim_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
