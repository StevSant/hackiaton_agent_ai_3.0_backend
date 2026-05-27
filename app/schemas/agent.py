"""Wire shapes for the LangGraph claims agent — surface to OpenAPI + the frontend.

`AgentAskRequest` is the body of `POST /agent/ask`. The streaming response is
JSON-per-SSE-event using the existing `ChatStreamEvent` discriminated union
(`app/schemas/chat/stream/`). Reusing that union — instead of inventing a new
shape — is the cross-stack contract rule from root CLAUDE.md §5.
"""

from pydantic import BaseModel, Field


class AgentAskContext(BaseModel):
    """Optional client-supplied context. Lets the UI pin the agent to a focused claim."""

    focus_claim_id: str | None = None


class AgentAskRequest(BaseModel):
    """Body of `POST /api/v1/agent/ask`.

    `query` is the user's natural-language question (Spanish). `context` lets the
    UI hint the agent ("the user is currently looking at SIN-0042"). The agent
    can use that for `explain_case` even when the user didn't paste the ID.
    `conversation_id` is the multi-turn chat thread — same value across follow-up
    questions binds them to one memory window. Omit to start fresh.
    """

    query: str = Field(..., min_length=1, max_length=2000)
    context: AgentAskContext | None = None
    conversation_id: str | None = Field(
        default=None,
        description="UUID-ish opaque id that links a follow-up to its prior turns",
    )
