from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import cast

import pytest

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.domain.reviews.state_machine import apply_dictamen
from app.infrastructure.reviews.in_memory_reviews_store import InMemoryReviewsStore
from app.schemas.claim import ClaimDetail, ClaimReview, DictamenOutcome, ReviewStatus
from app.schemas.risk import Tier
from app.use_cases.reviews.list_historico import list_antifraude_historico


def test_requiere_mas_info_keeps_dictamen_metadata_for_history() -> None:
    review = ClaimReview(status=ReviewStatus.escalado)

    updated = apply_dictamen(
        review,
        by_id="antifraude-1",
        by_name="Lucía Vélez",
        outcome=DictamenOutcome.requiere_mas_info,
        justificacion="Faltan fotografías del daño y declaración ampliada del conductor.",
    )

    assert updated.status == ReviewStatus.pendiente
    assert updated.dictamen_outcome == DictamenOutcome.requiere_mas_info
    assert updated.dictamen_justificacion is not None
    assert updated.dictaminado_by == "antifraude-1"
    assert updated.dictaminado_at is not None
    assert updated.bounce_count == 1


@pytest.mark.asyncio
async def test_antifraude_historico_includes_all_outcomes_sorted_by_dictamen_date() -> None:
    store = InMemoryReviewsStore()
    queries = _FakeClaimQueries()
    older_dictamen_at = datetime(2026, 5, 29, 14, 0, tzinfo=UTC)
    latest_dictamen_at = older_dictamen_at + timedelta(minutes=10)

    await store.save(
        "SIN-OLDER",
        ClaimReview(
            status=ReviewStatus.dictaminado,
            dictamen_outcome=DictamenOutcome.confirmado_sospecha,
            dictamen_justificacion="La evidencia documental sostiene una alerta para revisión.",
            dictaminado_by="antifraude-1",
            dictaminado_at=older_dictamen_at,
        ),
    )
    await store.save(
        "SIN-LATEST",
        ClaimReview(
            status=ReviewStatus.pendiente,
            dictamen_outcome=DictamenOutcome.requiere_mas_info,
            dictamen_justificacion="Falta documentación clave para continuar el análisis.",
            dictaminado_by="antifraude-1",
            dictaminado_at=latest_dictamen_at,
            bounce_count=1,
        ),
    )

    page = await list_antifraude_historico(
        store, cast(ClaimQueries, queries), user_id="antifraude-1", page=0, page_size=10
    )

    assert [row.id for row in page.items] == ["SIN-LATEST", "SIN-OLDER"]
    assert page.items[0].dictamen_outcome == DictamenOutcome.requiere_mas_info
    assert page.items[0].dictaminado_at == latest_dictamen_at


class _FakeClaimQueries:
    async def get_detail(self, claim_id: str) -> ClaimDetail | None:
        return ClaimDetail(
            id=claim_id,
            ramo="vehiculos",
            cobertura="Daños propios",
            asegurado="María Salazar",
            asegurado_id="ASE-1",
            poliza="POL-1",
            ciudad="Quito",
            fecha_ocurrencia=date(2026, 4, 17),
            fecha_reporte=date(2026, 4, 18),
            monto_reclamado=12000.0,
            suma_asegurada=30000.0,
            estado="Reserva",
            sucursal="Quito",
            descripcion="Siniestro sintético para prueba de histórico.",
            score=53,
            nivel=Tier.amarillo,
        )
