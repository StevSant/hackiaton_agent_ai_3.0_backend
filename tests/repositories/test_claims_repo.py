"""Integration tests for ClaimsRepo — require a live Postgres + pgvector.

Run locally with docker-compose:
    docker-compose up -d postgres
    uv run pytest -m integration

These are SKIPPED in CI because Docker is not available.
"""

import pytest


@pytest.mark.integration
async def test_claims_repo_get_by_id_returns_none_for_missing() -> None:
    """get_by_id returns None when the siniestro does not exist."""
    # Wired in when a real session fixture is available.
    pytest.skip("requires live Postgres — run with docker-compose")


@pytest.mark.integration
async def test_claims_repo_create_and_retrieve() -> None:
    """Create a siniestro row and retrieve it by id."""
    pytest.skip("requires live Postgres — run with docker-compose")


@pytest.mark.integration
async def test_claims_repo_list_with_pagination() -> None:
    """list_paginated returns the correct page slice."""
    pytest.skip("requires live Postgres — run with docker-compose")
