"""Acceptance test: the 12 mandatory NL questions (root CLAUDE.md §2.6).

The expected shape is asserted per-question — not a one-size-fits-all "any
claim ID present" check. Q4 surfaces ramos (not claim IDs); Q5 surfaces
ciudades; Q11 surfaces aggregate counts; etc.

Real-LLM smoke is in `tests/integration/test_nl_questions_real_llm.py` (gated
by @pytest.mark.integration). This suite uses `InMemoryFakeLLM` so it's
deterministic + offline.

Each test drains the SSE stream into a list and inspects:
  - which tool_call events fired
  - the tool_result payload (the structured data the LLM would compose over)
  - that no error event was emitted
  - that a done event terminated the stream
"""

from typing import Any

import pytest

from app.schemas.agent import AgentAskContext, AgentAskRequest
from app.schemas.chat.stream import DoneEvent, ErrorEvent, ToolCallEvent, ToolResultEvent
from app.use_cases.ask_agent import AskAgent


async def _run(ask_agent: AskAgent, query: str, **context: Any) -> list[Any]:
    ctx = AgentAskContext(**context) if context else None
    return [event async for event in ask_agent.run(AgentAskRequest(query=query, context=ctx))]


def _tool_calls(events: list[Any]) -> list[str]:
    return [e.data.tool for e in events if isinstance(e, ToolCallEvent)]


def _tool_results(events: list[Any]) -> list[Any]:
    return [e.data.result for e in events if isinstance(e, ToolResultEvent)]


def _assert_clean_finish(events: list[Any]) -> None:
    errors = [e for e in events if isinstance(e, ErrorEvent)]
    assert not errors, f"unexpected error events: {[e.data.model_dump() for e in errors]}"
    done = [e for e in events if isinstance(e, DoneEvent)]
    assert len(done) == 1, "stream must end with exactly one done event"


@pytest.mark.asyncio
async def test_q1_top_10_high_risk(ask_agent: AskAgent) -> None:
    events = await _run(
        ask_agent, "¿Cuáles son los 10 siniestros con mayor riesgo de posible fraude?"
    )
    _assert_clean_finish(events)
    assert "query_claims" in _tool_calls(events)
    result = _tool_results(events)[0]
    assert result["mode"] == "top_risk"
    assert len(result["claims"]) > 0
    # Top-N must be sorted desc by score, rojo first
    scores = [c["score"] for c in result["claims"]]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_q2_explain_case_by_id_in_query(ask_agent: AskAgent) -> None:
    events = await _run(ask_agent, "¿Por qué SIN-1001 fue marcado como alto riesgo?")
    _assert_clean_finish(events)
    assert "get_claim_detail" in _tool_calls(events)
    result = _tool_results(events)[0]
    assert result["found"] is True
    assert result["claim"]["id"] == "SIN-1001"
    assert len(result["claim"]["alertas"]) > 0


@pytest.mark.asyncio
async def test_q2_explain_case_via_context_focus(ask_agent: AskAgent) -> None:
    # The chat panel can pin the agent to a focused claim without the user typing the ID.
    events = await _run(
        ask_agent,
        "Explícame este caso por favor",
        focus_claim_id="SIN-1002",
    )
    _assert_clean_finish(events)
    result = _tool_results(events)[0]
    assert result["claim"]["id"] == "SIN-1002"


@pytest.mark.asyncio
async def test_q3_providers_concentrating_alerts(ask_agent: AskAgent) -> None:
    events = await _run(ask_agent, "¿Qué proveedores concentran más alertas?")
    _assert_clean_finish(events)
    assert "aggregate_by_dimension" in _tool_calls(events)
    result = _tool_results(events)[0]
    assert result["dimension"] == "proveedor"
    # P-042 is in 3 of the 8 fixtures → must appear first
    assert result["rows"][0]["key"] == "P-042"
    assert result["rows"][0]["count"] >= 2
    assert result["rows"][0]["example_claim_id"]  # citation present


