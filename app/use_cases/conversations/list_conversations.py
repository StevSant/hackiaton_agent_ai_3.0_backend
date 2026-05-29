"""List conversations for the current user, optionally filtered by a search query."""

from __future__ import annotations

from uuid import UUID

from app.repositories.conversations_repo import ConversationsRepo
from app.repositories.messages_repo import MessagesRepo
from app.schemas.conversation import ConversationSummary


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
        # One query for ALL snippets instead of one query per conversation (N+1).
        snippets = await self._messages.latest_user_snippets([row.id for row in rows])
        return [
            ConversationSummary(
                id=row.id,
                title=row.title,
                context_claim_id=row.context_claim_id,
                context_provider_id=getattr(row, "context_provider_id", None),
                context_asegurado_id=getattr(row, "context_asegurado_id", None),
                snippet=snippets.get(row.id),
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
