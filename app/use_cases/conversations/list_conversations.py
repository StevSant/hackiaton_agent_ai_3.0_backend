"""List conversations for the current user, optionally filtered by a search query."""

from __future__ import annotations

from uuid import UUID

from app.infrastructure.db.models.message import Message
from app.repositories.conversations_repo import ConversationsRepo
from app.repositories.messages_repo import MessagesRepo
from app.schemas.conversation import ConversationSummary


def _latest_user_snippet(messages: list[Message]) -> str | None:
    for msg in reversed(messages):
        if msg.role == "user" and msg.content:
            return msg.content[:140]
    return None


class ListConversations:
    def __init__(
        self,
        conversations: ConversationsRepo,
        messages: MessagesRepo,
    ) -> None:
        self._conversations = conversations
        self._messages = messages

    async def execute(
        self,
        user_id: UUID,
        query: str | None = None,
        context_claim_id: str | None = None,
        context_provider_id: str | None = None,
        context_asegurado_id: str | None = None,
    ) -> list[ConversationSummary]:
        rows = await self._conversations.list_for_user(
            user_id,
            query=query,
            context_claim_id=context_claim_id,
            context_provider_id=context_provider_id,
            context_asegurado_id=context_asegurado_id,
        )
        summaries: list[ConversationSummary] = []
        for row in rows:
            msgs = await self._messages.list_for_conversation(row.id)
            summaries.append(
                ConversationSummary(
                    id=row.id,
                    title=row.title,
                    context_claim_id=row.context_claim_id,
                    context_provider_id=getattr(row, "context_provider_id", None),
                    context_asegurado_id=getattr(row, "context_asegurado_id", None),
                    snippet=_latest_user_snippet(msgs),
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
            )
        return summaries
