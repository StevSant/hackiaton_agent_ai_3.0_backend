"""SQLAlchemy 2.0 async engine, session factory, and FastAPI session dependency.

The engine and session_factory are created once at app startup (lifespan) and
stored on app.state.  The `get_session` dependency yields an AsyncSession per
request; routes never touch the engine directly.
"""

import asyncio
from collections.abc import AsyncGenerator

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.errors import DatabaseUnavailable


def create_engine() -> AsyncEngine:
    # Supabase serves Postgres through pgbouncer in transaction-pooling mode,
    # which breaks asyncpg's named prepared statements. Disabling both caches
    # forces every statement to be sent as unnamed/parse-each-time, so the
    # connection pool can rotate freely.
    #
    # Pool hardening for Supabase + transaction pooler:
    # - Small pool: the Supabase pooler does the real pooling; keep ours tight.
    # - pool_recycle=1800: drop connections older than 30 min so we don't hand
    #   out sockets the pooler has already closed.
    # - pool_timeout=10: don't block requests for 30s waiting on a pool slot.
    # - connect_args["timeout"]=10: fail fast on TCP/SSL connect (asyncpg
    #   defaults to 60s — too long for a request to hang on).
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.APP_ENV == "dev" and settings.LOG_LEVEL == "DEBUG",
        pool_pre_ping=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE_S,
        pool_timeout=settings.DB_POOL_TIMEOUT_S,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "timeout": 10,
        },
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def _classify_connect_error(exc: BaseException) -> str | None:
    """Walk the exception chain and classify a connection failure.

    - "retryable": fast connect blip (DNS gaierror, connection refused/reset) —
      worth a quick retry, the remote pooler likely hiccupped mid-burst.
    - "down": connect timed out (host unreachable). Retrying just multiplies
      the wait, so we fail fast with a 503.
    - None: not a connection error — let it propagate as-is (real 500).

    TimeoutError is checked before OSError because it subclasses OSError; a
    socket.gaierror (also an OSError) means DNS, which is the retryable case.
    """
    seen: set[int] = set()
    nodes: list[BaseException] = []
    cursor: BaseException | None = exc
    while cursor is not None and id(cursor) not in seen:
        seen.add(id(cursor))
        nodes.append(cursor)
        # SQLAlchemy wraps the driver error on .orig — inspect it too.
        orig = getattr(cursor, "orig", None)
        if isinstance(orig, BaseException) and id(orig) not in seen:
            seen.add(id(orig))
            nodes.append(orig)
        cursor = cursor.__cause__ or cursor.__context__
    kind: str | None = None
    for node in nodes:
        if isinstance(node, TimeoutError):
            kind = "down"
        elif isinstance(node, OSError):
            return "retryable"
    return kind


async def _safe_rollback(session: AsyncSession) -> None:
    """Best-effort reset of session state after a failed connect, so the next
    retry starts from a clean transaction. Nothing to do if it also fails."""
    try:
        await session.rollback()
    except (SQLAlchemyError, OSError):
        pass


async def ensure_session_connected(session: AsyncSession) -> None:
    """Open the session's DB connection up front, retrying transient connect
    blips to the remote pooler.

    Without this, SQLAlchemy never retries a failed *initial* connect: a single
    DNS/TCP hiccup during a parallel request burst surfaces as a raw 500. Here
    we retry fast-failing connects a few times and, when the database is
    genuinely unreachable, raise DatabaseUnavailable so the global AppError
    handler returns a clean 503 instead of leaking an asyncpg/socket traceback.
    """
    attempts = max(1, settings.DB_CONNECT_MAX_RETRIES + 1)
    last_exc: BaseException | None = None
    for attempt in range(attempts):
        try:
            await session.connection()
            return
        except (OSError, SQLAlchemyError) as exc:
            kind = _classify_connect_error(exc)
            if kind is None:
                raise  # not a connection error — let it bubble as a 500
            last_exc = exc
            await _safe_rollback(session)
            if kind == "retryable" and attempt + 1 < attempts:
                await asyncio.sleep(settings.DB_CONNECT_RETRY_BACKOFF_S * (2**attempt))
                continue
            raise DatabaseUnavailable() from exc
    raise DatabaseUnavailable() from last_exc  # pragma: no cover - loop always returns/raises


# Module-level singletons populated by main.py lifespan.
# Routes import `get_session` and inject it via Depends().
_session_factory: async_sessionmaker[AsyncSession] | None = None


def set_session_factory(factory: async_sessionmaker[AsyncSession]) -> None:
    """Called once from app lifespan to register the session factory."""
    global _session_factory
    _session_factory = factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield one AsyncSession per request."""
    if _session_factory is None:
        msg = "Session factory not initialised — call set_session_factory() in lifespan."
        raise RuntimeError(msg)
    async with _session_factory() as session:
        await ensure_session_connected(session)
        yield session
