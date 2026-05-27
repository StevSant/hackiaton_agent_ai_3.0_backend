"""Fetch a conversation with all messages, enforcing ownership."""

from __future__ import annotations

from uuid import UUID

from app.core.errors import NotFound
from app.repositories.conversations_repo import ConversationsRepo
from app.schemas.conversation import ConversationDetail, MessageOut


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
            created_at=row.created_at,
            updated_at=row.updated_at,
            messages=[
                MessageOut(
                    id=m.id,
                    role=m.role,  # type: ignore[arg-type]
                    content=m.content,
                    sequence=m.sequence,
                    created_at=m.created_at,
                )
                for m in row.messages
            ],
        )
