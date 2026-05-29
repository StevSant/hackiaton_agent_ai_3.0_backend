"""ASGI middleware that absorbs mid-request DB disconnects from the pooler.

The Supabase pooler occasionally resets *live* connections (maintenance,
session reshuffles). `pool_pre_ping` only protects checkout, so a connection
can die while a request is using it. SQLAlchemy already invalidates the stale
pool generation on the failed attempt, so a retry runs on a fresh connection.

Behavior on a classified disconnect:
- idempotent request (GET/HEAD), response not started → retry once;
- retries exhausted or non-idempotent, response not started → clean 503
  (`database_unavailable`, same wire shape as the AppError handler);
- response fully sent (teardown rollback noise) → log + swallow;
- response started but unfinished (mid-stream) → re-raise, nothing to salvage.
"""

from __future__ import annotations

import asyncio
import logging

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings
from app.core.errors import DatabaseUnavailable
from app.infrastructure.db import is_disconnect_error

logger = logging.getLogger("app.db_retry")

_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD"})


class DbDisconnectRetryMiddleware:
    """Retry idempotent requests once when the pooler drops the connection."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        method: str = scope.get("method", "")
        path: str = scope.get("path", "")
        max_retries = (
            settings.DB_DISCONNECT_RETRY_MAX if method in _IDEMPOTENT_METHODS else 0
        )

        # Cache request messages so a retry can replay them to the fresh
        # dependency stack (GET bodies are empty, but FastAPI may still read).
        cached: list[Message] = []

        def make_receive() -> Receive:
            idx = 0

            async def _receive() -> Message:
                nonlocal idx
                if idx < len(cached):
                    message = cached[idx]
                else:
                    message = await receive()
                    cached.append(message)
                idx += 1
                return message

            return _receive

        started = False
        completed = False

        async def send_wrapper(message: Message) -> None:
            nonlocal started, completed
            if message["type"] == "http.response.start":
                started = True
            elif message["type"] == "http.response.body" and not message.get(
                "more_body"
            ):
                completed = True
            await send(message)

        attempt = 0
        while True:
            try:
                await self._app(scope, make_receive(), send_wrapper)
                return
            except Exception as exc:
                if not is_disconnect_error(exc):
                    raise
                if completed:
                    # Teardown-only failure: the client already got its
                    # response — don't let uvicorn print a scary traceback.
                    logger.warning(
                        "DB connection dropped after response completed: %s %s",
                        method,
                        path,
                    )
                    return
                if started:
                    raise  # mid-stream — can't retry or replace the response
                if attempt < max_retries:
                    attempt += 1
                    logger.warning(
                        "DB disconnect on %s %s — retrying (%d/%d)",
                        method,
                        path,
                        attempt,
                        max_retries,
                    )
                    await asyncio.sleep(settings.DB_CONNECT_RETRY_BACKOFF_S)
                    continue
                logger.warning(
                    "DB disconnect on %s %s — returning 503", method, path
                )
                response = JSONResponse(
                    status_code=DatabaseUnavailable.status_code,
                    content={
                        "code": DatabaseUnavailable.code,
                        "message": DatabaseUnavailable.message,
                    },
                )
                await response(scope, make_receive(), send_wrapper)
                return
