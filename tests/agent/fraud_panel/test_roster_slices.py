"""The 4 specialists exist and each extracts a non-empty data slice."""

from __future__ import annotations

from app.agents.fraud_panel import PANEL_ROSTER
from tests.fixtures.claims import claim_rojo


def test_roster_has_four_specialists_with_unique_ids() -> None:
    ids = [s.id for s in PANEL_ROSTER]
    assert ids == ["reglas", "ml", "narrativa", "documentos_red"]
    assert len(set(ids)) == 4


def test_each_specialist_slice_returns_a_dict() -> None:
    claim = claim_rojo()
    for specialist in PANEL_ROSTER:
        sliced = specialist.slice_fn(claim)
        assert isinstance(sliced, dict)
        assert sliced  # non-empty


def test_reglas_slice_includes_alertas_and_score() -> None:
    claim = claim_rojo()
    reglas = next(s for s in PANEL_ROSTER if s.id == "reglas")
    sliced = reglas.slice_fn(claim)
    assert "score" in sliced and "alertas" in sliced
