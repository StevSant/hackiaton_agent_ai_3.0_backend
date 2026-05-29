"""Repository for `messages` — append-only, ordered by `sequence` per conversation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.message import Message

# Conversation-list snippet length (last user message preview).
_SNIPPET_LEN = 140


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
        transparency_metadata: dict[str, Any] | None = None,
    ) -> Message:
        seq = await self.next_sequence(conversation_id)
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            sequence=seq,
            chart_payload=chart_payload,
            transparency_metadata=transparency_metadata,
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

    async def latest_user_snippets(
        self, conversation_ids: Sequence[UUID]
    ) -> dict[UUID, str]:
        """Last user-message preview for each conversation, in ONE query.

        Replaces the N+1 "load every message of every conversation" pattern the
        conversation list used. A window function ranks user messages per
        conversation by sequence and keeps the latest, selecting only `content`
        (never the big chart_payload / transparency_metadata columns).
        """
        if not conversation_ids:
            return {}
        ranked = (
            select(
                Message.conversation_id.label("cid"),
                Message.content.label("content"),
                func.row_number()
                .over(
                    partition_by=Message.conversation_id,
                    order_by=Message.sequence.desc(),
                )
                .label("rn"),
            )
            .where(
                Message.conversation_id.in_(conversation_ids),
                Message.role == "user",
                Message.content != "",
            )
            .subquery()
        )
        stmt = select(ranked.c.cid, ranked.c.content).where(ranked.c.rn == 1)
        result = await self._s.execute(stmt)
        return {row.cid: (row.content or "")[:_SNIPPET_LEN] for row in result.all()}
