"""Rename a conversation owned by the current user."""

from __future__ import annotations

from uuid import UUID

from app.core.errors import NotFound
from app.repositories.conversations_repo import ConversationsRepo
from app.schemas.conversation import ConversationDetail


class RenameConversation:
    def __init__(self, conversations: ConversationsRepo) -> None:
        self._conversations = conversations

    async def execute(
        self, conversation_id: UUID, user_id: UUID, title: str
    ) -> ConversationDetail:
        updated = await self._conversations.update_title(conversation_id, user_id, title)
        if updated is None:
            raise NotFound(f"Conversation {conversation_id} not found")
        return ConversationDetail(
            id=updated.id,
            title=updated.title,
            context_claim_id=updated.context_claim_id,
            created_at=updated.created_at,
            updated_at=updated.updated_at,
            messages=[],
        )
