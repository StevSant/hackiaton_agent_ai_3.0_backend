"""Classify exceptions that mean the DB connection died mid-operation.

`pool_pre_ping` only protects connections at *checkout*; the Supabase pooler
can still reset a connection while a request holds it (maintenance restarts,
session-mode reshuffles). Those surface as a SQLAlchemy `DBAPIError` wrapping
asyncpg's 08xxx connection family or a raw TCP reset.
"""

from __future__ import annotations

from asyncpg.exceptions import PostgresConnectionError
from sqlalchemy.exc import DBAPIError


def is_disconnect_error(exc: BaseException) -> bool:
    """True when the exception chain points at a dropped DB connection.

    A bare `ConnectionError` only counts when a `DBAPIError` is also in the
    chain — otherwise an httpx/LLM connect failure would be misclassified as
    a database outage.
    """
    seen: set[int] = set()
    nodes: list[BaseException] = []
    cursor: BaseException | None = exc
    while cursor is not None and id(cursor) not in seen:
        seen.add(id(cursor))
        nodes.append(cursor)
        # SQLAlchemy keeps the driver error on .orig — inspect it too.
        orig = getattr(cursor, "orig", None)
        if isinstance(orig, BaseException) and id(orig) not in seen:
            seen.add(id(orig))
            nodes.append(orig)
        cursor = cursor.__cause__ or cursor.__context__

    has_dbapi = any(isinstance(n, DBAPIError) for n in nodes)
    for node in nodes:
        if isinstance(node, DBAPIError) and node.connection_invalidated:
            return True
        if isinstance(node, PostgresConnectionError):
            return True
        if isinstance(node, ConnectionError) and has_dbapi:
            return True
    return False
