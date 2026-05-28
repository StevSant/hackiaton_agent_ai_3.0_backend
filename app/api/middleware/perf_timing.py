"""ASGI middleware that logs total + DB time per request.

Pairs with `sqlalchemy_perf_listener`: that listener accumulates per-query
duration into a `ContextVar` keyed by request; this middleware reads it on
response and emits a single structured log line.

Off-path: gated by `settings.PERF_TIMING_ENABLED` — when false, the middleware
short-circuits to a passthrough.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.middleware.perf_context import (
    perf_request_id_var,
    reset_db_time,
    take_db_time_ms,
)
from app.core.config import settings

logger = logging.getLogger("app.perf")


class PerfTimingMiddleware:
    """Log `request_id route status total_ms db_ms` per HTTP request."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not settings.PERF_TIMING_ENABLED:
            await self._app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex[:12]
        token = perf_request_id_var.set(request_id)
        reset_db_time()

        start = time.perf_counter()
        status_holder: dict[str, int] = {"code": 0}

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                status_holder["code"] = int(message.get("status", 0))
            await send(message)

        try:
            await self._app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            db_ms = take_db_time_ms()
            route = scope.get("path", "")
            method = scope.get("method", "")
            logger.info(
                "perf",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "route": route,
                    "status": status_holder["code"],
                    "total_ms": round(elapsed_ms, 2),
                    "db_ms": round(db_ms, 2),
                },
            )
            perf_request_id_var.reset(token)
