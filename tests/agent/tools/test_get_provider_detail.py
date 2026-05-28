"""Smoke tests for GetProviderDetailTool using InMemoryClaimQueries.

Verifies that the tool correctly calls the port and returns the expected output
shape. No real DB or LLM calls — pure unit test.
"""

import pytest

from app.agents.claims_agent.tools.get_provider_detail_tool import (
    GetProviderDetailInput,
    GetProviderDetailTool,
)
from app.use_cases.claim_queries import InMemoryClaimQueries
from tests.fixtures.agent_claims import agent_fixtures


def _make_tool() -> GetProviderDetailTool:
    queries = InMemoryClaimQueries(claims=agent_fixtures())
    return GetProviderDetailTool(queries)


# ---------------------------------------------------------------------------
# Test 1: known provider → output contains ProviderOut + top_claims
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_provider_detail_found() -> None:
    """Fetching a known provider id returns found=True with provider data and top_claims."""
    tool = _make_tool()
    result = await tool.run(GetProviderDetailInput(provider_id="P-042"))

    assert result.found is True
    assert result.provider is not None
    assert result.provider.id_proveedor == "P-042"
    assert isinstance(result.top_claims, list)
    assert len(result.top_claims) > 0
    # Top claims should be ordered by score desc
    if len(result.top_claims) > 1:
        assert result.top_claims[0].score >= result.top_claims[-1].score


# ---------------------------------------------------------------------------
# Test 2: unknown provider → found=False, no provider, empty top_claims
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_provider_detail_not_found() -> None:
    """Fetching an unknown provider id returns found=False."""
    tool = _make_tool()
    result = await tool.run(GetProviderDetailInput(provider_id="PRV-NONEXISTENT"))

    assert result.found is False
    assert result.provider is None
    assert result.top_claims == []


# ---------------------------------------------------------------------------
# Test 3: tool metadata
# ---------------------------------------------------------------------------


def test_get_provider_detail_tool_metadata() -> None:
    """Tool name and description are set correctly."""
    tool = _make_tool()
    assert tool.name == "get_provider_detail"
    assert "proveedor" in tool.description.lower()
    schema = tool.input_schema
    assert "provider_id" in schema.get("properties", {})
