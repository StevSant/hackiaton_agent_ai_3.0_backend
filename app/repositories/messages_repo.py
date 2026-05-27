"""Repository for `messages` — append-only, ordered by `sequence` per conversation."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.message import Message


class MessagesRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def next_sequence(self, conversation_id: UUID) -> int:
        stmt = select(func.coalesce(func.max(Message.sequence), -1) + 1).where(
            Message.conversation_id == conversation_id
        )
        result = await self._s.execute(stmt)
        return int(result.scalar_one())

    async def add(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        chart_payload: dict[str, Any] | None = None,
    ) -> Message:
        seq = await self.next_sequence(conversation_id)
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            sequence=seq,
            chart_payload=chart_payload,
        )
        self._s.add(msg)
        await self._s.flush()
        return msg

    async def list_for_conversation(
        self, conversation_id: UUID
    ) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.sequence.asc())
        )
        result = await self._s.execute(stmt)
        return list(result.scalars().all())
