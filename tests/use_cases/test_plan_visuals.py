"""Tests for VisualPlan schema (Task 1) and PlanVisuals use case (Task 3)."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.llm import InMemoryFakeLLM, PromptLoader
from app.schemas.visual_plan import VisualPlan
from app.use_cases.plan_visuals import PlanVisuals

# ---------------------------------------------------------------------------
# Task 1: Schema tests
# ---------------------------------------------------------------------------


def test_visual_plan_parses_and_caps_are_data_only() -> None:
    plan = VisualPlan.model_validate(
        {"visuals": [{"tool_ref": "call_1", "format": "table", "title": "Top 10"}]}
    )
    assert plan.visuals[0].format == "table"
    assert plan.visuals[0].tool_ref == "call_1"


def test_visual_plan_empty_is_valid() -> None:
    assert VisualPlan.model_validate({"visuals": []}).visuals == []


# ---------------------------------------------------------------------------
# Task 3: PlanVisuals use-case tests
#
# Pattern mirrors test_generate_conversation_title.py:
#   - Create a tmp prompts dir with the prompt file.
#   - Build InMemoryFakeLLM(script={substring: canned_response}).
#   - InMemoryFakeLLM.complete() with response_format set returns the scripted
#     dict as JSON content (want_dict=True branch in the fake).
# ---------------------------------------------------------------------------


def _make_prompts(tmp_path: Path) -> PromptLoader:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "visual_planner.v1.md").write_text(
        "Decide que visualización usar.", encoding="utf-8"
    )
    return PromptLoader(base_dir=prompts_dir)


async def test_plan_visuals_returns_empty_when_no_tool_results(tmp_path: Path) -> None:
    # No candidates → PlanVisuals returns early without calling the LLM.
    llm = InMemoryFakeLLM()
    planner = PlanVisuals(llm=llm, prompts=_make_prompts(tmp_path), model="fake")
    plan = await planner.run(query="hola", tool_results=[])
    assert plan.visuals == []


async def test_plan_visuals_returns_empty_for_non_visual_tools(tmp_path: Path) -> None:
    # Tools not in _VISUAL_TOOLS are filtered out → no candidates → early return.
    llm = InMemoryFakeLLM()
    planner = PlanVisuals(llm=llm, prompts=_make_prompts(tmp_path), model="fake")
    plan = await planner.run(
        query="hola",
        tool_results=[{"call_id": "c1", "tool": "unknown_tool", "result": {}}],
    )
    assert plan.visuals == []


async def test_plan_visuals_calls_llm_and_returns_plan(tmp_path: Path) -> None:
    # The scripted dict must match what VisualPlan.model_validate_json expects.
    # InMemoryFakeLLM: script key is a substring that appears in the user message
    # (which contains the query + tool summaries).
    canned_plan = {"visuals": [{"tool_ref": "c1", "format": "table", "title": "Top"}]}

    # Key on something that will appear in the user message (the query text).
    llm = InMemoryFakeLLM(script={"top 10 siniestros": canned_plan})
    planner = PlanVisuals(llm=llm, prompts=_make_prompts(tmp_path), model="fake")

    tool_results = [
        {
            "call_id": "c1",
            "tool": "query_claims",
            "args": {},
            "result": {"claims": [{"id": "SIN-1", "score": 88}]},
        }
    ]
    plan = await planner.run(
        query="¿Cuáles son los top 10 siniestros con mayor riesgo?",
        tool_results=tool_results,
    )
    assert len(plan.visuals) == 1
    assert plan.visuals[0].format == "table"
    assert plan.visuals[0].tool_ref == "c1"


async def test_plan_visuals_caps_at_two_visuals(tmp_path: Path) -> None:
    # Even if the LLM returns 3, the hard cap is 2.
    canned_plan = {
        "visuals": [
            {"tool_ref": "c1", "format": "table", "title": None},
            {"tool_ref": "c1", "format": "horizontal_bar", "title": None},
            {"tool_ref": "c1", "format": "kpi", "title": None},
        ]
    }
    llm = InMemoryFakeLLM(script={"resumen ejecutivo": canned_plan})
    planner = PlanVisuals(llm=llm, prompts=_make_prompts(tmp_path), model="fake")

    tool_results = [
        {
            "call_id": "c1",
            "tool": "summarize_critical",
            "args": {},
            "result": {"summary": {"total_claims": 50, "rojo_count": 5}},
        }
    ]
    plan = await planner.run(
        query="Necesito un resumen ejecutivo de la cartera",
        tool_results=tool_results,
    )
    assert len(plan.visuals) <= 2


async def test_plan_visuals_returns_empty_on_llm_error(tmp_path: Path) -> None:
    # If the LLM returns invalid JSON, the use case catches the error and
    # returns an empty plan (graceful degradation).
    llm = InMemoryFakeLLM(script={"siniestro": "INVALID JSON NOT A VISUAL PLAN"})
    planner = PlanVisuals(llm=llm, prompts=_make_prompts(tmp_path), model="fake")

    tool_results = [
        {
            "call_id": "c1",
            "tool": "query_claims",
            "args": {},
            "result": {"claims": [{"id": "SIN-1", "score": 80}]},
        }
    ]
    plan = await planner.run(
        query="¿Cuáles son los siniestros con mayor riesgo?",
        tool_results=tool_results,
    )
    assert plan.visuals == []
