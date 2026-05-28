"""ConversationPersister — DB writes around an agent stream.

Owns short-lived sessions so the SSE stream never holds a connection open.

Lifecycle per agent turn:
  1. `before_stream(...)`     — upsert conversation + write user Message
  2. (stream runs, no DB ops)
  3. `after_stream(...)`      — write assistant Message
  4. `schedule_title(...)`    — fire-and-forget task to generate the title
                                 if and only if this was the first turn
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.auth.user import User
from app.repositories.conversations_repo import ConversationsRepo
from app.repositories.messages_repo import MessagesRepo
from app.use_cases.conversations.generate_conversation_title import (
    GenerateConversationTitle,
)

logger = logging.getLogger(__name__)

SessionFactory = async_sessionmaker[AsyncSession] | Callable[[], Any]


class ConversationPersister:
    def __init__(
        self,
        session_factory: SessionFactory,
        title_generator: GenerateConversationTitle,
    ) -> None:
        self._sf = session_factory
        self._title_gen = title_generator

    async def before_stream(
        self,
        *,
        conversation_id: UUID,
        user: User,
        query: str,
        context_claim_id: str | None,
    ) -> int:
        """Returns the sequence number that was written for the user message."""
        async with self._sf() as session:
            convs = ConversationsRepo(session)
            msgs = MessagesRepo(session)
            await convs.upsert(conversation_id, user.id, context_claim_id)
            written = await msgs.add(conversation_id, "user", query)
            await convs.touch(conversation_id)
            await session.commit()
            return written.sequence

    async def after_stream(
        self,
        *,
        conversation_id: UUID,
        user: User,
        answer: str,
        chart_payload: dict[str, Any] | None = None,
        transparency_metadata: dict[str, Any] | None = None,
    ) -> int:
        async with self._sf() as session:
            convs = ConversationsRepo(session)
            msgs = MessagesRepo(session)
            written = await msgs.add(
                conversation_id,
                "assistant",
                answer,
                chart_payload=chart_payload,
                transparency_metadata=transparency_metadata,
            )
            await convs.touch(conversation_id)
            await session.commit()
            return written.sequence

    def schedule_title(
        self,
        *,
        conversation_id: UUID,
        user: User,
        query: str,
        answer: str,
        assistant_sequence: int,
    ) -> None:
        # Only generate a title on the very first assistant turn.
        if assistant_sequence != 1:
            return
        _task = asyncio.create_task(
            self._generate_and_save_title(
                conversation_id=conversation_id,
                user=user,
                query=query,
                answer=answer,
            )
        )
        # Keep a reference to prevent the task from being garbage-collected.
        del _task

    async def _generate_and_save_title(
        self,
        *,
        conversation_id: UUID,
        user: User,
        query: str,
        answer: str,
    ) -> None:
        try:
            title = await self._title_gen.execute(query, answer)
            async with self._sf() as session:
                convs = ConversationsRepo(session)
                await convs.update_title(conversation_id, user.id, title)
                await session.commit()
        except Exception as exc:
            logger.warning(
                "Title generation/persist failed for conv %s: %s", conversation_id, exc
            )
