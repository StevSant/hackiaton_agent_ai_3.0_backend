"""Unit tests for FS-16 — Robo sin parte policial."""

import pytest

from app.domain.rules.context import RuleContext
from app.domain.rules.signals.FS_16_theft_without_police_report import FS16TheftWithoutPoliceReport
from tests.fixtures.claims import claim_verde, claim_rojo


@pytest.fixture()
def rule() -> FS16TheftWithoutPoliceReport:
    return FS16TheftWithoutPoliceReport()


class TestFS16DoesNotFire:
    def test_non_theft_claim_ignored(self, rule: FS16TheftWithoutPoliceReport) -> None:
        """No theft coverage → rule never fires regardless of police report status."""
        claim = claim_verde()  # cobertura = Responsabilidad Civil
        ctx = RuleContext.from_claim(claim)
        ctx.tiene_parte_policial = False  # even if missing, must not fire for non-theft
        assert rule.evaluate(claim, ctx) is None

    def test_theft_with_police_report_no_fire(self, rule: FS16TheftWithoutPoliceReport) -> None:
        """Theft claim with a valid police report number → safe."""
        claim = claim_rojo()  # cobertura = Pérdida Total por Robo
        ctx = RuleContext.from_claim(claim)
        ctx.tiene_parte_policial = True
        assert rule.evaluate(claim, ctx) is None


class TestFS16Fires:
    def test_theft_without_police_report(self, rule: FS16TheftWithoutPoliceReport) -> None:
        """Theft claim with no police report → FS-16 must fire."""
        claim = claim_rojo()
        ctx = RuleContext.from_claim(claim)
        ctx.tiene_parte_policial = False  # no part policial on file

        result = rule.evaluate(claim, ctx)
        assert result is not None
        assert result.code == "FS-16"
        assert result.points > 0
        assert result.tier_hint.value == "amarillo"
        assert result.evidence["tiene_parte_policial"] is False

    def test_evidence_shape(self, rule: FS16TheftWithoutPoliceReport) -> None:
        claim = claim_rojo()
        ctx = RuleContext.from_claim(claim)
        ctx.tiene_parte_policial = False

        result = rule.evaluate(claim, ctx)
        assert result is not None
        assert "es_robo" in result.evidence
        assert result.evidence["es_robo"] is True
