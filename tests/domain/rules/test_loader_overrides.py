"""Unit tests for the rules-engine override overlay in domain.rules.loader.

The loader holds runtime override state (paused rules + threshold overlays) that
infrastructure hydrates from the DB. These tests pin the merge + enable semantics
without any DB. The module state is global, so every test resets it.
"""

from __future__ import annotations

import pytest

from app.domain.rules.defaults import DEFAULT_DISABLED_CODES
from app.domain.rules.loader import (
    apply_overrides,
    disabled_codes,
    numeric_thresholds,
    reset_overrides,
    rule_cfg,
    rule_enabled,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_overrides()
    yield
    reset_overrides()


class TestDefaults:
    def test_fs14_paused_by_default(self) -> None:
        assert "FS-14" in DEFAULT_DISABLED_CODES
        assert rule_enabled("FS-14") is False

    def test_other_rules_enabled_by_default(self) -> None:
        assert rule_enabled("FS-01") is True


class TestEnableOverlay:
    def test_apply_pauses_a_rule(self) -> None:
        apply_overrides({"FS-01"}, {})
        assert rule_enabled("FS-01") is False
        assert disabled_codes() == {"FS-01"}

    def test_apply_can_reenable_a_default_disabled_rule(self) -> None:
        # An empty disabled-set means FS-14 is no longer paused.
        apply_overrides(set(), {})
        assert rule_enabled("FS-14") is True

    def test_reset_restores_defaults(self) -> None:
        apply_overrides({"FS-01"}, {})
        reset_overrides()
        assert rule_enabled("FS-01") is True
        assert rule_enabled("FS-14") is False


class TestThresholdOverlay:
    def test_override_merges_onto_base(self) -> None:
        base = rule_cfg("FS_01")["tier1_days"]
        assert base == 10  # config.yaml default
        apply_overrides(set(), {"FS_01": {"tier1_days": 7}})
        merged = rule_cfg("FS_01")
        assert merged["tier1_days"] == 7
        # Untouched keys keep their defaults.
        assert merged["tier1_points"] == 8

    def test_numeric_thresholds_reflects_override(self) -> None:
        apply_overrides(set(), {"FS_01": {"tier1_days": 7}})
        assert numeric_thresholds("FS_01")["tier1_days"] == 7.0

    def test_numeric_thresholds_excludes_non_numeric_and_missing(self) -> None:
        # RF-02 has no config block → no tunable thresholds.
        assert numeric_thresholds("RF_02") == {}
        # RF-01 only carries a coverage list → no numeric thresholds.
        assert numeric_thresholds("RF_01") == {}
