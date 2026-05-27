"""SQLAlchemy 2.0 async engine, session factory, and FastAPI session dependency.

The engine and session_factory are created once at app startup (lifespan) and
stored on app.state.  The `get_session` dependency yields an AsyncSession per
request; routes never touch the engine directly.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def create_engine() -> AsyncEngine:
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.APP_ENV == "dev" and settings.LOG_LEVEL == "DEBUG",
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


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
        yield session
