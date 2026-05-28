"""Tests for filter_claim_id support in aggregate_by_dimension_tool and summarize_critical_tool.

These are the Slice 5 follow-up tests: the other two tools (query_claims, missing_documents)
already had DB-level filtering; this suite confirms the remaining two work correctly.
"""

import pytest

from app.agents.claims_agent.tools.aggregate_by_dimension_tool import (
    AggregateByDimensionInput,
    AggregateByDimensionTool,
)
from app.agents.claims_agent.tools.summarize_critical_tool import (
    SummarizeCriticalInput,
    SummarizeCriticalTool,
)
from app.use_cases.claim_queries import InMemoryClaimQueries
from tests.fixtures.agent_claims import agent_fixtures


@pytest.fixture()
def queries() -> InMemoryClaimQueries:
    return InMemoryClaimQueries(claims=agent_fixtures())


# ---------------------------------------------------------------------------
# aggregate_by_dimension — filter_claim_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregate_no_filter_returns_all_rows(queries: InMemoryClaimQueries) -> None:
    tool = AggregateByDimensionTool(queries)
    result = await tool.run(
        AggregateByDimensionInput(dimension="proveedor", tier="amarillo+rojo", top_n=10)
    )
    # SIN-1001..1003 use P-042, SIN-2001..2002 use P-099 → at least 2 providers
    assert len(result.rows) >= 2


@pytest.mark.asyncio
async def test_aggregate_filter_scopes_to_claim_ramo(queries: InMemoryClaimQueries) -> None:
    """filter_claim_id=SIN-1001 (ramo=Vehículos) → rows contain only ramo=Vehículos."""
    tool = AggregateByDimensionTool(queries)
    result = await tool.run(
        AggregateByDimensionInput(
            dimension="ramo", tier="amarillo+rojo", top_n=10, filter_claim_id="SIN-1001"
        )
    )
    assert len(result.rows) >= 1
    keys = {r.key for r in result.rows}
    assert "Vehículos" in keys
    # Must not contain unrelated ramos
    for r in result.rows:
        assert r.key == "Vehículos"


@pytest.mark.asyncio
async def test_aggregate_filter_unknown_claim_returns_empty(
    queries: InMemoryClaimQueries,
) -> None:
    tool = AggregateByDimensionTool(queries)
    result = await tool.run(
        AggregateByDimensionInput(
            dimension="proveedor",
            tier="amarillo+rojo",
            top_n=10,
            filter_claim_id="SIN-NONEXISTENT",
        )
    )
    assert result.rows == []


@pytest.mark.asyncio
async def test_aggregate_filter_proveedor_none_returns_empty(
    queries: InMemoryClaimQueries,
) -> None:
    """Claims with proveedor=None (SIN-3001) produce no row for dimension=proveedor."""
    tool = AggregateByDimensionTool(queries)
    result = await tool.run(
        AggregateByDimensionInput(
            dimension="proveedor",
            tier="amarillo+rojo",
            top_n=10,
            filter_claim_id="SIN-3001",
        )
    )
    # SIN-3001 is verde and has no proveedor — nothing to aggregate
    assert result.rows == []


# ---------------------------------------------------------------------------
# summarize_critical — filter_claim_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_no_filter_returns_full_summary(
    queries: InMemoryClaimQueries,
) -> None:
    tool = SummarizeCriticalTool(queries)
    result = await tool.run(SummarizeCriticalInput())
    assert result.summary.total_claims > 0
    assert result.summary.rojo_count + result.summary.amarillo_count + result.summary.verde_count == result.summary.total_claims


@pytest.mark.asyncio
async def test_summarize_filter_rojo_claim(queries: InMemoryClaimQueries) -> None:
    """filter_claim_id=SIN-1001 (rojo, score=88) → single-claim summary scoped to it."""
    tool = SummarizeCriticalTool(queries)
    result = await tool.run(SummarizeCriticalInput(filter_claim_id="SIN-1001"))
    s = result.summary
    assert s.total_claims == 1
    assert s.rojo_count == 1
    assert s.amarillo_count == 0
    assert s.verde_count == 0
    assert len(s.top_rojo) == 1
    assert s.top_rojo[0].id == "SIN-1001"
    assert "Vehículos" in s.top_ramos


@pytest.mark.asyncio
async def test_summarize_filter_verde_claim(queries: InMemoryClaimQueries) -> None:
    """filter_claim_id=SIN-3001 (verde) → summary with verde_count=1, top_rojo empty."""
    tool = SummarizeCriticalTool(queries)
    result = await tool.run(SummarizeCriticalInput(filter_claim_id="SIN-3001"))
    s = result.summary
    assert s.total_claims == 1
    assert s.verde_count == 1
    assert s.rojo_count == 0
    assert s.top_rojo == []


@pytest.mark.asyncio
async def test_summarize_filter_unknown_claim_falls_back_to_full(
    queries: InMemoryClaimQueries,
) -> None:
    """When filter_claim_id doesn't exist, tool falls back to the full summary."""
    tool = SummarizeCriticalTool(queries)
    result = await tool.run(SummarizeCriticalInput(filter_claim_id="SIN-NONEXISTENT"))
    # Falls back to full — total > 1
    assert result.summary.total_claims > 1
