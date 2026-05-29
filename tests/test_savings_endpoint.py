"""Smoke test for GET /api/v1/reports/savings-analysis.

Full DB integration is out of scope for unit tests (no live DB in CI).
This file verifies:
  1. The route is registered in the OpenAPI schema.
  2. The response schema fields are present in OpenAPI.
  3. The app imports cleanly (covered by the import itself at module load).
"""

from __future__ import annotations

import app.main


def test_savings_analysis_route_in_openapi() -> None:
    """Route must be registered and visible in the OpenAPI spec."""
    schema = app.main.app.openapi()
    paths = schema.get("paths", {})
    assert any(
        "savings-analysis" in path for path in paths
    ), "GET /reports/savings-analysis must be in OpenAPI paths"


def test_savings_analysis_schema_fields_in_openapi() -> None:
    """SavingsAnalysisOut, SavingsTierBucket, and SavingsEstimate fields must be in OpenAPI."""
    schema = app.main.app.openapi()
    components = schema.get("components", {}).get("schemas", {})

    # Top-level schema names must be registered.
    assert "SavingsAnalysisOut" in components, "SavingsAnalysisOut schema must be in OpenAPI components"
    assert "SavingsTierBucket" in components, "SavingsTierBucket schema must be in OpenAPI components"

    # SavingsEstimate field — distinct from SavingsTierBucket.ahorro_potencial.
    assert "ahorro_potencial_estimado" in str(components), (
        "SavingsEstimate.ahorro_potencial_estimado must be in OpenAPI"
    )

    # SavingsTierBucket-specific field: assert it exists as a property key, not
    # just as a substring of a longer name like ahorro_potencial_estimado.
    tier_bucket_props = components.get("SavingsTierBucket", {}).get("properties", {})
    assert "ahorro_potencial" in tier_bucket_props, (
        "SavingsTierBucket must have an 'ahorro_potencial' property (not just a substring match)"
    )
    assert "ahorro_potencial_estimado" not in tier_bucket_props, (
        "SavingsTierBucket.ahorro_potencial must not be confused with SavingsEstimate.ahorro_potencial_estimado"
    )

    # SavingsAnalysisOut-specific fields.
    analysis_props = components.get("SavingsAnalysisOut", {}).get("properties", {})
    assert "total_ahorro_potencial" in analysis_props, (
        "SavingsAnalysisOut must have 'total_ahorro_potencial'"
    )
    assert "por_nivel" in analysis_props, "SavingsAnalysisOut must have 'por_nivel'"
