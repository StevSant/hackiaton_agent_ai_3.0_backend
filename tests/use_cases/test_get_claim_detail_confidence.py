"""get_claim_detail re-assesses confidence with the ML probability (A2)."""

from __future__ import annotations

import pytest

from app.domain.ml.types import MLPrediction
from app.schemas.risk import FactorContribution
from app.use_cases.claim_queries import InMemoryClaimQueries
from app.use_cases.get_claim_detail import get_claim_detail
from tests.fixtures.claims import claim_verde


class _HighProbClassifier:
    async def predict(self, features: dict[str, float]) -> MLPrediction:
        return MLPrediction(
            probability=0.92,
            factors=[FactorContribution(feature="monto_reclamado", shap_value=0.5, direction="up")],
        )


@pytest.mark.asyncio
async def test_high_ml_clean_rules_flags_possible_false_positive() -> None:
    queries = InMemoryClaimQueries(claims=[claim_verde()])
    detail = await get_claim_detail(
        queries, "SIN-0001", classifier=_HighProbClassifier(), detector=None
    )
    assert detail is not None
    assert detail.ml_probability == pytest.approx(0.92)
    assert detail.posible_falso_positivo is True
    assert detail.confianza == "baja"


@pytest.mark.asyncio
async def test_no_ml_clean_claim_stays_high_confidence() -> None:
    queries = InMemoryClaimQueries(claims=[claim_verde()])
    detail = await get_claim_detail(queries, "SIN-0001", classifier=None, detector=None)
    assert detail is not None
    assert detail.posible_falso_positivo is False
    assert detail.confianza == "alta"
