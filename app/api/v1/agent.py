"""Agent SSE endpoint — streams `ChatStreamEvent` from the LangGraph claims agent.

The legacy wire shape (`message` / `history` / `context_claim_id`) used by the
Angular client (`agent.store.ts`) is preserved here and adapted on entry to the
use-case shape (`query` / `context.focus_claim_id` / `conversation_id`) expected
by `AskAgent`. `history` is intentionally dropped: multi-turn memory is owned by
the LangGraph checkpointer keyed by `conversation_id`.

This route holds zero business logic and never imports an LLM SDK directly —
it delegates to `AskAgent` (ReAct loop + 5 tools wired in `deps.py`), which goes
through the `LLMProvider` port.
"""

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_ask_agent, get_current_user
from app.domain.auth.user import User
from app.schemas.agent import AgentAskContext
from app.schemas.agent import AgentAskRequest as AskAgentRequest
from app.schemas.chat.request import AgentAskRequest as WireAgentAskRequest
from app.use_cases.ask_agent import AskAgent

router = APIRouter(prefix="/agent", tags=["agent"])


def _to_use_case_request(wire: WireAgentAskRequest) -> AskAgentRequest:
    context = (
        AgentAskContext(focus_claim_id=wire.context_claim_id)
        if wire.context_claim_id
        else None
    )
    return AskAgentRequest(
        query=wire.message,
        context=context,
        conversation_id=wire.conversation_id,
    )


async def _stream_events(
    ask_agent: AskAgent, req: AskAgentRequest, user: User
) -> AsyncIterator[str]:
    async for event in ask_agent.run(req, user=user):
        payload = event.model_dump(mode="json")
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/ask")
async def agent_ask(
    body: WireAgentAskRequest,
    ask_agent: Annotated[AskAgent, Depends(get_ask_agent)],
    user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    req = _to_use_case_request(body)
    return StreamingResponse(
        _stream_events(ask_agent, req, user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
