"""Register SQLAlchemy event hooks that accumulate per-query DB time.

Wired once at app startup from `main.lifespan` against the live async engine's
sync sibling (`engine.sync_engine`). Each query's wall-time gets added to the
current request's `perf_db_time_ms_var`; if there's no active request (CLI,
lifespan task), the addition is a no-op.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.middleware.perf_context import (
    add_db_time_ms,
    perf_request_id_var,
)

_START_KEY = "_perf_query_start"


def register_sqlalchemy_perf_listener(engine: AsyncEngine) -> None:
    """Attach before/after-execute hooks to the underlying sync engine."""
    sync_engine: Engine = engine.sync_engine

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        conn.info[_START_KEY] = time.perf_counter()

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        start = conn.info.pop(_START_KEY, None)
        if start is None:
            return
        if perf_request_id_var.get() is None:
            return  # off-request work (CLI / lifespan task)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        add_db_time_ms(elapsed_ms)
