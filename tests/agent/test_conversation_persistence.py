"""Smoke: two /agent/ask calls with the same conversation_id should persist 4 messages.

Integration test — requires a real Postgres DB (runs the app lifespan) and
a seed user in AUTH_SEED_USERS.

Run against a live uvicorn server, not the in-process ASGI test client, because
this test needs the full FastAPI lifespan (DB session factory setup, ML model
loading). The pytest.mark.skip is a guard for `uv run pytest -q`; remove it to
run the test manually against a running dev server.
"""

from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest

pytestmark = pytest.mark.asyncio

_BASE_URL = "http://localhost:8000"


async def _login_token(base_url: str) -> str:
    # Seed user from .env AUTH_SEED_USERS — analista@demo.com / Demo.Analista2026
    async with httpx.AsyncClient(base_url=base_url) as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "analista@demo.com", "password": "Demo.Analista2026"},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]


async def _consume_sse(resp: httpx.Response) -> list[dict]:
    events: list[dict] = []
    async for line in resp.aiter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: "):]))
    return events


@pytest.mark.integration
@pytest.mark.skip(reason="Requires live dev server — uv run uvicorn app.main:app")
async def test_two_asks_persist_four_messages() -> None:
    """Two /agent/ask turns with the same conversation_id should persist 4 messages.

    To run:
        1. Start the dev server: uv run uvicorn app.main:app --reload --port 8000
        2. Run: uv run pytest tests/agent/test_conversation_persistence.py -m integration -v
           (with the @pytest.mark.skip removed)
    """
    token = await _login_token(_BASE_URL)
    headers = {"Authorization": f"Bearer {token}"}
    conv_id = str(uuid4())

    async with httpx.AsyncClient(base_url=_BASE_URL) as client:
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
