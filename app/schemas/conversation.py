"""Wire schemas for conversation history endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.chat.stream.chart_data import ChartData


class MessageOut(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    sequence: int
    created_at: datetime
    chart_payload: ChartData | None = None
    # Transparency payload for assistant messages — steps, tool_calls, citations.
    # Null for user messages and legacy assistant messages without recorded metadata.
    transparency_metadata: dict[str, Any] | None = None


class ConversationSummary(BaseModel):
    id: UUID
    title: str | None
    context_claim_id: str | None
    snippet: str | None
    created_at: datetime
    updated_at: datetime


class ConversationDetail(BaseModel):
    id: UUID
    title: str | None
    context_claim_id: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut]


class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class ConversationDeleted(BaseModel):
    ok: bool
