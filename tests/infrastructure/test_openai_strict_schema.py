"""Regression: strict-mode schema normalization must patch nested $defs models.

OpenAI strict mode 400s when ANY object node lacks `additionalProperties: false`.
The walker used to treat the `$defs` container as a schema node and never visited
the definitions inside it — first surfaced by `VisualPlan` (the first strict
schema with a nested model; the panel's strict schemas are flat, so no $defs).
"""

from app.infrastructure.llm.openai_adapter import _normalize_strict_schema
from app.schemas.visual_plan import VisualPlan


def test_nested_defs_get_additional_properties_false() -> None:
    norm = _normalize_strict_schema(VisualPlan.model_json_schema())

    # Root object patched.
    assert norm["additionalProperties"] is False
    assert norm["required"] == ["visuals"]

    # Nested $defs model patched too (this was the bug).
    pv = norm["$defs"]["PlannedVisual"]
    assert pv["additionalProperties"] is False
    # Strict mode: every property listed in required; defaults stripped.
    assert set(pv["required"]) == {"tool_ref", "format", "title"}
    assert "default" not in pv["properties"]["title"]
