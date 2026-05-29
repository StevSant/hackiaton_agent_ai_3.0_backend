"""Wire shape of the background rescore job (POST /rules/rescore + status poll)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class RescoreStatusOut(BaseModel):
    status: Literal["idle", "running", "done", "error"]
    processed: int
    total: int
    changed: int
    error: str | None = None
