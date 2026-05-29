"""assess_confidence — confidence + possible-false-positive signalling (A2).

Pure, deterministic. Fed by data already present on a scored claim: the
additive rules score, the fired rule codes, and (optionally) the ML
probability. It NEVER accuses — it raises a "posible falso positivo" review
flag and lowers confidence when the signals disagree, so the analyst looks
harder (challenge spec §2.10: AI is an alert, the human decides).

Decision order (first match wins):
  1. Conflict — the model flags high risk but NO hard rule (RF-*) corroborates
     it → possible false positive, confianza "baja". Covers both "high ML vs.
     low rules" and "low rules score as a standalone signal worth a second look".
  2. Vague band — the additive score straddles the verde/amarillo boundary and
     no hard rule fired → ambiguous, confianza "media".
  3. Otherwise — signals agree (hard rule corroborates, or everything is clearly
     low) → confianza "alta", no flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from app.core.config import settings

if TYPE_CHECKING:
    from app.schemas.claim import ClaimDetail

Confianza = Literal["alta", "media", "baja"]


@dataclass(frozen=True, slots=True)
class ConfidenceAssessment:
    """Result of the confidence/false-positive evaluation for one claim."""

    posible_falso_positivo: bool
    confianza: Confianza


def _has_hard_rule(rule_codes: list[str]) -> bool:
    """True when any critical hard rule (RF-*) fired — that corroborates the alert."""
    return any(code.upper().startswith("RF-") for code in rule_codes)


def assess_confidence(
    *,
    score: int,
    rule_codes: list[str],
    ml_probability: float | None,
) -> ConfidenceAssessment:
    """Evaluate signal agreement → (posible_falso_positivo, confianza).

    Args:
        score: Additive rules score [0, 100].
        rule_codes: Codes of the rules that fired (e.g. ["FS-01", "RF-04"]).
        ml_probability: Supervised model probability [0, 1], or None if unwired.
    """
    hard_rule = _has_hard_rule(rule_codes)

    # 1. Conflict — model says high risk, nothing hard corroborates it.
    if (
        ml_probability is not None
        and ml_probability >= settings.CONFIDENCE_ML_HIGH
        and not hard_rule
    ):
        return ConfidenceAssessment(posible_falso_positivo=True, confianza="baja")

    # 2. Vague band — additive score straddles the verde/amarillo boundary.
    if (
        not hard_rule
        and settings.CONFIDENCE_VAGUE_BAND_LOW <= score <= settings.CONFIDENCE_VAGUE_BAND_HIGH
    ):
        return ConfidenceAssessment(posible_falso_positivo=True, confianza="media")

    # 3. Signals agree.
    return ConfidenceAssessment(posible_falso_positivo=False, confianza="alta")


def apply_confidence(detail: "ClaimDetail") -> "ClaimDetail":
    """Return *detail* with A2 confidence fields set from its current signals.

    Uses the post-enrichment data on the claim: the additive ``score``, the
    fired rule codes (``alertas[*].code``), and ``ml_probability``. Safe to call
    in any path that produces a finalized ``ClaimDetail``.
    """
    assessment = assess_confidence(
        score=detail.score,
        rule_codes=[a.code for a in detail.alertas],
        ml_probability=detail.ml_probability,
    )
    return detail.model_copy(
        update={
            "posible_falso_positivo": assessment.posible_falso_positivo,
            "confianza": assessment.confianza,
        }
    )
