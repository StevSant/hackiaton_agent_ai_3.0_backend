"""Conversation history REST endpoints — all gated by get_current_user."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.domain.auth.user import User
from app.infrastructure.db.engine import get_session
from app.repositories.conversations_repo import ConversationsRepo
from app.repositories.messages_repo import MessagesRepo
from app.schemas.conversation import (
    ConversationDeleted,
    ConversationDetail,
    ConversationRename,
    ConversationSummary,
)
from app.use_cases.conversations.delete_conversation import DeleteConversation
from app.use_cases.conversations.get_conversation import GetConversation
from app.use_cases.conversations.list_conversations import ListConversations
from app.use_cases.conversations.rename_conversation import RenameConversation

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    q: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    context_claim_id: Annotated[str | None, Query()] = None,
    context_provider_id: Annotated[str | None, Query()] = None,
    context_asegurado_id: Annotated[str | None, Query()] = None,
) -> list[ConversationSummary]:
    uc = ListConversations(ConversationsRepo(session), MessagesRepo(session))
    return await uc.execute(
        user.id,
        query=q,
        context_claim_id=context_claim_id,
        context_provider_id=context_provider_id,
        context_asegurado_id=context_asegurado_id,
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationDetail:
    uc = GetConversation(ConversationsRepo(session))
    return await uc.execute(conversation_id, user.id)


@router.patch("/{conversation_id}", response_model=ConversationDetail)
async def rename_conversation(
    conversation_id: UUID,
    body: ConversationRename,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationDetail:
    uc = RenameConversation(ConversationsRepo(session))
    result = await uc.execute(conversation_id, user.id, body.title)
    await session.commit()
    return result


@router.delete("/{conversation_id}", response_model=ConversationDeleted)
async def delete_conversation(
    conversation_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationDeleted:
    uc = DeleteConversation(ConversationsRepo(session))
    await uc.execute(conversation_id, user.id)
    await session.commit()
    return ConversationDeleted(ok=True)
