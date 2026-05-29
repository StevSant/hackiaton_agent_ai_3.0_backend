"""assess_confidence — false-positive + vague-band + clean-case logic (A2)."""

from __future__ import annotations

from app.use_cases.assess_confidence import ConfidenceAssessment, assess_confidence


def test_high_ml_no_hard_rules_is_possible_false_positive() -> None:
    result = assess_confidence(score=20, rule_codes=["FS-03"], ml_probability=0.82)
    assert result == ConfidenceAssessment(posible_falso_positivo=True, confianza="baja")


def test_vague_band_score_is_medium_confidence() -> None:
    result = assess_confidence(score=42, rule_codes=["FS-01"], ml_probability=None)
    assert result == ConfidenceAssessment(posible_falso_positivo=True, confianza="media")


def test_clean_hard_rule_case_is_high_confidence() -> None:
    result = assess_confidence(score=88, rule_codes=["RF-01", "FS-14"], ml_probability=0.91)
    assert result == ConfidenceAssessment(posible_falso_positivo=False, confianza="alta")


def test_clean_low_risk_case_is_high_confidence() -> None:
    result = assess_confidence(score=12, rule_codes=[], ml_probability=0.08)
    assert result == ConfidenceAssessment(posible_falso_positivo=False, confianza="alta")


def test_hard_rule_overrides_vague_band() -> None:
    result = assess_confidence(score=40, rule_codes=["RF-04"], ml_probability=None)
    assert result == ConfidenceAssessment(posible_falso_positivo=False, confianza="alta")


def test_conflict_takes_precedence_over_vague_band() -> None:
    result = assess_confidence(score=45, rule_codes=["FS-02"], ml_probability=0.80)
    assert result == ConfidenceAssessment(posible_falso_positivo=True, confianza="baja")


def test_high_ml_high_rules_score_no_hard_rule_is_not_false_positive() -> None:
    # ML and the rules score AGREE (both high) → not a conflict → alta.
    result = assess_confidence(
        score=72, rule_codes=["FS-01", "FS-03", "FS-09"], ml_probability=0.82
    )
    assert result == ConfidenceAssessment(posible_falso_positivo=False, confianza="alta")


def test_vague_band_lower_boundary() -> None:
    assert assess_confidence(score=35, rule_codes=[], ml_probability=None).confianza == "media"


def test_vague_band_upper_boundary() -> None:
    assert assess_confidence(score=50, rule_codes=[], ml_probability=None).confianza == "media"


def test_just_below_vague_band_is_alta() -> None:
    assert assess_confidence(score=34, rule_codes=[], ml_probability=None).confianza == "alta"


def test_just_above_vague_band_is_alta() -> None:
    assert assess_confidence(score=51, rule_codes=[], ml_probability=None).confianza == "alta"
