"""Unit tests for FS-17 — Siniestro cerca del fin de la póliza."""

import pytest

from app.domain.rules.context import RuleContext
from app.domain.rules.signals.FS_17_claim_near_policy_end import FS17ClaimNearPolicyEnd
from tests.fixtures.claims import claim_verde


@pytest.fixture()
def rule() -> FS17ClaimNearPolicyEnd:
    return FS17ClaimNearPolicyEnd()


@pytest.fixture()
def base_ctx() -> RuleContext:
    return RuleContext.from_claim(claim_verde())


class TestFS17DoesNotFire:
    def test_far_from_policy_end(self, rule: FS17ClaimNearPolicyEnd, base_ctx: RuleContext) -> None:
        base_ctx.dias_desde_fin_poliza = 90
        assert rule.evaluate(claim_verde(), base_ctx) is None

    def test_exactly_31_days(self, rule: FS17ClaimNearPolicyEnd, base_ctx: RuleContext) -> None:
        base_ctx.dias_desde_fin_poliza = 31
        assert rule.evaluate(claim_verde(), base_ctx) is None

    def test_default_9999_safe(self, rule: FS17ClaimNearPolicyEnd, base_ctx: RuleContext) -> None:
        """Unknown end date → default 9999 → must not fire."""
        base_ctx.dias_desde_fin_poliza = 9999
        assert rule.evaluate(claim_verde(), base_ctx) is None

    def test_negative_days_no_fire(self, rule: FS17ClaimNearPolicyEnd, base_ctx: RuleContext) -> None:
        """Occurrence after policy end (expired) → skip, not a proximity risk."""
        base_ctx.dias_desde_fin_poliza = -5
        assert rule.evaluate(claim_verde(), base_ctx) is None


class TestFS17Fires:
    def test_high_band_10_days(self, rule: FS17ClaimNearPolicyEnd, base_ctx: RuleContext) -> None:
        base_ctx.dias_desde_fin_poliza = 10
        result = rule.evaluate(claim_verde(), base_ctx)
        assert result is not None
        assert result.code == "FS-17"
        assert result.points == 8  # points_high from config

    def test_high_band_0_days(self, rule: FS17ClaimNearPolicyEnd, base_ctx: RuleContext) -> None:
        """Occurrence on the last day of coverage → high band."""
        base_ctx.dias_desde_fin_poliza = 0
        result = rule.evaluate(claim_verde(), base_ctx)
        assert result is not None
        assert result.points == 8

    def test_mid_band_20_days(self, rule: FS17ClaimNearPolicyEnd, base_ctx: RuleContext) -> None:
        base_ctx.dias_desde_fin_poliza = 20
        result = rule.evaluate(claim_verde(), base_ctx)
        assert result is not None
        assert result.code == "FS-17"
        assert result.points == 4  # points_mid from config

    def test_mid_band_exactly_30(self, rule: FS17ClaimNearPolicyEnd, base_ctx: RuleContext) -> None:
        """30 days is still within the mid band (threshold_days_mid = 30)."""
        base_ctx.dias_desde_fin_poliza = 30
        result = rule.evaluate(claim_verde(), base_ctx)
        assert result is not None
        assert result.points == 4

    def test_evidence_contains_days(self, rule: FS17ClaimNearPolicyEnd, base_ctx: RuleContext) -> None:
        base_ctx.dias_desde_fin_poliza = 7
        result = rule.evaluate(claim_verde(), base_ctx)
        assert result is not None
        assert result.evidence["dias_desde_fin_poliza"] == 7
