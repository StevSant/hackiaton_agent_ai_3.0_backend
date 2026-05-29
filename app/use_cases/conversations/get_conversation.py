"""Fetch a conversation with all messages, enforcing ownership."""

from __future__ import annotations

from uuid import UUID

from app.core.errors import NotFound
from app.repositories.conversations_repo import ConversationsRepo
from app.schemas.conversation import ConversationDetail, MessageOut
from app.use_cases.visual_payload_replay import legacy_chart_to_visuals


class GetConversation:
    def __init__(self, conversations: ConversationsRepo) -> None:
        self._conversations = conversations

    async def execute(self, conversation_id: UUID, user_id: UUID) -> ConversationDetail:
        row = await self._conversations.get(conversation_id, user_id)
        if row is None:
            raise NotFound(f"Conversation {conversation_id} not found")
        return ConversationDetail(
            id=row.id,
            title=row.title,
            context_claim_id=row.context_claim_id,
            context_provider_id=getattr(row, "context_provider_id", None),
            context_asegurado_id=getattr(row, "context_asegurado_id", None),
            created_at=row.created_at,
            updated_at=row.updated_at,
            messages=[
                MessageOut(
                    id=m.id,
                    role=m.role,  # type: ignore[arg-type]
                    content=m.content,
                    sequence=m.sequence,
                    created_at=m.created_at,
                    chart_payload=m.chart_payload,  # type: ignore[arg-type]
                    # Prefer the new visual_payload when set; fall back to
                    # mapping the legacy chart_payload into the visual shape.
                    visual_payload=(
                        m.visual_payload  # type: ignore[arg-type]
                        if getattr(m, "visual_payload", None) is not None
                        else legacy_chart_to_visuals(m.chart_payload)  # type: ignore[arg-type]
                    ),
                    transparency_metadata=m.transparency_metadata,
                )
                for m in row.messages
            ],
        )
