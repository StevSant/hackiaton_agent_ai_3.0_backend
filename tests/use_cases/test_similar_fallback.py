"""Unit tests for the "Narrativas similares" read-time fallback.

The panel reads ``ClaimDetail.similar``. ``_attach_similar_fallback`` backfills
it from the live similarity engine when the persisted list is empty, so a claim
whose neighbours were never persisted (imported before the fix, or scored via a
path without a similarity port) still shows genuine matches on the detail page.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.core.config import settings
from app.schemas.claim import ClaimDetail, ClaimReview
from app.schemas.risk import SimilarClaim, Tier
from app.use_cases.get_claim_detail import _attach_similar_fallback


class _FakeSimilarity:
    """NarrativeSimilarity stub returning a canned neighbour list."""

    def __init__(self, neighbours: list[SimilarClaim]) -> None:
        self._neighbours = neighbours
        self.calls = 0

    async def index(self, claim_id: str, descripcion: str) -> None:  # pragma: no cover
        raise AssertionError("index must not be called from the read path")

    async def nearest(self, claim_id: str, top_k: int = 3) -> list[SimilarClaim]:
        self.calls += 1
        return self._neighbours[:top_k]

    async def max_similarity(self, claim_id: str) -> float:  # pragma: no cover
        return self._neighbours[0].similarity if self._neighbours else 0.0


def _claim(
    *,
    similar: list[SimilarClaim] | None = None,
    descripcion: str | None = None,
) -> ClaimDetail:
    return ClaimDetail(
        id="SIN-FB-001",
        ramo="Vehículos",
        cobertura="Responsabilidad Civil",
        asegurado="Prueba",
        asegurado_id="ASE-FB-001",
        poliza="POL-FB-001",
        ciudad="Guayaquil",
        fecha_ocurrencia=date(2026, 3, 1),
        fecha_reporte=date(2026, 3, 5),
        monto_reclamado=1500.0,
        suma_asegurada=20000.0,
        estado="Reserva",
        sucursal="Guayaquil Centro",
        descripcion="Colisión por alcance en avenida principal con daños moderados."
        if descripcion is None
        else descripcion,
        score=20,
        nivel=Tier.verde,
        review=ClaimReview(),
        similar=similar or [],
    )


@pytest.mark.asyncio
async def test_backfills_when_empty() -> None:
    """Empty persisted list + engine matches above the floor → list is backfilled."""
    neighbours = [
        SimilarClaim(claim_id="SIN-X", similarity=0.91, snippet="Narrativa muy parecida."),
        SimilarClaim(claim_id="SIN-Y", similarity=0.60, snippet="Narrativa algo parecida."),
    ]
    fake = _FakeSimilarity(neighbours)

    result = await _attach_similar_fallback(_claim(similar=[]), fake)

    assert fake.calls == 1
    assert [s.claim_id for s in result.similar] == ["SIN-X", "SIN-Y"]


@pytest.mark.asyncio
async def test_does_not_overwrite_existing() -> None:
    """A non-empty persisted list is authoritative — the engine is never queried."""
    existing = [SimilarClaim(claim_id="SIN-KEEP", similarity=0.88, snippet="Ya persistido.")]
    fake = _FakeSimilarity(
        [SimilarClaim(claim_id="SIN-OTHER", similarity=0.95, snippet="No usar.")]
    )

    result = await _attach_similar_fallback(_claim(similar=existing), fake)

    assert fake.calls == 0
    assert [s.claim_id for s in result.similar] == ["SIN-KEEP"]


@pytest.mark.asyncio
async def test_filters_below_display_floor() -> None:
    """Neighbours below SIMILARITY_DISPLAY_MIN are noise and must not surface."""
    low = settings.SIMILARITY_DISPLAY_MIN - 0.1
    fake = _FakeSimilarity(
        [SimilarClaim(claim_id="SIN-LOW", similarity=low, snippet="Demasiado lejana.")]
    )

    result = await _attach_similar_fallback(_claim(similar=[]), fake)

    assert result.similar == []


@pytest.mark.asyncio
async def test_no_similarity_port_is_noop() -> None:
    """Without a similarity port the claim is returned untouched."""
    result = await _attach_similar_fallback(_claim(similar=[]), None)
    assert result.similar == []


@pytest.mark.asyncio
async def test_short_narrative_skipped() -> None:
    """Narratives too short to embed meaningfully don't trigger a lookup."""
    fake = _FakeSimilarity(
        [SimilarClaim(claim_id="SIN-X", similarity=0.99, snippet="Irrelevante.")]
    )
    result = await _attach_similar_fallback(_claim(similar=[], descripcion="Choque."), fake)
    assert fake.calls == 0
    assert result.similar == []
