"""enrich_claim_score — happy path with fakes + no-op pass-through path."""

from __future__ import annotations

import pytest

from app.domain.anomaly.types import AnomalyResult
from app.domain.ml.types import MLPrediction
from app.schemas.risk import FactorContribution
from app.use_cases.enrich_claim_score import enrich_claim_score
from tests.fixtures.claims import claim_amarillo


class _FakeClassifier:
    """Returns a fixed prediction; ignores features."""

    async def predict(self, features: dict[str, float]) -> MLPrediction:
        return MLPrediction(
            probability=0.73,
            factors=[
                FactorContribution(
                    feature="monto_reclamado", shap_value=0.42, direction="up"
                ),
                FactorContribution(
                    feature="dias_entre_ocurrencia_reporte",
                    shap_value=-0.18,
                    direction="down",
                ),
            ],
        )


class _FakeDetector:
    async def score(self, features: dict[str, float]) -> AnomalyResult:
        return AnomalyResult(score=-0.27, nearest_normal_claim_id="SIN-0001")


@pytest.mark.asyncio
async def test_enrich_with_both_ports_populates_all_fields() -> None:
    claim = claim_amarillo()
    enriched = await enrich_claim_score(
        claim, classifier=_FakeClassifier(), detector=_FakeDetector()
    )

    assert enriched.ml_probability == pytest.approx(0.73)
    assert len(enriched.ml_factors) == 2
    assert enriched.ml_factors[0].feature == "monto_reclamado"
    assert enriched.anomaly_score == pytest.approx(-0.27)
    assert enriched.nearest_normal_claim_id == "SIN-0001"


@pytest.mark.asyncio
async def test_enrich_with_only_classifier_leaves_anomaly_unset() -> None:
    claim = claim_amarillo()
    enriched = await enrich_claim_score(claim, classifier=_FakeClassifier(), detector=None)
    assert enriched.ml_probability == pytest.approx(0.73)
    assert enriched.anomaly_score is None
    assert enriched.nearest_normal_claim_id is None


@pytest.mark.asyncio
async def test_enrich_with_only_detector_leaves_ml_unset() -> None:
    claim = claim_amarillo()
    enriched = await enrich_claim_score(claim, classifier=None, detector=_FakeDetector())
    assert enriched.ml_probability is None
    assert enriched.ml_factors == []
    assert enriched.anomaly_score == pytest.approx(-0.27)


@pytest.mark.asyncio
async def test_enrich_with_no_ports_passes_through_unchanged() -> None:
    claim = claim_amarillo()
    enriched = await enrich_claim_score(claim, classifier=None, detector=None)
    assert enriched is claim
