"""Tiny dependency for setting `Cache-Control` on read-only GET responses.

Usage:

    @router.get("/foo", dependencies=[Depends(cache_for(60))])
    async def foo(): ...

Emits ``Cache-Control: private, max-age=N, stale-while-revalidate=N*5`` so the
browser caches per-user (won't leak across sessions) and the next nav can serve
instantly while a background revalidate hits the server.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Response


def cache_for(seconds: int) -> Callable[[Response], None]:
    """Return a FastAPI dependency that sets a private Cache-Control header.

    ``seconds`` is the freshness window; SWR is 5x to keep paint instant on
    repeat navigation while data refreshes silently.
    """

    def _set_cache_header(response: Response) -> None:
        response.headers["Cache-Control"] = (
            f"private, max-age={seconds}, stale-while-revalidate={seconds * 5}"
        )

    return _set_cache_header
