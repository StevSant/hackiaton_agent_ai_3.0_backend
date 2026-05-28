"""Smoke tests for GetAseguradoDetailTool using InMemoryClaimQueries.

Symmetric counterpart to test_get_provider_detail.py.
"""

import pytest

from app.agents.claims_agent.tools.get_asegurado_detail_tool import (
    GetAseguradoDetailInput,
    GetAseguradoDetailTool,
)
from app.use_cases.claim_queries import InMemoryClaimQueries
from tests.fixtures.agent_claims import agent_fixtures


def _make_tool() -> GetAseguradoDetailTool:
    queries = InMemoryClaimQueries(claims=agent_fixtures())
    return GetAseguradoDetailTool(queries)


# ---------------------------------------------------------------------------
# Test 1: known asegurado → output contains AseguradoOut + top_claims
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_asegurado_detail_found() -> None:
    """Fetching a known asegurado id returns found=True with asegurado data and top_claims."""
    tool = _make_tool()
    # "R. Castro" appears in the fixtures as an asegurado field value
    result = await tool.run(GetAseguradoDetailInput(asegurado_id="R. Castro"))

    assert result.found is True
    assert result.asegurado is not None
    assert result.asegurado.id_asegurado == "R. Castro"
    assert isinstance(result.top_claims, list)
    assert len(result.top_claims) > 0
    # Top claims should be ordered by score desc
    if len(result.top_claims) > 1:
        assert result.top_claims[0].score >= result.top_claims[-1].score


# ---------------------------------------------------------------------------
# Test 2: unknown asegurado → found=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_asegurado_detail_not_found() -> None:
    """Fetching an unknown asegurado id returns found=False."""
    tool = _make_tool()
    result = await tool.run(GetAseguradoDetailInput(asegurado_id="ASE-NONEXISTENT"))

    assert result.found is False
    assert result.asegurado is None
    assert result.top_claims == []


# ---------------------------------------------------------------------------
# Test 3: tool metadata
# ---------------------------------------------------------------------------


def test_get_asegurado_detail_tool_metadata() -> None:
    """Tool name and description are set correctly."""
    tool = _make_tool()
    assert tool.name == "get_asegurado_detail"
    assert "asegurado" in tool.description.lower()
    schema = tool.input_schema
    assert "asegurado_id" in schema.get("properties", {})
