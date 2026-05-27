"""Smoke test for `POST /api/v1/agent/transcribe`."""

import uuid

import httpx
import pytest

from app.api.deps import get_current_user, get_speech_transcriber
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.infrastructure.speech import InMemoryFakeTranscriber
from app.main import create_app


def _stub_user() -> User:
    return User(
        id=uuid.uuid5(uuid.NAMESPACE_URL, "analista@test.local"),
        email="analista@test.local",
        role=Role.analista,
        full_name="Test Analista",
    )


@pytest.mark.asyncio
async def test_agent_transcribe_returns_text() -> None:
    app = create_app()
    app.dependency_overrides[get_speech_transcriber] = lambda: InMemoryFakeTranscriber()
    app.dependency_overrides[get_current_user] = _stub_user

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agent/transcribe",
            files={"file": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["text"] == "¿Cuáles son los 5 siniestros con mayor riesgo?"
