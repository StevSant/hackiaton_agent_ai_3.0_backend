"""Ports for the rules engine: FraudRule Protocol + RuleMeta catalog descriptor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.domain.rules.context import RuleContext
    from app.schemas.claim import ClaimDetail
    from app.schemas.risk import RuleActivation, Tier


@dataclass(frozen=True)
class RuleMeta:
    """Static catalog entry for one fraud rule.

    Used by the catalog endpoint (L4) and agent tool responses.
    Descriptions must never contain the word "fraude" — use "posible fraude" / "alerta".
    """

    code: str                  # e.g. "FS-07", "RF-01"
    name: str                  # short human name (Spanish)
    tier_hint: Tier          # default tier when this rule fires
    short_description: str     # one sentence explaining what it detects (for UI)
    what_triggers: str         # condition that makes the rule fire (for UI)
    max_points: int            # 0 for hard rules


@runtime_checkable
class FraudRule(Protocol):
    """Single-responsibility fraud signal or hard rule.

    Each FS-NN / RF-NN rule is its own file and provides:
    - A module-level ``META: RuleMeta`` constant.
    - A class/function implementing this protocol.
    """

    META: RuleMeta  # class-level constant

    def evaluate(
        self,
        claim: ClaimDetail,
        ctx: RuleContext,
    ) -> RuleActivation | None:
        """Return a RuleActivation when the rule fires, None otherwise."""
        ...
