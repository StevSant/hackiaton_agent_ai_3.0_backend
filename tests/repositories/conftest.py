"""Repository-test fixtures: provide an AsyncSession against the dev Postgres.

This fixture wraps each test in a transaction that is rolled back at the end so
tests stay independent. Requires the dev DB to be migrated (`alembic upgrade head`).
"""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings


@pytest.fixture
async def db_session() -> AsyncIterator:
    # statement_cache_size=0 is required when the DATABASE_URL points to
    # Supabase's pgbouncer pooler (port 6543, transaction mode).
    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await session.begin()
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()
    await engine.dispose()
