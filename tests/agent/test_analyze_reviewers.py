"""analyze_reviewers tool — aggregates dictámenes per analyst (A3)."""

from __future__ import annotations

import pytest

from app.agents.claims_agent.tools import AnalyzeReviewersTool
from app.agents.claims_agent.tools.analyze_reviewers_tool import AnalyzeReviewersInput
from app.schemas.claim import ClaimReview, DictamenOutcome, ReviewStatus
from app.use_cases.claim_queries import InMemoryClaimQueries
from tests.fixtures.agent_claims import agent_fixtures


@pytest.mark.asyncio
async def test_analyze_reviewers_empty_when_no_dictamenes() -> None:
    """agent_fixtures have no dictamen set → tool returns empty list cleanly."""
    queries = InMemoryClaimQueries(claims=agent_fixtures())
    tool = AnalyzeReviewersTool(queries)
    out = await tool.run(AnalyzeReviewersInput(top_n=20))
    assert isinstance(out.reviewers, list)
    assert out.reviewers == []


@pytest.mark.asyncio
async def test_analyze_reviewers_aggregates_per_analyst() -> None:
    """With dictámenes set, counts are aggregated correctly per analyst."""
    from tests.fixtures.agent_claims import _claim
    from app.schemas.claim import ClaimAlert, ClaimDocument
    from app.schemas.risk import Tier

    # Build two claims with dictámenes by "Ana Pérez"
    claim_a = _claim(
        id_="SIN-R001",
        ramo="Vehículos",
        cobertura="Choque",
        asegurado="Test A",
        ciudad="Quito",
        monto=5000.0,
        score=80,
        nivel=Tier.rojo,
        proveedor=None,
        alertas=[ClaimAlert(code="RF-01", puntos=0, severidad="high", detalle="PTxRB")],
        documentos=[ClaimDocument(tipo="Denuncia", estado="Entregado")],
    )
    claim_a.review = ClaimReview(
        status=ReviewStatus.dictaminado,
        dictamen_outcome=DictamenOutcome.confirmado_sospecha,
        dictaminado_by="USR-001",
        dictaminado_by_name="Ana Pérez",
    )

    claim_b = _claim(
        id_="SIN-R002",
        ramo="Vehículos",
        cobertura="Choque",
        asegurado="Test B",
        ciudad="Quito",
        monto=3000.0,
        score=70,
        nivel=Tier.amarillo,
        proveedor=None,
        alertas=[],
        documentos=[],
    )
    claim_b.review = ClaimReview(
        status=ReviewStatus.dictaminado,
        dictamen_outcome=DictamenOutcome.descartado,
        dictaminado_by="USR-001",
        dictaminado_by_name="Ana Pérez",
    )

    # A third claim by a different analyst
    claim_c = _claim(
        id_="SIN-R003",
        ramo="Incendio",
        cobertura="Total",
        asegurado="Test C",
        ciudad="Guayaquil",
        monto=20000.0,
        score=85,
        nivel=Tier.rojo,
        proveedor=None,
        alertas=[],
        documentos=[],
    )
    claim_c.review = ClaimReview(
        status=ReviewStatus.dictaminado,
        dictamen_outcome=DictamenOutcome.requiere_mas_info,
        dictaminado_by="USR-002",
        dictaminado_by_name="Carlos Mora",
    )

    queries = InMemoryClaimQueries(claims=[claim_a, claim_b, claim_c])
    tool = AnalyzeReviewersTool(queries)
    out = await tool.run(AnalyzeReviewersInput(top_n=20))

    assert len(out.reviewers) == 2
    # Ana Pérez has 2 dictámenes — should be first (most active)
    ana = next(r for r in out.reviewers if r.analista == "Ana Pérez")
    assert ana.total_dictamenes == 2
    assert ana.confirmados == 1
    assert ana.descartados == 1
    assert ana.requiere_mas_info == 0
    assert set(ana.claim_ids) == {"SIN-R001", "SIN-R002"}

    carlos = next(r for r in out.reviewers if r.analista == "Carlos Mora")
    assert carlos.total_dictamenes == 1
    assert carlos.requiere_mas_info == 1


@pytest.mark.asyncio
async def test_analyze_reviewers_top_n_limit() -> None:
    """top_n parameter correctly caps the number of returned rows."""
    from tests.fixtures.agent_claims import _claim
    from app.schemas.claim import ClaimAlert, ClaimDocument
    from app.schemas.risk import Tier

    claims = []
    for i in range(5):
        c = _claim(
            id_=f"SIN-TN{i:03d}",
            ramo="Vehículos",
            cobertura="Choque",
            asegurado=f"Asegurado {i}",
            ciudad="Quito",
            monto=1000.0,
            score=60,
            nivel=Tier.amarillo,
            proveedor=None,
            alertas=[],
            documentos=[],
        )
        c.review = ClaimReview(
            status=ReviewStatus.dictaminado,
            dictamen_outcome=DictamenOutcome.descartado,
            dictaminado_by=f"USR-{i:03d}",
            dictaminado_by_name=f"Analista {i}",
        )
        claims.append(c)

    queries = InMemoryClaimQueries(claims=claims)
    tool = AnalyzeReviewersTool(queries)
    out = await tool.run(AnalyzeReviewersInput(top_n=3))
    assert len(out.reviewers) <= 3
