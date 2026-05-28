"""Tests for asegurado-focus dispatcher behavior.

Symmetric counterpart to test_focus_provider_id.py.

Covers:
  - inject when phrasing matches 'este asegurado' / 'ese cliente'
  - do NOT inject when question is broad ('qué asegurados tienen mayor frecuencia')
  - get_asegurado_detail always gets asegurado_id injected (no phrasing gate)
  - LLM-provided filter_asegurado_id overrides auto-inject
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


def _make_focus(asegurado_id: str) -> FocusContext:
    return FocusContext(asegurado_id=asegurado_id)


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
# Test 1: get_asegurado_detail always gets asegurado_id injected (no phrasing gate)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_asegurado_detail_always_injects_asegurado_id() -> None:
    """get_asegurado_detail must receive asegurado_id even for broad phrasing."""
    focus = _make_focus("ASE-1001")
    llm_args: dict[str, Any] = {}
    broad_message = "¿qué asegurados tienen mayor frecuencia de reclamos?"

    resolved = inject_focus_context(
        tool_name="get_asegurado_detail",
        llm_args=llm_args,
        focus=focus,
        last_user_message=broad_message,
    )

    assert resolved["asegurado_id"] == "ASE-1001"


# ---------------------------------------------------------------------------
# Test 2: broad tool — focused phrasing → inject filter_asegurado_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregate_injects_filter_for_focused_asegurado_phrasing() -> None:
    """aggregate_by_dimension should receive filter_asegurado_id when phrasing is 'este asegurado'."""
    focus = _make_focus("ASE-1001")
    llm_args: dict[str, Any] = {"dimension": "ramo", "tier": "amarillo+rojo", "top_n": 10}
    focused_message = "¿en qué ramos reclama este asegurado?"

    resolved = inject_focus_context(
        tool_name="aggregate_by_dimension",
        llm_args=llm_args,
        focus=focus,
        last_user_message=focused_message,
    )

    assert resolved.get("filter_asegurado_id") == "ASE-1001"


# ---------------------------------------------------------------------------
# Test 3: broad tool — broad phrasing → do NOT inject filter_asegurado_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregate_does_not_inject_for_broad_asegurado_question() -> None:
    """Even with asegurado focus set, broad questions must NOT get filter_asegurado_id."""
    focus = _make_focus("ASE-1001")
    llm_args: dict[str, Any] = {"dimension": "asegurado", "tier": "amarillo+rojo", "top_n": 10}
    broad_message = "¿qué asegurados tienen mayor frecuencia de reclamos?"

    resolved = inject_focus_context(
        tool_name="aggregate_by_dimension",
        llm_args=llm_args,
        focus=focus,
        last_user_message=broad_message,
    )

    assert resolved.get("filter_asegurado_id") is None


# ---------------------------------------------------------------------------
# Test 4: LLM-provided filter_asegurado_id overrides auto-inject
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_provided_filter_asegurado_id_wins() -> None:
    """When the LLM explicitly provides filter_asegurado_id, that value is kept."""
    focus = _make_focus("ASE-1001")
    llm_args: dict[str, Any] = {
        "dimension": "ramo",
        "tier": "amarillo+rojo",
        "top_n": 5,
        "filter_asegurado_id": "ASE-9999",  # LLM's explicit choice
    }
    focused_message = "¿en qué ramos reclama este asegurado?"

    resolved = inject_focus_context(
        tool_name="aggregate_by_dimension",
        llm_args=llm_args,
        focus=focus,
        last_user_message=focused_message,
    )

    # LLM's value must win
    assert resolved["filter_asegurado_id"] == "ASE-9999"


# ---------------------------------------------------------------------------
# Test 5: matching phrasing — 'ese cliente' also triggers injection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ese_cliente_triggers_injection() -> None:
    """'ese cliente' must also trigger filter_asegurado_id injection."""
    focus = _make_focus("ASE-1001")
    llm_args: dict[str, Any] = {"dimension": "ramo", "tier": "amarillo+rojo", "top_n": 10}
    message = "¿cuántas alertas acumula ese cliente?"

    resolved = inject_focus_context(
        tool_name="aggregate_by_dimension",
        llm_args=llm_args,
        focus=focus,
        last_user_message=message,
    )

    assert resolved.get("filter_asegurado_id") == "ASE-1001"


# ---------------------------------------------------------------------------
# Integration: ToolEntry.run_with_context injects asegurado focus
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_entry_run_with_context_injects_asegurado_focus() -> None:
    """ToolEntry.run_with_context dispatches get_asegurado_detail with asegurado_id injected."""
    queries = _make_queries()
    registry = _make_registry(queries)
    entry = registry["get_asegurado_detail"]

    # The fixture's asegurado field on claims is "R. Castro", etc. — not an id.
    # InMemoryClaimQueries.get_asegurado_detail matches on c.asegurado == asegurado_id.
    # Use a real asegurado name from fixtures as a stand-in.
    focus = FocusContext(asegurado_id="R. Castro")

    result = await entry.run_with_context(
        llm_args={},
        focus=focus,
        last_user_message="cuéntame sobre este asegurado",
    )

    assert result.found is True  # type: ignore[attr-defined]
    assert result.asegurado is not None  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Provider focus context does NOT bleed into asegurado tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provider_focus_does_not_inject_into_asegurado_tool() -> None:
    """A provider-focused session must NOT inject asegurado_id into get_asegurado_detail."""
    provider_focus = FocusContext(provider_id="P-042")
    llm_args: dict[str, Any] = {}
    message = "cuéntame sobre este proveedor"

    resolved = inject_focus_context(
        tool_name="get_asegurado_detail",
        llm_args=llm_args,
        focus=provider_focus,
        last_user_message=message,
    )

    assert "asegurado_id" not in resolved or resolved.get("asegurado_id") is None
