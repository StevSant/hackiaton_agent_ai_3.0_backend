"""Generic pagination envelope — used by all list endpoints.

Contract per design spec §10:
    { items: T[], total: int, page: int, page_size: int }
Page index is 0-based; default page_size=25, max=100.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page[T](BaseModel):
    items: list[T]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=0)
    page_size: int = Field(..., ge=1, le=100)