@pytest.mark.asyncio
async def test_q4_ramos_with_higher_suspicious_pct(ask_agent: AskAgent) -> None:
    events = await _run(ask_agent, "¿Qué ramos tienen mayor porcentaje de casos sospechosos?")
    _assert_clean_finish(events)
    result = _tool_results(events)[0]
    assert result["dimension"] == "ramo"
    # Vehículos dominates (rojo + amarillo) → first
    assert result["rows"][0]["key"] == "Vehículos"
    assert result["rows"][0]["pct"] > 0


@pytest.mark.asyncio
async def test_q5_cities_with_alert_concentration(ask_agent: AskAgent) -> None:
    events = await _run(ask_agent, "¿Qué ciudades presentan mayor concentración de alertas?")
    _assert_clean_finish(events)
    result = _tool_results(events)[0]
    assert result["dimension"] == "ciudad"
    cities = [row["key"] for row in result["rows"]]
    assert "Guayaquil" in cities or "Quito" in cities


@pytest.mark.asyncio
async def test_q6_insured_with_highest_frequency(ask_agent: AskAgent) -> None:
    events = await _run(ask_agent, "¿Qué asegurados tienen mayor frecuencia de reclamos?")
    _assert_clean_finish(events)
    result = _tool_results(events)[0]
    assert result["dimension"] == "asegurado"
    # A. Pérez repeats across SIN-1003 + SIN-2003
    top_insured = [row["key"] for row in result["rows"]]
    assert "A. Pérez" in top_insured


@pytest.mark.asyncio
async def test_q7_missing_documents(ask_agent: AskAgent) -> None:
    events = await _run(ask_agent, "¿Qué documentos faltan en los casos críticos?")
    _assert_clean_finish(events)
    assert "missing_documents" in _tool_calls(events)
    result = _tool_results(events)[0]
    assert len(result["claims"]) > 0
    for row in result["claims"]:
        assert len(row["documentos_faltantes"]) > 0
        assert row["claim_id"].startswith("SIN-")


@pytest.mark.asyncio
async def test_q8_atypical_amounts(ask_agent: AskAgent) -> None:
    events = await _run(ask_agent, "¿Qué casos tienen montos atípicos?")
    _assert_clean_finish(events)
    # Q8 maps to aggregate (proveedor by default) — shape check only
    assert "aggregate_by_dimension" in _tool_calls(events)
    result = _tool_results(events)[0]
    assert "rows" in result


@pytest.mark.asyncio
async def test_q9_claims_near_policy_start(ask_agent: AskAgent) -> None:
    events = await _run(ask_agent, "¿Qué siniestros ocurrieron cerca del inicio de la póliza?")
    _assert_clean_finish(events)
    assert "query_claims" in _tool_calls(events)
    result = _tool_results(events)[0]
    assert result["mode"] == "near_policy_start"
    # SIN-2001 + SIN-2002 both carry FS-01 in fixtures
    ids = {c["id"] for c in result["claims"]}
    assert ids & {"SIN-2001", "SIN-2002"}


@pytest.mark.asyncio
async def test_q10_repeated_patterns(ask_agent: AskAgent) -> None:
    events = await _run(ask_agent, "¿Qué patrones se repiten en los reclamos sospechosos?")
    _assert_clean_finish(events)
    assert "aggregate_by_dimension" in _tool_calls(events)


@pytest.mark.asyncio
async def test_q11_executive_summary(ask_agent: AskAgent) -> None:
    events = await _run(ask_agent, "Genera un resumen ejecutivo de los casos críticos.")
    _assert_clean_finish(events)
    assert "summarize_critical" in _tool_calls(events)
    result = _tool_results(events)[0]
    summary = result["summary"]
    assert summary["total_claims"] == 8
    assert summary["rojo_count"] == 3
    assert summary["amarillo_count"] == 3
    assert summary["verde_count"] == 2
    assert len(summary["top_rojo"]) > 0
    assert "P-042" in summary["top_proveedores"]


@pytest.mark.asyncio
async def test_q12_recommend_review_first(ask_agent: AskAgent) -> None:
    events = await _run(ask_agent, "Recomienda qué casos debería revisar primero el analista.")
    _assert_clean_finish(events)
    assert "query_claims" in _tool_calls(events)
    result = _tool_results(events)[0]
    assert result["mode"] == "recommend_review"
    # Rojo cases must appear at the top of the recommendation
    top = result["claims"][0]
    assert top["nivel"] == "rojo"
