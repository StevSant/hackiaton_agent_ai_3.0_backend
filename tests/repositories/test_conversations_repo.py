"""Integration tests for ConversationsRepo — runs against the real test Postgres."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.infrastructure.db.models.conversation import Conversation
from app.repositories.conversations_repo import ConversationsRepo
from app.repositories.messages_repo import MessagesRepo

pytestmark = pytest.mark.asyncio


async def test_upsert_then_list(db_session):
    user_id = uuid4()
    conv_id = uuid4()
    repo = ConversationsRepo(db_session)

    await repo.upsert(conv_id, user_id, context_claim_id=None)
    await db_session.commit()

    listed = await repo.list_for_user(user_id)
    assert len(listed) == 1
    assert listed[0].id == conv_id


async def test_upsert_is_idempotent(db_session):
    user_id = uuid4()
    conv_id = uuid4()
    repo = ConversationsRepo(db_session)

    await repo.upsert(conv_id, user_id, context_claim_id="S-1")
    await repo.upsert(conv_id, user_id, context_claim_id="S-1")
    await db_session.commit()

    listed = await repo.list_for_user(user_id)
    assert len(listed) == 1


async def test_get_filters_by_owner(db_session):
    owner = uuid4()
    other = uuid4()
    conv_id = uuid4()
    repo = ConversationsRepo(db_session)

    await repo.upsert(conv_id, owner, context_claim_id=None)
    await db_session.commit()

    assert await repo.get(conv_id, owner) is not None
    assert await repo.get(conv_id, other) is None


async def test_delete_cascades_messages(db_session):
    user_id = uuid4()
    conv_id = uuid4()
    convs = ConversationsRepo(db_session)
    msgs = MessagesRepo(db_session)

    await convs.upsert(conv_id, user_id, context_claim_id=None)
    await msgs.add(conv_id, "user", "hola")
    await msgs.add(conv_id, "assistant", "qué tal")
    await db_session.commit()

    deleted = await convs.delete(conv_id, user_id)
    await db_session.commit()
    assert deleted is True

    assert await msgs.list_for_conversation(conv_id) == []


async def test_search_matches_title_or_content(db_session):
    user_id = uuid4()
    a_id = uuid4()
    b_id = uuid4()
    convs = ConversationsRepo(db_session)
    msgs = MessagesRepo(db_session)

    await convs.upsert(a_id, user_id, context_claim_id=None)
    await convs.update_title(a_id, user_id, "Proveedor reincidente")
    await msgs.add(a_id, "user", "qué proveedores son sospechosos")

    await convs.upsert(b_id, user_id, context_claim_id=None)
    await convs.update_title(b_id, user_id, "Otra cosa")
    await msgs.add(b_id, "user", "Top 10 siniestros")
    await db_session.commit()

    results = await convs.list_for_user(user_id, query="proveedor")
    assert {c.id for c in results} == {a_id}
