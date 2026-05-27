"""Smoke test for `GET /api/v1/status/ai`.

The status route surfaces lifespan-pinned AI state. We override `get_ai_state`
so the test doesn't depend on a real sentence-transformer download — fast and
hermetic.
"""

import httpx
import pytest

from app.api.deps import get_ai_state
from app.core.lifespan_state import AIState
from app.infrastructure.llm import InMemoryFakeLLM, PromptLoader
from app.main import create_app


def _fake_ai_state() -> AIState:
    from pathlib import Path

    prompts_dir = (
        Path(__file__).resolve().parents[1] / "app" / "agents" / "claims_agent" / "prompts"
    )
    return AIState(
        llm=InMemoryFakeLLM(),
        llm_provider="fake",
        llm_model="gpt-4o-mini",
        embeddings=None,
        embeddings_model="paraphrase-multilingual-MiniLM-L12-v2",
        embeddings_dim=384,
        prompts=PromptLoader(base_dir=prompts_dir),
        fraud_classifier=None,
        fraud_model_present=False,
        anomaly_detector=None,
        anomaly_model_present=False,
        nearest_normal_index_present=False,
    )


@pytest.mark.asyncio
async def test_status_ai_returns_lifespan_snapshot() -> None:
    app = create_app()
    app.dependency_overrides[get_ai_state] = _fake_ai_state

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/status/ai")

    assert response.status_code == 200
    body = response.json()
    assert body["llm_provider"] == "fake"
    assert body["llm_model"] == "gpt-4o-mini"
    assert body["embeddings_loaded"] is False
    assert body["embeddings_dim"] == 384
    assert body["fraud_model_present"] is False
    assert body["anomaly_model_present"] is False
    assert "claims_system.v1" in body["prompts_loaded"]
    assert "route.v1" in body["prompts_loaded"]
    assert "compose.v1" in body["prompts_loaded"]
