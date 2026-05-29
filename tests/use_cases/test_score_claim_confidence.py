"""score_claim populates the A2 confidence fields (rules-only, ml unknown)."""

from __future__ import annotations

from tests.fixtures.claims import claim_amarillo, claim_rojo, claim_verde
from app.use_cases.score_claim import score_claim


def test_score_claim_sets_confidence_fields_present() -> None:
    score = score_claim(claim_verde())
    assert score.posible_falso_positivo is False
    assert score.confianza == "alta"


def test_score_claim_rojo_hard_rule_is_high_confidence() -> None:
    score = score_claim(claim_rojo())
    assert score.posible_falso_positivo is False
    assert score.confianza == "alta"
