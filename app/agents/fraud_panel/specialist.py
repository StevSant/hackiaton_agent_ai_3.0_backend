"""Specialist definition — one analyst persona on the fraud panel."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.schemas.claim import ClaimDetail


@dataclass(frozen=True, slots=True)
class Specialist:
    """A panel specialist: identity + prompt + the claim slice it reasons over."""

    id: str
    display_name: str
    lens: str
    prompt_id: str
    slice_fn: Callable[[ClaimDetail], dict[str, Any]]
