"""Tests for F2 — GET /api/v1/conversations with entity-context filters.

Strategy: override get_current_user + get_session with in-memory stubs so no
real DB is required. The ConversationsRepo and ListConversations use case are
exercised through a lightweight stub on the repo layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from collections.abc import AsyncIterator

import pytest
import httpx

from app.api.deps import get_current_user
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.infrastructure.db.engine import get_session
from app.main import create_app
from app.schemas.conversation import ConversationSummary

# ---------------------------------------------------------------------------
# Shared stubs
# ---------------------------------------------------------------------------

_USER_ID = uuid.uuid5(uuid.NAMESPACE_URL, "analista@test.local")

_PROVIDER_ID = "PROV-001"
_ASEGURADO_ID = "ASE-001"
_CLAIM_ID = "SIN-001"

_NOW = datetime.now(timezone.utc)


def _stub_user() -> User:
    return User(
        id=_USER_ID,
        email="analista@test.local",
        role=Role.analista,
        full_name="Test Analista",
    )


def _make_summary(
    context_provider_id: str | None = None,
    context_asegurado_id: str | None = None,
    context_claim_id: str | None = None,
) -> ConversationSummary:
    return ConversationSummary(
        id=uuid.uuid4(),
        title="Test conversation",
        context_claim_id=context_claim_id,
        context_provider_id=context_provider_id,
        context_asegurado_id=context_asegurado_id,
        snippet="hola",
        created_at=_NOW,
        updated_at=_NOW,
    )


# ---------------------------------------------------------------------------
# Test: filter by context_provider_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_conversations_filter_by_provider_id() -> None:
    """?context_provider_id=X returns only conversations tagged with that provider."""
    import app.api.v1.conversations as _conv_module
    from app.use_cases.conversations.list_conversations import ListConversations

    provider_conv = _make_summary(context_provider_id=_PROVIDER_ID)
    other_conv = _make_summary(context_provider_id="PROV-OTHER")

    # Patch ListConversations.execute so the test controls what 'rows' come back
    # based on the filter params — simulating DB-level WHERE filtering.
    original_execute = ListConversations.execute

    async def _fake_execute(
        self: Any,
        user_id: Any,
        query: Any = None,
        context_claim_id: str | None = None,
        context_provider_id: str | None = None,
        context_asegurado_id: str | None = None,
    ) -> list[ConversationSummary]:
        if context_provider_id == _PROVIDER_ID:
            return [provider_conv]
        return [provider_conv, other_conv]

    ListConversations.execute = _fake_execute  # type: ignore[method-assign]

    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user

    # Stub get_session to avoid real DB
    async def _fake_session() -> AsyncIterator[Any]:
        session = MagicMock()
        session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
        yield session

    app.dependency_overrides[get_session] = _fake_session

    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    f"/api/v1/conversations?context_provider_id={_PROVIDER_ID}"
                )
    finally:
        ListConversations.execute = original_execute  # type: ignore[method-assign]

    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["context_provider_id"] == _PROVIDER_ID


@pytest.mark.asyncio
async def test_list_conversations_filter_by_asegurado_id() -> None:
    """?context_asegurado_id=X returns only conversations tagged with that asegurado."""
    import app.api.v1.conversations as _conv_module
    from app.use_cases.conversations.list_conversations import ListConversations

    ase_conv = _make_summary(context_asegurado_id=_ASEGURADO_ID)

    original_execute = ListConversations.execute

    async def _fake_execute(
        self: Any,
        user_id: Any,
        query: Any = None,
        context_claim_id: str | None = None,
        context_provider_id: str | None = None,
        context_asegurado_id: str | None = None,
    ) -> list[ConversationSummary]:
        if context_asegurado_id == _ASEGURADO_ID:
            return [ase_conv]
        return []

    ListConversations.execute = _fake_execute  # type: ignore[method-assign]

    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user

    async def _fake_session() -> AsyncIterator[Any]:
        session = MagicMock()
        yield session

    app.dependency_overrides[get_session] = _fake_session

    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    f"/api/v1/conversations?context_asegurado_id={_ASEGURADO_ID}"
                )
    finally:
        ListConversations.execute = original_execute  # type: ignore[method-assign]

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) == 1
    assert data[0]["context_asegurado_id"] == _ASEGURADO_ID


@pytest.mark.asyncio
async def test_list_conversations_no_filter_returns_all() -> None:
    """Without filters, all the user's conversations are returned."""
    from app.use_cases.conversations.list_conversations import ListConversations

    all_convs = [
        _make_summary(context_provider_id=_PROVIDER_ID),
        _make_summary(context_asegurado_id=_ASEGURADO_ID),
    ]

    original_execute = ListConversations.execute

    async def _fake_execute(
        self: Any,
        user_id: Any,
        query: Any = None,
        context_claim_id: str | None = None,
        context_provider_id: str | None = None,
        context_asegurado_id: str | None = None,
    ) -> list[ConversationSummary]:
        # No filter → return all
        if not any([context_claim_id, context_provider_id, context_asegurado_id]):
            return all_convs
        return []

    ListConversations.execute = _fake_execute  # type: ignore[method-assign]

    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user

    async def _fake_session() -> AsyncIterator[Any]:
        yield MagicMock()

    app.dependency_overrides[get_session] = _fake_session

    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/conversations")
    finally:
        ListConversations.execute = original_execute  # type: ignore[method-assign]

    assert response.status_code == 200, response.text
    assert len(response.json()) == 2
