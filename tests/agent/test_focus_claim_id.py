"""Tests for Slice 5 — auto-scope tools to focus_claim_id.

Each test targets the `_tool_dispatcher` cross-cutting logic that injects
`focus_claim_id` into tool args when the LLM omitted an explicit claim id.

Arrange-Act-Assert. No real LLM calls — every test uses InMemoryFakeLLM.
"""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.claims_agent._tool_dispatcher import inject_focus_claim_id
from app.agents.claims_agent.tools import (
    AggregateByDimensionTool,
    GetClaimDetailTool,
    MissingDocumentsTool,
    QueryClaimsTool,
    SummarizeCriticalTool,
)
from app.agents.claims_agent.tools.registry import ToolEntry, build_tool_registry
from app.use_cases.claim_queries import InMemoryClaimQueries
from tests.fixtures.agent_claims import agent_fixtures


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_queries() -> InMemoryClaimQueries:
    return InMemoryClaimQueries(claims=agent_fixtures())


def _make_registry(queries: InMemoryClaimQueries) -> dict[str, ToolEntry]:
    return build_tool_registry(
        query_claims=QueryClaimsTool(queries),
        get_claim_detail=GetClaimDetailTool(queries),
        aggregate_by_dimension=AggregateByDimensionTool(queries),
        missing_documents=MissingDocumentsTool(queries),
        summarize_critical=SummarizeCriticalTool(queries),
    )


# ---------------------------------------------------------------------------
# Test 1: focus set, LLM gives no claim_id → auto-inject
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_claim_detail_injects_focus_when_llm_omits_claim_id() -> None:
    """When focus_claim_id is set and the LLM provides no claim_id, the tool
    must run against the focused case."""
    # Arrange
    queries = _make_queries()
    registry = _make_registry(queries)
    focus = "SIN-FOO"
    tool_name = "get_claim_detail"
    llm_args: dict[str, Any] = {}  # LLM did NOT provide claim_id
    last_user_message = "¿por qué fue marcado este caso?"

    # Act
    resolved_args = inject_focus_claim_id(
        tool_name=tool_name,
        llm_args=llm_args,
        focus_claim_id=focus,
        last_user_message=last_user_message,
    )

    # Assert
    assert resolved_args["claim_id"] == "SIN-FOO"


# ---------------------------------------------------------------------------
# Test 2: focus set, LLM provides a DIFFERENT claim_id → use LLM's value
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_claim_detail_respects_llm_explicit_claim_id() -> None:
    """When the LLM explicitly provides a different claim_id, that value wins."""
    # Arrange
    focus = "SIN-FOO"
    tool_name = "get_claim_detail"
    llm_args: dict[str, Any] = {"claim_id": "SIN-BAR"}
    last_user_message = "explicame el caso SIN-BAR"

    # Act
    resolved_args = inject_focus_claim_id(
        tool_name=tool_name,
        llm_args=llm_args,
        focus_claim_id=focus,
        last_user_message=last_user_message,
    )

    # Assert — LLM's explicit id is preserved
    assert resolved_args["claim_id"] == "SIN-BAR"


# ---------------------------------------------------------------------------
# Test 3: focus is None, LLM gives no claim_id → args unchanged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_claim_detail_no_focus_no_claim_id_unchanged() -> None:
    """When focus_claim_id is None and LLM omits claim_id, args pass through
    untouched — the tool's existing behavior (probably returning not-found) is
    preserved without crashing."""
    # Arrange
    tool_name = "get_claim_detail"
    llm_args: dict[str, Any] = {}
    last_user_message = "explica el caso"

    # Act
    resolved_args = inject_focus_claim_id(
        tool_name=tool_name,
        llm_args=llm_args,
        focus_claim_id=None,
        last_user_message=last_user_message,
    )

    # Assert — no injection, args unchanged
    assert "claim_id" not in resolved_args


# ---------------------------------------------------------------------------
# Test 4: focus set, aggregate tool, BROAD question → NO auto-filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregate_tool_does_not_inject_focus_for_broad_question() -> None:
    """aggregate_by_dimension should NOT auto-filter when the question is broad
    (no 'este caso' / 'el caso' / 'este siniestro' language)."""
    # Arrange
    tool_name = "aggregate_by_dimension"
    llm_args: dict[str, Any] = {"dimension": "proveedor", "tier": "amarillo+rojo", "top_n": 10}
    focus = "SIN-FOO"
    last_user_message = "Cuáles son los 10 casos más sospechosos?"

    # Act
    resolved_args = inject_focus_claim_id(
        tool_name=tool_name,
        llm_args=llm_args,
        focus_claim_id=focus,
        last_user_message=last_user_message,
    )

    # Assert — filter_claim_id must NOT have been injected
    assert "filter_claim_id" not in resolved_args or resolved_args.get("filter_claim_id") is None


# ---------------------------------------------------------------------------
# Test 5: focus set, aggregate tool, FOCUSED question → auto-inject filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregate_tool_injects_focus_for_focused_question() -> None:
    """aggregate_by_dimension SHOULD auto-inject filter_claim_id when the
    question contains 'este caso' / 'este siniestro' / 'el caso' etc."""
    # Arrange
    tool_name = "aggregate_by_dimension"
    llm_args: dict[str, Any] = {"dimension": "proveedor", "tier": "amarillo+rojo", "top_n": 10}
    focus = "SIN-FOO"
    last_user_message = "Qué patrones similares hay en este caso?"

    # Act
    resolved_args = inject_focus_claim_id(
        tool_name=tool_name,
        llm_args=llm_args,
        focus_claim_id=focus,
        last_user_message=last_user_message,
    )

    # Assert
    assert resolved_args.get("filter_claim_id") == "SIN-FOO"


# ---------------------------------------------------------------------------
# Integration: verify that the ToolEntry.run_raw path uses the dispatcher
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_entry_run_with_context_injects_focus() -> None:
    """ToolEntry.run_with_context injects focus_claim_id before calling the tool."""
    # Arrange
    queries = _make_queries()
    registry = _make_registry(queries)
    entry = registry["get_claim_detail"]

    # Act — simulate the LLM returning no claim_id, but focus is SIN-1001
    result = await entry.run_with_context(
        llm_args={},
        focus_claim_id="SIN-1001",
        last_user_message="por qué este siniestro fue marcado?",
    )

    # Assert — the tool found the real fixture record
    assert result.found is True  # type: ignore[attr-defined]
    assert result.claim is not None  # type: ignore[attr-defined]
    assert result.claim.id == "SIN-1001"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_tool_entry_run_with_context_no_focus_no_claim_id_raises() -> None:
    """Without focus and without claim_id, get_claim_detail raises ValueError
    because claim_id is a required field — this is the unchanged existing behavior."""
    # Arrange
    queries = _make_queries()
    registry = _make_registry(queries)
    entry = registry["get_claim_detail"]

    # Act / Assert — existing behavior: required field missing → ValueError
    with pytest.raises(ValueError, match="invalid args for tool 'get_claim_detail'"):
        await entry.run_with_context(
            llm_args={},
            focus_claim_id=None,
            last_user_message="explica el caso",
        )
