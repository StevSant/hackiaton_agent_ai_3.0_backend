"""Unit tests for FS-19 — Perfil de riesgo alto del asegurado."""

import pytest

from app.domain.rules.context import RuleContext
from app.domain.rules.signals.FS_19_high_risk_profile import FS19HighRiskProfile
from tests.fixtures.claims import claim_verde


@pytest.fixture()
def rule() -> FS19HighRiskProfile:
    return FS19HighRiskProfile()


@pytest.fixture()
def base_ctx() -> RuleContext:
    return RuleContext.from_claim(claim_verde())


class TestFS19DoesNotFire:
    def test_no_profile(self, rule: FS19HighRiskProfile, base_ctx: RuleContext) -> None:
        base_ctx.perfil_riesgo = None
        assert rule.evaluate(claim_verde(), base_ctx) is None

    def test_medium_profile(self, rule: FS19HighRiskProfile, base_ctx: RuleContext) -> None:
        base_ctx.perfil_riesgo = "Medio"
        assert rule.evaluate(claim_verde(), base_ctx) is None

    def test_low_profile(self, rule: FS19HighRiskProfile, base_ctx: RuleContext) -> None:
        base_ctx.perfil_riesgo = "Bajo"
        assert rule.evaluate(claim_verde(), base_ctx) is None

    def test_empty_string_profile(self, rule: FS19HighRiskProfile, base_ctx: RuleContext) -> None:
        base_ctx.perfil_riesgo = ""
        assert rule.evaluate(claim_verde(), base_ctx) is None


class TestFS19Fires:
    def test_alto_exact(self, rule: FS19HighRiskProfile, base_ctx: RuleContext) -> None:
        base_ctx.perfil_riesgo = "Alto"
        result = rule.evaluate(claim_verde(), base_ctx)
        assert result is not None
        assert result.code == "FS-19"
        assert result.points == 3  # config FS_19.points
        assert result.tier_hint.value == "amarillo"

    def test_alto_lowercase(self, rule: FS19HighRiskProfile, base_ctx: RuleContext) -> None:
        """Case-insensitive match."""
        base_ctx.perfil_riesgo = "alto"
        result = rule.evaluate(claim_verde(), base_ctx)
        assert result is not None

    def test_alto_mixed_case(self, rule: FS19HighRiskProfile, base_ctx: RuleContext) -> None:
        base_ctx.perfil_riesgo = "ALTO"
        result = rule.evaluate(claim_verde(), base_ctx)
        assert result is not None

    def test_alto_in_phrase(self, rule: FS19HighRiskProfile, base_ctx: RuleContext) -> None:
        """'alto' as substring of a longer profile string."""
        base_ctx.perfil_riesgo = "Riesgo alto confirmado"
        result = rule.evaluate(claim_verde(), base_ctx)
        assert result is not None

    def test_evidence_contains_profile(self, rule: FS19HighRiskProfile, base_ctx: RuleContext) -> None:
        base_ctx.perfil_riesgo = "Alto"
        result = rule.evaluate(claim_verde(), base_ctx)
        assert result is not None
        assert result.evidence["perfil_riesgo"] == "Alto"
