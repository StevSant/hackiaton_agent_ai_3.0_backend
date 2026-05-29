"""Decide, after the tool loop, whether/which visuals best present the answer.

One structured strict LLM call. Returns a VisualPlan (possibly empty). The
deterministic builder (`_visuals_from_tools`) turns the plan into AgentVisuals.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.infrastructure.llm import LLMProvider, Message, PromptLoader, ResponseFormat
from app.schemas.visual_plan import VisualPlan

logger = logging.getLogger(__name__)

# Tools that can ever yield a visual — others are skipped from the planner payload.
_VISUAL_TOOLS = (
    "query_claims",
    "aggregate_by_dimension",
    "get_claim_detail",
    "missing_documents",
    "summarize_critical",
)


def _summarize_tool_result(tr: dict[str, Any]) -> dict[str, Any]:
    """Compact, token-cheap summary for the planner — shape, not full data."""
    result = tr.get("result")
    summary: dict[str, Any] = {
        "tool_ref": tr.get("call_id", ""),
        "tool": tr.get("tool", ""),
    }
    if isinstance(result, dict):
        if isinstance(result.get("claims"), list):
            summary["n_claims"] = len(result["claims"])
        if isinstance(result.get("rows"), list):
            summary["n_rows"] = len(result["rows"])
            summary["dimension"] = result.get("dimension")
        if "summary" in result:
            summary["is_executive_summary"] = True
        if result.get("found") is not None:
            summary["single_claim"] = bool(result.get("found"))
    # Pass the user-set chart_hint through if present (explicit request wins).
    args = tr.get("args")
    if isinstance(args, dict) and isinstance(args.get("chart_hint"), dict):
        summary["explicit_request"] = args["chart_hint"].get("chart_type")
    return summary


class PlanVisuals:
    def __init__(self, *, llm: LLMProvider, prompts: PromptLoader, model: str) -> None:
        self._llm = llm
        self._prompts = prompts
        self._model = model

    async def run(self, *, query: str, tool_results: list[dict[str, Any]]) -> VisualPlan:
        candidates = [
            _summarize_tool_result(tr)
            for tr in tool_results
            if tr.get("tool") in _VISUAL_TOOLS and isinstance(tr.get("result"), dict)
        ]
        if not candidates:
            return VisualPlan()
        try:
            system = self._prompts.load("visual_planner", "v1")
            user = (
                f"Pregunta del usuario:\n{query}\n\n"
                f"Resultados disponibles:\n{json.dumps(candidates, ensure_ascii=False)}"
            )
            result = await self._llm.complete(
                messages=[
                    Message(role="system", content=system),
                    Message(role="user", content=user),
                ],
                model=self._model,
                response_format=ResponseFormat(
                    schema_name=VisualPlan.__name__,
                    json_schema=VisualPlan.model_json_schema(),
                    strict=True,
                ),
            )
            plan = VisualPlan.model_validate_json(result.message.content)
        except Exception:
            logger.exception("plan_visuals failed; no visuals this turn")
            return VisualPlan()
        # Hard cap: never more than 2 visuals regardless of model output.
        return VisualPlan(visuals=plan.visuals[:2])
