"""Delete a conversation (cascades to messages)."""

from __future__ import annotations

from uuid import UUID

from app.core.errors import NotFound
from app.repositories.conversations_repo import ConversationsRepo


class DeleteConversation:
    def __init__(self, conversations: ConversationsRepo) -> None:
        self._conversations = conversations

    async def execute(self, conversation_id: UUID, user_id: UUID) -> None:
        deleted = await self._conversations.delete(conversation_id, user_id)
        if not deleted:
            raise NotFound(f"Conversation {conversation_id} not found")
