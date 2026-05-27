"""POST /api/v1/agent/ask — SSE stream of `ChatStreamEvent`.

Per backend CLAUDE.md §7: each SSE message carries one event as `data: <json>\n\n`.
Always emits a final `done` (or `error` + `done`) event so clients can release the
connection deterministically.
"""

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_ask_agent
from app.schemas.agent import AgentAskRequest
from app.use_cases.ask_agent import AskAgent

router = APIRouter(prefix="/agent", tags=["agent"])


async def _sse(events: AsyncIterator[object]) -> AsyncIterator[str]:
    async for event in events:
        payload = event.model_dump(mode="json") if hasattr(event, "model_dump") else event
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post(
    "/ask",
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "Server-Sent Events stream of ChatStreamEvent",
        }
    },
)
async def ask(
    req: AgentAskRequest,
    use_case: Annotated[AskAgent, Depends(get_ask_agent)],
) -> StreamingResponse:
    return StreamingResponse(
        _sse(use_case.run(req)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
