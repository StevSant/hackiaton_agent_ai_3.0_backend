"""Unit tests for FS-18 — Concentración o colusión de proveedor."""

import pytest

from app.domain.rules.context import RuleContext
from app.domain.rules.signals.FS_18_provider_concentration import FS18ProviderConcentration
from tests.fixtures.claims import claim_verde, claim_amarillo


@pytest.fixture()
def rule() -> FS18ProviderConcentration:
    return FS18ProviderConcentration()


@pytest.fixture()
def base_ctx() -> RuleContext:
    return RuleContext.from_claim(claim_verde())


class TestFS18DoesNotFire:
    def test_no_provider_data(self, rule: FS18ProviderConcentration, base_ctx: RuleContext) -> None:
        """Both counts at zero → safe defaults → no fire."""
        base_ctx.pareja_proveedor_asegurado = 0
        base_ctx.proveedor_total_siniestros = 0
        assert rule.evaluate(claim_verde(), base_ctx) is None

    def test_pair_at_threshold_not_above(
        self, rule: FS18ProviderConcentration, base_ctx: RuleContext
    ) -> None:
        """Exactly at threshold (not above) → no fire."""
        base_ctx.pareja_proveedor_asegurado = 1  # threshold_pair = 1, must be > 1
        base_ctx.proveedor_total_siniestros = 0
        assert rule.evaluate(claim_verde(), base_ctx) is None

    def test_provider_at_threshold_not_above(
        self, rule: FS18ProviderConcentration, base_ctx: RuleContext
    ) -> None:
        base_ctx.pareja_proveedor_asegurado = 0
        base_ctx.proveedor_total_siniestros = 15  # threshold_provider = 15, must be > 15
        assert rule.evaluate(claim_verde(), base_ctx) is None


class TestFS18FiresPairSignal:
    def test_pair_above_threshold(
        self, rule: FS18ProviderConcentration, base_ctx: RuleContext
    ) -> None:
        base_ctx.pareja_proveedor_asegurado = 2  # > 1 → fires
        base_ctx.proveedor_total_siniestros = 0
        result = rule.evaluate(claim_verde(), base_ctx)
        assert result is not None
        assert result.code == "FS-18"
        assert result.points == 8  # points_pair from config
        assert result.evidence["pareja_proveedor_asegurado"] == 2

    def test_pair_signal_stronger_than_provider(
        self, rule: FS18ProviderConcentration, base_ctx: RuleContext
    ) -> None:
        """When both fire, the pair (collusion) signal wins."""
        base_ctx.pareja_proveedor_asegurado = 3
        base_ctx.proveedor_total_siniestros = 20
        result = rule.evaluate(claim_verde(), base_ctx)
        assert result is not None
        assert result.points == 8  # points_pair, not points_provider


class TestFS18FiresProviderSignal:
    def test_provider_over_concentration(
        self, rule: FS18ProviderConcentration, base_ctx: RuleContext
    ) -> None:
        base_ctx.pareja_proveedor_asegurado = 0
        base_ctx.proveedor_total_siniestros = 16  # > 15 → fires
        result = rule.evaluate(claim_verde(), base_ctx)
        assert result is not None
        assert result.code == "FS-18"
        assert result.points == 4  # points_provider from config

    def test_evidence_shape(
        self, rule: FS18ProviderConcentration, base_ctx: RuleContext
    ) -> None:
        base_ctx.pareja_proveedor_asegurado = 0
        base_ctx.proveedor_total_siniestros = 20
        result = rule.evaluate(claim_verde(), base_ctx)
        assert result is not None
        assert "proveedor_total_siniestros" in result.evidence
        assert "pareja_proveedor_asegurado" in result.evidence
