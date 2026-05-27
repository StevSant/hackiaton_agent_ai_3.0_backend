"""GET /claims/{id} smoke test — ml/anomaly fields are present in the response.

Artifacts are not loaded in the test lifespan, so we expect:
- ``ml_probability``      → None
- ``ml_factors``          → []
- ``anomaly_score``       → None
- ``nearest_normal_claim_id`` → None

This locks down the wire contract: the fields exist on the response even when
the adapters aren't wired, so the frontend can rely on their presence.
"""

from __future__ import annotations

import uuid

import httpx
import pytest

from app.api.deps import get_current_user
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.main import create_app


def _stub_user() -> User:
    return User(
        id=uuid.uuid5(uuid.NAMESPACE_URL, "analista@test.local"),
        email="analista@test.local",
        role=Role.analista,
        full_name="Test Analista",
    )


@pytest.mark.asyncio
async def test_claim_detail_returns_ml_fields_at_default() -> None:
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/claims/SIN-0001")

    if response.status_code == 404:
        pytest.skip("Synthetic dataset SIN-0001 not present in this environment.")

    assert response.status_code == 200
    body = response.json()
    assert "ml_probability" in body
    assert "ml_factors" in body
    assert "anomaly_score" in body
    assert "nearest_normal_claim_id" in body

    # No artifacts loaded → defaults.
    assert body["ml_probability"] is None
    assert body["ml_factors"] == []
    assert body["nearest_normal_claim_id"] is None
