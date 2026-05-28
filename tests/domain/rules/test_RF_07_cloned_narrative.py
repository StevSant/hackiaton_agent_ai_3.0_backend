"""Unit tests for RF-07 — cloned narrative hard rule.

Key invariant: RF-07 fires only when narrativa_similar_score >= 0.98
(config.yaml RF_07.threshold_similarity). FS-13 similarity range
(0.70–0.97) must NOT trigger it.
"""

import pytest

from app.domain.rules.context import RuleContext
from app.domain.rules.hard.RF_07_cloned_narrative import RF07ClonedNarrative
from tests.fixtures.claims import claim_verde


@pytest.fixture()
def rule() -> RF07ClonedNarrative:
    return RF07ClonedNarrative()


@pytest.fixture()
def base_ctx() -> RuleContext:
    return RuleContext.from_claim(claim_verde())


class TestRF07DoesNotFireBelowThreshold:
    def test_no_similarity(self, rule: RF07ClonedNarrative, base_ctx: RuleContext) -> None:
        base_ctx.narrativa_similar_score = 0.0
        base_ctx.narrativa_clonada = False
        assert rule.evaluate(claim_verde(), base_ctx) is None

    def test_fs13_range_high_end_does_not_fire(
        self, rule: RF07ClonedNarrative, base_ctx: RuleContext
    ) -> None:
        """sim=0.901 is in FS-13 territory — RF-07 must NOT fire."""
        base_ctx.narrativa_similar_score = 0.901
        base_ctx.narrativa_clonada = False
        assert rule.evaluate(claim_verde(), base_ctx) is None

    def test_just_below_threshold(
        self, rule: RF07ClonedNarrative, base_ctx: RuleContext
    ) -> None:
        base_ctx.narrativa_similar_score = 0.979
        base_ctx.narrativa_clonada = False
        assert rule.evaluate(claim_verde(), base_ctx) is None


class TestRF07FiresAtThreshold:
    def test_exactly_at_threshold(
        self, rule: RF07ClonedNarrative, base_ctx: RuleContext
    ) -> None:
        base_ctx.narrativa_similar_score = 0.98
        base_ctx.narrativa_clonada = True
        result = rule.evaluate(claim_verde(), base_ctx)
        assert result is not None
        assert result.code == "RF-07"
        assert result.tier_hint.value == "amarillo"

    def test_above_threshold(self, rule: RF07ClonedNarrative, base_ctx: RuleContext) -> None:
        base_ctx.narrativa_similar_score = 0.99
        base_ctx.narrativa_clonada = True
        result = rule.evaluate(claim_verde(), base_ctx)
        assert result is not None
        assert result.code == "RF-07"

    def test_narrativa_clonada_flag_alone_triggers(
        self, rule: RF07ClonedNarrative, base_ctx: RuleContext
    ) -> None:
        """If the similarity layer sets narrativa_clonada=True directly, rule fires
        regardless of narrativa_similar_score value (belt-and-suspenders path)."""
        base_ctx.narrativa_similar_score = 0.0
        base_ctx.narrativa_clonada = True
        result = rule.evaluate(claim_verde(), base_ctx)
        assert result is not None
        assert result.code == "RF-07"
