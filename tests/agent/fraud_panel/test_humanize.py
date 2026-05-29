"""Slice humanizers: raw floats / nulls become business-Spanish readings."""

from __future__ import annotations

from app.agents.fraud_panel import anomaly_reading, probability_reading, similarity_reading


def test_probability_reading_rounds_to_percent() -> None:
    assert probability_reading(0.234) == "23%"
    assert probability_reading(0.0) == "0%"
    assert probability_reading(None) == "no disponible"


def test_anomaly_reading_bands_to_spanish() -> None:
    assert anomaly_reading(-0.5339900598064599) == "muy atípico frente al histórico"
    assert anomaly_reading(-0.05) == "algo atípico frente al histórico"
    assert anomaly_reading(0.12) == "dentro de lo normal"
    assert anomaly_reading(None) == "no disponible"


def test_similarity_reading_rounds_to_percent() -> None:
    assert similarity_reading(0.8712) == "87%"
    assert similarity_reading(None) == "no disponible"
