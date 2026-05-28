"""Tests for provider-focus dispatcher behavior.

Covers:
  - inject when phrasing matches 'este proveedor' / 'ese proveedor'
  - do NOT inject when question is broad ('qué proveedores concentran más alertas')
  - get_provider_detail always gets provider_id injected (no phrasing gate)
  - LLM-provided filter_provider_id overrides auto-inject
"""

from typing import Any

import pytest

from app.agents.claims_agent._tool_dispatcher import FocusContext, inject_focus_context
from app.agents.claims_agent.tools import (
    AggregateByDimensionTool,
    GetAseguradoDetailTool,
    GetClaimDetailTool,
    GetProviderDetailTool,
    MissingDocumentsTool,
    QueryClaimsTool,
    SummarizeCriticalTool,
)
from app.agents.claims_agent.tools.registry import ToolEntry, build_tool_registry
from app.use_cases.claim_queries import InMemoryClaimQueries
from tests.fixtures.agent_claims import agent_fixtures


def _make_queries() -> InMemoryClaimQueries:
    return InMemoryClaimQueries(claims=agent_fixtures())


def _make_focus(provider_id: str) -> FocusContext:
    return FocusContext(provider_id=provider_id)


def _make_registry(queries: InMemoryClaimQueries) -> dict[str, ToolEntry]:
    return build_tool_registry(
        query_claims=QueryClaimsTool(queries),
        get_claim_detail=GetClaimDetailTool(queries),
        aggregate_by_dimension=AggregateByDimensionTool(queries),
        missing_documents=MissingDocumentsTool(queries),
        summarize_critical=SummarizeCriticalTool(queries),
        get_provider_detail=GetProviderDetailTool(queries),
        get_asegurado_detail=GetAseguradoDetailTool(queries),
    )


# ---------------------------------------------------------------------------
# Test 1: get_provider_detail always gets provider_id injected (no phrasing gate)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_provider_detail_always_injects_provider_id() -> None:
    """get_provider_detail must receive provider_id even for broad phrasing."""
    focus = _make_focus("P-042")
    llm_args: dict[str, Any] = {}  # LLM did NOT provide provider_id
    broad_message = "¿qué proveedores concentran más alertas?"

    resolved = inject_focus_context(
        tool_name="get_provider_detail",
        llm_args=llm_args,
        focus=focus,
        last_user_message=broad_message,
    )

    assert resolved["provider_id"] == "P-042"


# ---------------------------------------------------------------------------
# Test 2: broad tool — focused phrasing → inject filter_provider_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregate_injects_filter_for_focused_provider_phrasing() -> None:
    """aggregate_by_dimension should receive filter_provider_id when phrasing is 'este proveedor'."""
    focus = _make_focus("P-042")
    llm_args: dict[str, Any] = {"dimension": "ramo", "tier": "amarillo+rojo", "top_n": 10}
    focused_message = "¿cuáles casos de este proveedor son atípicos?"

    resolved = inject_focus_context(
        tool_name="aggregate_by_dimension",
        llm_args=llm_args,
        focus=focus,
        last_user_message=focused_message,
    )

    assert resolved.get("filter_provider_id") == "P-042"


# ---------------------------------------------------------------------------
# Test 3: broad tool — broad phrasing → do NOT inject filter_provider_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregate_does_not_inject_for_broad_question() -> None:
    """Even with provider focus set, broad questions must NOT get filter_provider_id."""
    focus = _make_focus("P-042")
    llm_args: dict[str, Any] = {"dimension": "proveedor", "tier": "amarillo+rojo", "top_n": 10}
    broad_message = "¿qué proveedores concentran más alertas?"

    resolved = inject_focus_context(
        tool_name="aggregate_by_dimension",
        llm_args=llm_args,
        focus=focus,
        last_user_message=broad_message,
    )

    assert resolved.get("filter_provider_id") is None


# ---------------------------------------------------------------------------
# Test 4: LLM-provided filter_provider_id overrides auto-inject
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_provided_filter_provider_id_wins() -> None:
    """When the LLM explicitly provides filter_provider_id, that value is kept."""
    focus = _make_focus("P-042")
    llm_args: dict[str, Any] = {
        "dimension": "ramo",
        "tier": "amarillo+rojo",
        "top_n": 5,
        "filter_provider_id": "P-999",  # LLM's explicit choice
    }
    focused_message = "resume las señales de este proveedor"

    resolved = inject_focus_context(
        tool_name="aggregate_by_dimension",
        llm_args=llm_args,
        focus=focus,
        last_user_message=focused_message,
    )

    # LLM's value must win
    assert resolved["filter_provider_id"] == "P-999"


# ---------------------------------------------------------------------------
# Test 5: matching phrasing — 'ese beneficiario' also triggers injection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ese_beneficiario_triggers_injection() -> None:
    """'ese beneficiario' must also trigger filter_provider_id injection."""
    focus = _make_focus("P-042")
    llm_args: dict[str, Any] = {"dimension": "ramo", "tier": "amarillo+rojo", "top_n": 10}
    message = "¿qué ramos concentra ese beneficiario?"

    resolved = inject_focus_context(
        tool_name="aggregate_by_dimension",
        llm_args=llm_args,
        focus=focus,
        last_user_message=message,
    )

    assert resolved.get("filter_provider_id") == "P-042"


# ---------------------------------------------------------------------------
# Integration: ToolEntry.run_with_context injects provider focus
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_entry_run_with_context_injects_provider_focus() -> None:
    """ToolEntry.run_with_context dispatches get_provider_detail with provider_id injected."""
    queries = _make_queries()
    registry = _make_registry(queries)
    entry = registry["get_provider_detail"]
    focus = FocusContext(provider_id="P-042")

    result = await entry.run_with_context(
        llm_args={},
        focus=focus,
        last_user_message="cuéntame sobre este proveedor",
    )

    assert result.found is True  # type: ignore[attr-defined]
    assert result.provider is not None  # type: ignore[attr-defined]
    assert result.provider.id_proveedor == "P-042"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Claim focus context does NOT bleed into provider tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claim_focus_does_not_inject_into_provider_tool() -> None:
    """A claim-focused session must NOT inject provider_id into get_provider_detail."""
    claim_focus = FocusContext(claim_id="SIN-1001")
    llm_args: dict[str, Any] = {}
    message = "explica este caso"

    resolved = inject_focus_context(
        tool_name="get_provider_detail",
        llm_args=llm_args,
        focus=claim_focus,
        last_user_message=message,
    )

    assert "provider_id" not in resolved or resolved.get("provider_id") is None
