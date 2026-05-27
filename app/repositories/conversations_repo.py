"""Repository for `conversations` — owns ownership filtering and upsert semantics."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.db.models.conversation import Conversation
from app.infrastructure.db.models.message import Message


class ConversationsRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        query: str | None = None,
        limit: int = 200,
    ) -> list[Conversation]:
        stmt = select(Conversation).where(Conversation.user_id == user_id)
        if query:
            like = f"%{query}%"
            # Match title OR any message content. EXISTS keeps it efficient.
            stmt = stmt.where(
                or_(
                    Conversation.title.ilike(like),
                    select(Message.id)
                    .where(Message.conversation_id == Conversation.id)
                    .where(Message.content.ilike(like))
                    .exists(),
                )
            )
        stmt = stmt.order_by(Conversation.updated_at.desc()).limit(limit)
        result = await self._s.execute(stmt)
        return list(result.scalars().all())

    async def get(self, conversation_id: UUID, user_id: UUID) -> Conversation | None:
        stmt = (
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .where(Conversation.user_id == user_id)
            .options(selectinload(Conversation.messages))
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        conversation_id: UUID,
        user_id: UUID,
        context_claim_id: str | None,
    ) -> None:
        """Idempotent: if the id+user already exists, just bump updated_at."""
        stmt = (
            pg_insert(Conversation)
            .values(
                id=conversation_id,
                user_id=user_id,
                context_claim_id=context_claim_id,
            )
            .on_conflict_do_update(
                index_elements=[Conversation.id],
                set_={"updated_at": datetime.now(timezone.utc)},
            )
        )
        await self._s.execute(stmt)

    async def update_title(
        self, conversation_id: UUID, user_id: UUID, title: str
    ) -> Conversation | None:
        stmt = (
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .where(Conversation.user_id == user_id)
            .values(title=title)
            .returning(Conversation)
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, conversation_id: UUID, user_id: UUID) -> bool:
        stmt = (
            delete(Conversation)
            .where(Conversation.id == conversation_id)
            .where(Conversation.user_id == user_id)
        )
        result = await self._s.execute(stmt)
        return result.rowcount > 0

    async def touch(self, conversation_id: UUID) -> None:
        stmt = (
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=datetime.now(timezone.utc))
        )
        await self._s.execute(stmt)
