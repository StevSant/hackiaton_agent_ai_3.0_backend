"""RuleOverrideRecord — the persisted runtime state of one fraud rule."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RuleOverrideRecord:
    """One rule's persisted override state.

    ``thresholds`` is a partial overlay on the rule's ``config.yaml`` block
    (e.g. ``{"tier1_days": 7}``); empty when only the enabled flag was edited.
    """

    code: str
    enabled: bool = True
    thresholds: dict[str, Any] = field(default_factory=dict)
