"""Per-request context for perf accounting.

Holds two `ContextVar`s:
- `perf_request_id_var` — opaque id for cross-log correlation.
- `perf_db_time_ms_var` — accumulated DB time (ms) for the current request.

The SQLAlchemy listener writes; the ASGI middleware reads at end-of-request.
"""

from __future__ import annotations

from contextvars import ContextVar

perf_request_id_var: ContextVar[str | None] = ContextVar(
    "perf_request_id", default=None
)
perf_db_time_ms_var: ContextVar[float] = ContextVar("perf_db_time_ms", default=0.0)


def add_db_time_ms(delta: float) -> None:
    """Add `delta` milliseconds to the current request's DB-time accumulator."""
    current = perf_db_time_ms_var.get()
    perf_db_time_ms_var.set(current + delta)


def take_db_time_ms() -> float:
    """Return the current accumulator value, then reset to 0.0."""
    current = perf_db_time_ms_var.get()
    perf_db_time_ms_var.set(0.0)
    return current


def reset_db_time() -> None:
    perf_db_time_ms_var.set(0.0)
