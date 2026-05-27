"""Smoke: two /agent/ask calls with the same conversation_id should persist 4 messages."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio


async def _login_token(client) -> str:
    # Seed user from .env AUTH_SEED_USERS — analista@demo.com / Demo.Analista2026
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "analista@demo.com", "password": "Demo.Analista2026"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _consume_sse(resp) -> list[dict]:
    events: list[dict] = []
    async for line in resp.aiter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: "):]))
    return events


async def test_two_asks_persist_four_messages(client):
    token = await _login_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    conv_id = str(uuid4())

    async with client.stream(
        "POST",
        "/api/v1/agent/ask",
        headers=headers,
        json={"message": "Hola", "conversation_id": conv_id},
    ) as resp:
        await _consume_sse(resp)

    async with client.stream(
        "POST",
        "/api/v1/agent/ask",
        headers=headers,
        json={"message": "Otra pregunta", "conversation_id": conv_id},
    ) as resp:
        await _consume_sse(resp)

    detail = await client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert len(body["messages"]) == 4
    assert [m["role"] for m in body["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
