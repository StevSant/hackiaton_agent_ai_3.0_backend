"""Smoke tests for POST /api/v1/claims/import/stream — the SSE import endpoint.

TDD: written FIRST. Tests drive the implementation shape.

Strategy:
- Use FastAPI's dependency_overrides to inject a no-op AsyncSession stub.
- The stream use case is also overridden with a controlled async-generator so
  unit tests never touch a real DB, embeddings, or ML model.
- Two scenarios:
    1. Golden path: 2-row JSON → events arrive in order, totals are correct.
    2. One malformed row: import.error fires, valid row still processes.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.main import create_app
from app.schemas.imports.stream import (
    CaseCompletedEvent,
    ImportCompletedEvent,
    ImportErrorEvent,
    ImportStartedEvent,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stub_user() -> User:
    return User(
        id=uuid.uuid5(uuid.NAMESPACE_URL, "analista@test.local"),
        email="analista@test.local",
        role=Role.analista,
        full_name="Test Analista",
    )


def _two_row_json() -> bytes:
    """Minimal 2-row JSON body that the parser accepts."""
    rows = [
        {
            "id": "SIN-T001",
            "ramo": "Vehículos",
            "cobertura": "Responsabilidad Civil",
            "asegurado": "Prueba Uno",
            "asegurado_id": "ASE-T001",
            "poliza": "POL-T001",
            "ciudad": "Guayaquil",
            "fecha_ocurrencia": "2026-04-10",
            "fecha_reporte": "2026-04-12",
            "monto_reclamado": 1500.0,
            "suma_asegurada": 20000.0,
            "estado": "Reserva",
            "sucursal": "Guayaquil Centro",
            "descripcion": "Choque leve en semáforo.",
            "score": 0,
            "nivel": "verde",
        },
        {
            "id": "SIN-T002",
            "ramo": "Vehículos",
            "cobertura": "Pérdida Total por Robo",
            "asegurado": "Prueba Dos",
            "asegurado_id": "ASE-T002",
            "poliza": "POL-T002",
            "ciudad": "Quito",
            "fecha_ocurrencia": "2026-05-01",
            "fecha_reporte": "2026-05-07",
            "monto_reclamado": 28000.0,
            "suma_asegurada": 28000.0,
            "estado": "Reserva",
            "sucursal": "Quito Norte",
            "descripcion": "Robo total del vehículo.",
            "score": 0,
            "nivel": "verde",
        },
    ]
    return json.dumps(rows).encode()


def _parse_sse_events(body: str) -> list[dict]:
    """Extract JSON payloads from an SSE text body."""
    events: list[dict] = []
    for line in body.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


# ---------------------------------------------------------------------------
# Fake session override — no real DB in unit tests
# ---------------------------------------------------------------------------


async def _fake_optional_session() -> AsyncIterator[AsyncSession | None]:
    yield None  # No real DB session for unit tests


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_stream_golden_path_two_rows() -> None:
    """POST a 2-row JSON file; assert event order and totals."""
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user

    # Override the optional-session dependency so the endpoint doesn't crash
    # when there's no real DB available.
    from app.api.v1.imports import _get_optional_session  # type: ignore[attr-defined]
    app.dependency_overrides[_get_optional_session] = _fake_optional_session

    content = _two_row_json()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/claims/import/stream",
                content=content,
                headers={
                    "Content-Type": "application/json",
                    "Content-Disposition": "attachment; filename=claims.json",
                },
            )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse_events(response.text)
    types = [e["type"] for e in events]

    # Must start with import.started
    assert types[0] == "import.started", f"Got: {types}"

    # Must end with import.completed
    assert types[-1] == "import.completed", f"Got: {types}"

    # parse.row events for both claims
    parse_row_events = [e for e in events if e["type"] == "parse.row"]
    assert len(parse_row_events) == 2

    # case.completed events for both claims
    case_completed_events = [e for e in events if e["type"] == "case.completed"]
    assert len(case_completed_events) == 2

    # Totals in import.completed
    completed = events[-1]
    assert completed["data"]["imported"] == 2
    assert completed["data"]["skipped"] == 0

    # No errors on the golden path
    assert "import.error" not in types


@pytest.mark.asyncio
async def test_import_stream_error_row_continues_batch() -> None:
    """A row that raises during processing emits import.error; other rows still process.

    We override ``stream_import_claims`` at the module level so we can control exactly
    what the generator yields without needing a real DB or ML models.
    """
    from app.schemas.imports.stream import (
        CaseCompletedData,
        ImportCompletedData,
        ImportErrorData,
        ImportStartedData,
    )

    async def _controlled_stream(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        """Async generator that simulates one good row + one error row."""
        yield ImportStartedEvent(data=ImportStartedData(total_rows=2, filename="test.json"))
        yield CaseCompletedEvent(
            data=CaseCompletedData(
                claim_id="SIN-OK",
                score=25,
                tier="verde",
                persisted=False,
                rules_fired=0,
            )
        )
        yield ImportErrorEvent(
            data=ImportErrorData(row_index=1, claim_id="SIN-BAD", message="forced error")
        )
        yield ImportCompletedEvent(
            data=ImportCompletedData(imported=1, skipped=1, errors=["SIN-BAD: forced error"])
        )

    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user

    from app.api.v1.imports import _get_optional_session  # type: ignore[attr-defined]
    app.dependency_overrides[_get_optional_session] = _fake_optional_session

    import app.api.v1.imports as _imports_module

    original = _imports_module.stream_import_claims

    async def _patched_stream(records, filename, session, **kwargs):  # type: ignore[no-untyped-def]
        return _controlled_stream()

    _imports_module.stream_import_claims = _patched_stream  # type: ignore[assignment]

    content = json.dumps([{
        "id": "SIN-T003",
        "ramo": "Vehículos",
        "cobertura": "Responsabilidad Civil",
        "asegurado": "Test",
        "asegurado_id": "ASE-T003",
        "poliza": "POL-T003",
        "ciudad": "Guayaquil",
        "fecha_ocurrencia": "2026-04-10",
        "fecha_reporte": "2026-04-12",
        "monto_reclamado": 1000.0,
        "suma_asegurada": 15000.0,
        "estado": "Reserva",
        "sucursal": "Guayaquil Centro",
        "descripcion": "Test.",
        "score": 0,
        "nivel": "verde",
    }]).encode()

    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/claims/import/stream",
                    content=content,
                    headers={
                        "Content-Type": "application/json",
                        "Content-Disposition": "attachment; filename=claims.json",
                    },
                )
    finally:
        _imports_module.stream_import_claims = original  # type: ignore[assignment]

    assert response.status_code == 200, response.text
    events = _parse_sse_events(response.text)
    types = [e["type"] for e in events]

    assert types[0] == "import.started"
    assert types[-1] == "import.completed"
    assert "import.error" in types

    completed = events[-1]
    assert completed["data"]["imported"] == 1
    assert completed["data"]["skipped"] == 1


@pytest.mark.asyncio
async def test_import_stream_dry_run_no_session() -> None:
    """When no DB session is available, the endpoint streams events in dry-run mode.

    Claims are scored but not persisted; case.completed.data.persisted is False.
    """
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user

    from app.api.v1.imports import _get_optional_session  # type: ignore[attr-defined]
    app.dependency_overrides[_get_optional_session] = _fake_optional_session

    content = _two_row_json()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/claims/import/stream",
                content=content,
                headers={
                    "Content-Type": "application/json",
                    "Content-Disposition": "attachment; filename=claims.json",
                },
            )

    # Dry-run still returns 200 SSE stream
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    types = [e["type"] for e in events]
    assert types[0] == "import.started"
    assert types[-1] == "import.completed"

    # All case.completed events have persisted=False in dry-run
    completed_events = [e for e in events if e["type"] == "case.completed"]
    assert len(completed_events) == 2
    for ev in completed_events:
        assert ev["data"]["persisted"] is False


@pytest.mark.asyncio
async def test_import_stream_events_ordered_correctly() -> None:
    """Verify strict ordering: started → parse.row → case.* → completed."""
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user

    from app.api.v1.imports import _get_optional_session  # type: ignore[attr-defined]
    app.dependency_overrides[_get_optional_session] = _fake_optional_session

    content = _two_row_json()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/claims/import/stream",
                content=content,
                headers={
                    "Content-Type": "application/json",
                    "Content-Disposition": "attachment; filename=claims.json",
                },
            )

    events = _parse_sse_events(response.text)
    types = [e["type"] for e in events]

    # import.started is first
    assert types[0] == "import.started"

    # import.completed is last
    assert types[-1] == "import.completed"

    # case.completed always comes after case.started within a claim's events
    started_indices = [i for i, t in enumerate(types) if t == "case.started"]
    completed_indices = [i for i, t in enumerate(types) if t == "case.completed"]
    for s, c in zip(started_indices, completed_indices, strict=False):
        assert s < c, f"case.started at {s} should precede case.completed at {c}"

    # parse.row precedes case.started for the same claim
    parse_indices = [i for i, t in enumerate(types) if t == "parse.row"]
    for p, s in zip(parse_indices, started_indices, strict=False):
        assert p < s, f"parse.row at {p} should precede case.started at {s}"
