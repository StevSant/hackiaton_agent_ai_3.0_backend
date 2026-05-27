"""Logging filter that silences asyncpg-terminate CancelledError noise.

asyncpg's `terminate()` awaits a graceful close under SQLAlchemy's greenlet
bridge. During uvicorn shutdown that await races with the cancellation of
in-flight request scopes — the cancel propagates into the asyncpg coroutine
and bubbles back out as an "Exception terminating connection" record from
the `sqlalchemy.pool.*` logger. The process is exiting; the noise carries
no actionable signal.

This filter drops only those records (sqlalchemy.pool logger + CancelledError
exc_info). Real connection failures (OSError, InterfaceError, etc.) still log.
"""

import asyncio
import logging


class SQLAlchemyPoolCancelFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not record.name.startswith("sqlalchemy.pool"):
            return True
        exc_info = record.exc_info
        if not exc_info or exc_info[0] is None:
            return True
        return not issubclass(exc_info[0], asyncio.CancelledError)
