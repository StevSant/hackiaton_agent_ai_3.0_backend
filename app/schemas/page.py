"""Generic pagination envelope — used by all list endpoints.

Contract per design spec §10:
    { items: T[], total: int, page: int, page_size: int }
Page index is 0-based; default page_size=25, max=500.

The cap was 100 originally — bumped to 500 in 2026-05-27 so the bandeja can
fetch the whole working set in one request (the analyst UI filters
client-side over the full list, and a 4×RTT page walk on every refresh was
the dominant time-to-first-render cost).
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

MAX_PAGE_SIZE = 500


class Page[T](BaseModel):
    items: list[T]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=0)
    page_size: int = Field(..., ge=1, le=MAX_PAGE_SIZE)
