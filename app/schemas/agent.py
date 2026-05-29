"""Wire shapes for the LangGraph claims agent — surface to OpenAPI + the frontend.

`AgentAskRequest` is the body of `POST /agent/ask`. The streaming response is
JSON-per-SSE-event using the existing `ChatStreamEvent` discriminated union
(`app/schemas/chat/stream/`). Reusing that union — instead of inventing a new
shape — is the cross-stack contract rule from root CLAUDE.md §5.
"""

from pydantic import BaseModel, Field


class DocumentContext(BaseModel):
    """A document the analyst is editing in the canvas, attached to a chat turn.

    Rides in its own field (NOT in `query`/`message`) so the full markdown can be
    large without hitting the 4000-char chat cap. When present, the agent improves
    THIS document via `crear_documento` instead of inventing one from scratch.
    """

    titulo: str = Field(..., min_length=1, max_length=500)
    # Large by design — the document content is not subject to the chat cap.
    contenido_markdown: str = Field(..., min_length=1, max_length=40000)


class AgentAskContext(BaseModel):
    """Optional client-supplied context. Lets the UI pin the agent to a focused entity."""

    focus_claim_id: str | None = None
    focus_provider_id: str | None = None
    focus_asegurado_id: str | None = None
    document_context: DocumentContext | None = None


class AgentAskRequest(BaseModel):
    """Body of `POST /api/v1/agent/ask`.

    `query` is the user's natural-language question (Spanish). `context` lets the
    UI hint the agent ("the user is currently looking at SIN-0042"). The agent
    can use that for `explain_case` even when the user didn't paste the ID.
    `conversation_id` is the multi-turn chat thread — same value across follow-up
    questions binds them to one memory window. Omit to start fresh.
    """

    query: str = Field(..., min_length=1, max_length=4000)
    context: AgentAskContext | None = None
    conversation_id: str | None = Field(
        default=None,
        description="UUID-ish opaque id that links a follow-up to its prior turns",
    )
