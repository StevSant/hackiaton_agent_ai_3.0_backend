"""GET /claims/{id} smoke test — ml/anomaly fields are present in the response.

This locks down the wire contract: every claim detail surfaces all four
explainability extras (`ml_probability`, `ml_factors`, `anomaly_score`,
`nearest_normal_claim_id`) so the frontend can rely on their presence.
Values vary depending on whether the optional model artifacts were loaded
by the lifespan — the assertions only check that the keys exist and (when
present) carry sane shapes.
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

    # `httpx.ASGITransport` does not run FastAPI's lifespan — wrap the client
    # block in the app's lifespan context so `set_session_factory` runs and
    # `DbClaimQueries` can resolve a session.
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/claims/SIN-0001")

    if response.status_code == 404:
        pytest.skip("Synthetic dataset SIN-0001 not present in this environment.")

    assert response.status_code == 200
    body = response.json()
    assert "ml_probability" in body
    assert "ml_factors" in body
    assert "anomaly_score" in body
    assert "nearest_normal_claim_id" in body

    # Shapes are stable whether or not the optional model artifacts loaded.
    if body["ml_probability"] is not None:
        assert 0.0 <= body["ml_probability"] <= 1.0
    assert isinstance(body["ml_factors"], list)
    if body["anomaly_score"] is not None:
        assert isinstance(body["anomaly_score"], (int, float))
