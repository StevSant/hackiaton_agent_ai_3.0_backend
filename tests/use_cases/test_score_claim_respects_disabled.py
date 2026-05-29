"""score_claim must skip rules paused via the loader override overlay.

This is the end-to-end guarantee behind the dashboard pause toggle: disabling a
rule genuinely removes its contribution from the engine score (not just a
cosmetic flag). The loader state is global, so every test resets it.
"""

from __future__ import annotations

import pytest

from app.domain.rules.context import RuleContext
from app.domain.rules.loader import apply_overrides, reset_overrides
from app.use_cases.score_claim import score_claim
from tests.fixtures.claims import claim_verde


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_overrides()
    yield
    reset_overrides()


def _ctx_firing_fs01() -> RuleContext:
    # 5 days from policy start → FS-01 tier1 fires for 8 points.
    return RuleContext(dias_desde_inicio_poliza=5)


class TestDisabledRuleSkipped:
    def test_fs01_fires_when_enabled(self) -> None:
        score = score_claim(claim_verde(), ctx=_ctx_firing_fs01())
        codes = {a.code for a in score.activations}
        assert "FS-01" in codes
        assert score.score >= 8

    def test_fs01_skipped_when_paused(self) -> None:
        apply_overrides({"FS-01"}, {})
        score = score_claim(claim_verde(), ctx=_ctx_firing_fs01())
        codes = {a.code for a in score.activations}
        assert "FS-01" not in codes


class TestThresholdOverrideChangesScore:
    def test_tightening_fs01_window_stops_firing(self) -> None:
        # Occurrence at day 9 fires under the default 10-day window...
        ctx = RuleContext(dias_desde_inicio_poliza=9)
        assert "FS-01" in {a.code for a in score_claim(claim_verde(), ctx=ctx).activations}
        # ...but not after tightening tier1_days to 7 (and tier2_days to 7).
        apply_overrides(set(), {"FS_01": {"tier1_days": 7, "tier2_days": 7}})
        assert "FS-01" not in {a.code for a in score_claim(claim_verde(), ctx=ctx).activations}
