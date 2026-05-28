"""Workflow smoke test — standalone async script (NOT pytest).

Exercises the 5-state escalation machine via httpx.AsyncClient with two JWT roles.
Prints "WORKFLOW SMOKE OK" + per-assertion results.

Run:
    uv run python tests/reviews/smoke_workflow.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import traceback

# ---- env setup BEFORE any settings-loading imports ----
os.environ.setdefault("AUTH_ENABLED", "true")
os.environ.setdefault("JWT_SECRET", "smoke-test-secret-for-ci")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://unused:unused@localhost/unused")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault(
    "AUTH_SEED_USERS",
    json.dumps([
        {
            "email": "ana@demo.com",
            "password": "analista123",
            "role": "analista",
            "full_name": "Ana Lema",
        },
        {
            "email": "lucia@demo.com",
            "password": "antifraude123",
            "role": "antifraude",
            "full_name": "Lucía Vélez",
        },
    ]),
)

# ---- NOW safe to import app components ----
import httpx  # noqa: E402

from app.api.deps import get_claim_queries_dep, get_reviews_store  # noqa: E402
from app.infrastructure.reviews.in_memory_reviews_store import InMemoryReviewsStore  # noqa: E402
from app.main import create_app  # noqa: E402
from app.schemas.claim import ClaimReview  # noqa: E402
from app.use_cases.claim_queries.in_memory_claim_queries import InMemoryClaimQueries  # noqa: E402
from tests.fixtures.claims import claim_rojo  # noqa: E402

# ---- helpers ----------------------------------------------------------------

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

_results: list[str] = []
_failures = 0


def check(label: str, cond: bool, got: object = None) -> None:
    global _failures
    status = PASS if cond else FAIL
    suffix = f"  [got: {got!r}]" if not cond else ""
    _results.append(f"  {status}  {label}{suffix}")
    if not cond:
        _failures += 1


# ---- main smoke -------------------------------------------------------------


async def run_smoke() -> None:  # noqa: PLR0912, PLR0915
    app = create_app()

    # Fresh store (always starts empty) — test IDs are predictable
    fresh_store = InMemoryReviewsStore()
    app.dependency_overrides[get_reviews_store] = lambda: fresh_store

    # Single rojo fixture
    rojo = claim_rojo()
    claim_id = rojo.id  # "SIN-0003"
    fixture_queries = InMemoryClaimQueries(claims=[rojo])
    app.dependency_overrides[get_claim_queries_dep] = lambda: fixture_queries

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
    ) as client:

        # ---- Login ----
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": "ana@demo.com", "password": "analista123"},
        )
        check("Login analista → 200", r.status_code == 200, r.status_code)
        ana_token = r.json().get("access_token", "")

        r = await client.post(
            "/api/v1/auth/login",
            json={"email": "lucia@demo.com", "password": "antifraude123"},
        )
        check("Login antifraude → 200", r.status_code == 200, r.status_code)
        lucia_token = r.json().get("access_token", "")

        ana_h = {"Authorization": f"Bearer {ana_token}"}
        lucia_h = {"Authorization": f"Bearer {lucia_token}"}

        # =====================================================================
        # RBAC: analista /take → 403; antifraude /escalate → 403
        # =====================================================================
        r = await client.post(f"/api/v1/claims/{claim_id}/take", headers=ana_h)
        check("RBAC: analista /take → 403", r.status_code == 403, r.status_code)

        r = await client.post(
            f"/api/v1/claims/{claim_id}/escalate", json={}, headers=lucia_h
        )
        check("RBAC: antifraude /escalate → 403", r.status_code == 403, r.status_code)

        # =====================================================================
        # Happy path: escalate → take → dictamen confirmado_sospecha
        # =====================================================================

        # 1. Analista escalates
        r = await client.post(
            f"/api/v1/claims/{claim_id}/escalate",
            json={"note": "Monto atípico, documentos incompletos."},
            headers=ana_h,
        )
        check("Happy path: escalate → 200", r.status_code == 200, r.status_code)
        rv = r.json().get("review", {})
        check(
            "Happy path: status=escalado",
            rv.get("status") == "escalado",
            rv.get("status"),
        )

        # 2. Antifraude takes
        r = await client.post(f"/api/v1/claims/{claim_id}/take", headers=lucia_h)
        check("Happy path: take → 200", r.status_code == 200, r.status_code)
        rv = r.json().get("review", {})
        check(
            "Happy path: status=en_revision",
            rv.get("status") == "en_revision",
            rv.get("status"),
        )

        # 3. Antifraude dictamina confirmado_sospecha
        r = await client.post(
            f"/api/v1/claims/{claim_id}/dictamen",
            json={
                "outcome": "confirmado_sospecha",
                "justificacion": (
                    "Documentos alterados: fechas previas al siniestro. "
                    "Alerta de posible fraude confirmada."
                ),
            },
            headers=lucia_h,
        )
        check("Happy path: dictamen → 200", r.status_code == 200, r.status_code)
        rv = r.json().get("review", {})
        check(
            "Happy path: status=dictaminado",
            rv.get("status") == "dictaminado",
            rv.get("status"),
        )
        check(
            "Happy path: outcome=confirmado_sospecha",
            rv.get("dictamen_outcome") == "confirmado_sospecha",
            rv.get("dictamen_outcome"),
        )

        # 4. GET detail reflects dictamen
        r = await client.get(f"/api/v1/claims/{claim_id}", headers=ana_h)
        status_in_detail = r.json().get("review", {}).get("status") if r.status_code == 200 else None
        check(
            "GET /claims/{id}: review.status=dictaminado",
            r.status_code == 200 and status_in_detail == "dictaminado",
            status_in_detail,
        )

        # =====================================================================
        # Bounce path: reset → escalate → dictamen requiere_mas_info
        # =====================================================================
        await fresh_store.save(claim_id, ClaimReview())  # reset to pendiente

        r = await client.post(
            f"/api/v1/claims/{claim_id}/escalate", json={}, headers=ana_h
        )
        check("Bounce setup: escalate → 200", r.status_code == 200, r.status_code)

        r = await client.post(
            f"/api/v1/claims/{claim_id}/dictamen",
            json={
                "outcome": "requiere_mas_info",
                "justificacion": (
                    "Falta la declaración del testigo y la copia del SOAT vigente "
                    "al momento del siniestro."
                ),
            },
            headers=lucia_h,
        )
        check("Bounce: requiere_mas_info → 200", r.status_code == 200, r.status_code)
        rv = r.json().get("review", {})
        check(
            "Bounce: status=pendiente after bounce",
            rv.get("status") == "pendiente",
            rv.get("status"),
        )
        check("Bounce: bounce_count==1", rv.get("bounce_count") == 1, rv.get("bounce_count"))
        check("Bounce: bounce_note present", bool(rv.get("bounce_note")), rv.get("bounce_note"))

        # =====================================================================
        # Guard: /close on bounced claim → 422
        # =====================================================================
        r = await client.post(
            f"/api/v1/claims/{claim_id}/close", json={}, headers=ana_h
        )
        check("Guard: /close bounce_count>0 → 422", r.status_code == 422, r.status_code)

        # =====================================================================
        # Idempotency: same antifraude /take twice → 200; different → 409
        # =====================================================================
        await fresh_store.save(claim_id, ClaimReview())  # reset
        await client.post(
            f"/api/v1/claims/{claim_id}/escalate", json={}, headers=ana_h
        )

        r1 = await client.post(f"/api/v1/claims/{claim_id}/take", headers=lucia_h)
        check("Idempotency: first /take → 200", r1.status_code == 200, r1.status_code)

        r2 = await client.post(f"/api/v1/claims/{claim_id}/take", headers=lucia_h)
        check("Idempotency: second /take same user → 200", r2.status_code == 200, r2.status_code)

        # Create a second antifraude JWT via direct issuer
        from app.infrastructure.auth.env_seeded_user_repo import EnvSeededUserRepo
        from app.infrastructure.auth.jwt_issuer import JwtIssuer
        from app.use_cases.auth.login import LoginUseCase

        other_repo = EnvSeededUserRepo(
            json.dumps([
                {
                    "email": "otro@demo.com",
                    "password": "otro123",
                    "role": "antifraude",
                    "full_name": "Otro Antifraude",
                }
            ])
        )
        other_lc = LoginUseCase(repo=other_repo, issuer=JwtIssuer())
        otro_resp = other_lc.execute(email="otro@demo.com", password="otro123")
        otro_h = {"Authorization": f"Bearer {otro_resp.access_token}"}

        r3 = await client.post(f"/api/v1/claims/{claim_id}/take", headers=otro_h)
        check(
            "Idempotency: different antifraude /take → 409",
            r3.status_code == 409,
            r3.status_code,
        )

        # =====================================================================
        # GET /antifraude/inbox: real escalations visible
        # =====================================================================
        r = await client.get("/api/v1/antifraude/inbox", headers=lucia_h)
        check("Inbox: GET → 200", r.status_code == 200, r.status_code)
        inbox = r.json()
        check(
            "Inbox: at least the escalated claim under test is visible",
            inbox.get("total", 0) >= 1,
            inbox.get("total"),
        )

    # ---- print summary -------------------------------------------------------
    print("\n=== WORKFLOW SMOKE RESULTS ===")
    for line in _results:
        print(line)
    print()
    if _failures == 0:
        print("WORKFLOW SMOKE OK")
    else:
        print(f"WORKFLOW SMOKE FAILED — {_failures} assertion(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(run_smoke())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(1)
