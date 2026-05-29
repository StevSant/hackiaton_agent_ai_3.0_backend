"""DbDisconnectRetryMiddleware: retry idempotent requests on pooler resets.

Drives the raw ASGI middleware with a scripted downstream app — no DB, no
HTTP client. The disconnect is simulated with the same exception shape the
asyncpg dialect raises in production (DBAPIError wrapping the driver error).
"""

from __future__ import annotations

from typing import Any

import pytest
from asyncpg.exceptions import ConnectionDoesNotExistError
from sqlalchemy.exc import DBAPIError

from app.api.middleware import DbDisconnectRetryMiddleware
from app.infrastructure.db import is_disconnect_error


def _disconnect_exc() -> DBAPIError:
    return DBAPIError(
        "SELECT 1",
        None,
        ConnectionDoesNotExistError("connection was closed in the middle of operation"),
        connection_invalidated=True,
    )


def _scope(method: str) -> dict[str, Any]:
    return {"type": "http", "method": method, "path": "/api/v1/claims", "headers": []}


async def _receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b"", "more_body": False}


class _SendRecorder:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def __call__(self, message: dict[str, Any]) -> None:
        self.messages.append(message)

    @property
    def status(self) -> int | None:
        for m in self.messages:
            if m["type"] == "http.response.start":
                return int(m["status"])
        return None


def _app_fail_then_ok(failures: int) -> tuple[Any, dict[str, int]]:
    """Downstream app raising a disconnect the first `failures` calls."""
    calls = {"n": 0}

    async def app(scope: Any, receive: Any, send: Any) -> None:
        calls["n"] += 1
        if calls["n"] <= failures:
            raise _disconnect_exc()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    return app, calls


async def test_get_retries_once_and_succeeds() -> None:
    app, calls = _app_fail_then_ok(failures=1)
    mw = DbDisconnectRetryMiddleware(app)
    send = _SendRecorder()

    await mw(_scope("GET"), _receive, send)

    assert calls["n"] == 2
    assert send.status == 200


async def test_get_exhausted_retries_returns_503() -> None:
    app, calls = _app_fail_then_ok(failures=99)
    mw = DbDisconnectRetryMiddleware(app)
    send = _SendRecorder()

    await mw(_scope("GET"), _receive, send)

    assert calls["n"] == 2  # initial attempt + DB_DISCONNECT_RETRY_MAX
    assert send.status == 503
    body = b"".join(
        m.get("body", b"") for m in send.messages if m["type"] == "http.response.body"
    )
    assert b"database_unavailable" in body


async def test_post_is_not_retried_returns_503() -> None:
    app, calls = _app_fail_then_ok(failures=99)
    mw = DbDisconnectRetryMiddleware(app)
    send = _SendRecorder()

    await mw(_scope("POST"), _receive, send)

    assert calls["n"] == 1
    assert send.status == 503


async def test_non_disconnect_errors_propagate() -> None:
    async def app(scope: Any, receive: Any, send: Any) -> None:
        raise ValueError("not a db problem")

    mw = DbDisconnectRetryMiddleware(app)

    with pytest.raises(ValueError):
        await mw(_scope("GET"), _receive, _SendRecorder())


async def test_disconnect_after_completed_response_is_swallowed() -> None:
    """Teardown rollback noise: client already got its response — no traceback."""

    async def app(scope: Any, receive: Any, send: Any) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})
        raise _disconnect_exc()

    mw = DbDisconnectRetryMiddleware(app)
    send = _SendRecorder()

    await mw(_scope("GET"), _receive, send)  # must not raise

    assert send.status == 200


async def test_disconnect_mid_stream_reraises() -> None:
    async def app(scope: Any, receive: Any, send: Any) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"chunk", "more_body": True})
        raise _disconnect_exc()

    mw = DbDisconnectRetryMiddleware(app)

    with pytest.raises(DBAPIError):
        await mw(_scope("GET"), _receive, _SendRecorder())


def test_classifier_matches_production_exception_chain() -> None:
    # Mirror the real chain: DBAPIError.__cause__ → driver error, .orig set.
    driver = ConnectionDoesNotExistError("connection was closed")
    exc = DBAPIError("SELECT 1", None, driver)
    exc.__cause__ = driver
    assert is_disconnect_error(exc)


def test_classifier_ignores_non_db_connection_errors() -> None:
    # A bare TCP reset (e.g. httpx → OpenAI) must NOT classify as DB outage.
    assert not is_disconnect_error(ConnectionResetError("peer reset"))
    assert not is_disconnect_error(ValueError("nope"))
