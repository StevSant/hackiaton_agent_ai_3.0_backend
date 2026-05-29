from app.use_cases.visual_payload_replay import legacy_chart_to_visuals


def test_legacy_chart_payload_maps_to_chart_visual():
    legacy = {
        "message_id": "m1",
        "title": "Top riesgo",
        "chart_type": "horizontal_bar",
        "available_types": ["horizontal_bar"],
        "labels": ["SIN-1"],
        "series": [{"name": "Score", "data": [87.0]}],
    }
    visuals = legacy_chart_to_visuals(legacy)
    assert visuals == [{"kind": "chart", "data": legacy}]


def test_legacy_none_maps_to_empty_list():
    assert legacy_chart_to_visuals(None) == []


def test_legacy_empty_dict_maps_to_empty_list():
    # An empty chart_payload is useless — treat it like None (documents the
    # `if not chart_payload` semantics so it isn't "fixed" to `is None`).
    assert legacy_chart_to_visuals({}) == []
