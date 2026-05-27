"""Smoke test for the claims import feature — runs WITHOUT a live DB.

Validates:
1. Parse each sample file (JSON + CSV) — check row counts.
2. For every parsed ClaimDetail, verify that the mapping functions produce NO
   None values for any NOT-NULL ORM column.
3. Run score_claim on a sample subset — confirm no exceptions.
4. Import the app and check that POST /claims/import route is registered.
5. Print tier spread + signal coverage from the prod sample.

Exit code 0 → all checks passed ("IMPORT SMOKE OK").
Exit code 1 → at least one check failed.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Parse all samples
# ---------------------------------------------------------------------------
print("─" * 60)
print("1. Parsing sample files…")

from app.use_cases.import_claims import parse_csv, parse_json  # noqa: E402

samples_dir = Path("data/samples")

json_files = {
    "claims.dev.json": 40,
    "claims.test.json": 80,
    "claims.prod.json": 180,
}

all_claims = {}
for fname, expected_count in json_files.items():
    content = (samples_dir / fname).read_bytes()
    claims = parse_json(content)
    assert len(claims) == expected_count, (
        f"{fname}: expected {expected_count}, got {len(claims)}"
    )
    all_claims[fname] = claims
    print(f"  ✓ {fname}: {len(claims)} records")

csv_content = (samples_dir / "claims.sample.csv").read_bytes()
csv_claims = parse_csv(csv_content)
assert len(csv_claims) == 10, f"claims.sample.csv: expected 10, got {len(csv_claims)}"
print(f"  ✓ claims.sample.csv: {len(csv_claims)} records")

# ---------------------------------------------------------------------------
# 2. NOT-NULL check via ORM model introspection
# ---------------------------------------------------------------------------
print("\n2. NOT-NULL column check…")

from sqlalchemy import inspect as sa_inspect  # noqa: E402

from app.infrastructure.db.models.asegurado import Asegurado  # noqa: E402
from app.infrastructure.db.models.documento import Documento  # noqa: E402
from app.infrastructure.db.models.poliza import Poliza  # noqa: E402
from app.infrastructure.db.models.proveedor import Proveedor  # noqa: E402
from app.infrastructure.db.models.siniestro import Siniestro  # noqa: E402
from app.use_cases.load_dataset._mapping import (  # noqa: E402
    claim_detail_to_asegurado,
    claim_detail_to_documentos,
    claim_detail_to_poliza,
    claim_detail_to_proveedor,
    claim_detail_to_siniestro,
)


def _not_null_columns(model_class: type) -> list[str]:
    """Return a list of column names that are NOT NULL (nullable=False)."""
    mapper = sa_inspect(model_class)
    not_null = []
    for col in mapper.columns:
        # primary-key columns are never nullable by design; skip them
        if col.primary_key:
            continue
        if not col.nullable:
            not_null.append(col.key)
    return not_null


# Pre-compute NOT NULL columns per model
not_null_map = {
    "Asegurado": _not_null_columns(Asegurado),
    "Poliza": _not_null_columns(Poliza),
    "Siniestro": _not_null_columns(Siniestro),
    "Documento": _not_null_columns(Documento),
    "Proveedor": _not_null_columns(Proveedor),
}
print("  NOT-NULL columns per model:")
for m, cols in not_null_map.items():
    print(f"    {m}: {cols}")

null_violations: list[str] = []
# Check prod sample (largest — covers most archetypes)
prod_claims = all_claims["claims.prod.json"]
for idx, claim in enumerate(prod_claims):
    ase = claim_detail_to_asegurado(claim)
    pol = claim_detail_to_poliza(claim)
    sin = claim_detail_to_siniestro(claim)
    docs = claim_detail_to_documentos(claim)
    prov = claim_detail_to_proveedor(claim)

    for col in not_null_map["Asegurado"]:
        if getattr(ase, col, None) is None:
            null_violations.append(f"row {idx} Asegurado.{col} is None")
    for col in not_null_map["Poliza"]:
        if getattr(pol, col, None) is None:
            null_violations.append(f"row {idx} Poliza.{col} is None")
    for col in not_null_map["Siniestro"]:
        if getattr(sin, col, None) is None:
            null_violations.append(f"row {idx} Siniestro.{col} is None")
    for doc in docs:
        for col in not_null_map["Documento"]:
            if getattr(doc, col, None) is None:
                null_violations.append(f"row {idx} Documento.{col} is None")
    if prov is not None:
        for col in not_null_map["Proveedor"]:
            if getattr(prov, col, None) is None:
                null_violations.append(f"row {idx} Proveedor.{col} is None")

if null_violations:
    print("  ✗ NOT-NULL VIOLATIONS:")
    for v in null_violations[:20]:
        print(f"    {v}")
    sys.exit(1)
else:
    print(f"  ✓ All NOT-NULL columns populated correctly (checked {len(prod_claims)} rows)")

# ---------------------------------------------------------------------------
# 3. score_claim sanity check (first 10 prod claims)
# ---------------------------------------------------------------------------
print("\n3. score_claim sanity check…")
from app.domain.rules.context import RuleContext  # noqa: E402
from app.use_cases.score_claim import score_claim  # noqa: E402

for claim in prod_claims[:10]:
    ctx = RuleContext.from_claim(claim)
    risk = score_claim(claim, ctx=ctx)
    assert 0 <= risk.score <= 100, f"score out of range: {risk.score}"
print("  ✓ 10 claims scored without errors")

# ---------------------------------------------------------------------------
# 4. Route registration check
# ---------------------------------------------------------------------------
print("\n4. Route registration check…")
from app.main import app  # noqa: E402

routes = [r.path for r in app.routes if hasattr(r, "path")]  # type: ignore[attr-defined]
import_routes = [r for r in routes if "import" in r]
assert import_routes, f"POST /claims/import not found in routes: {routes}"
print(f"  ✓ Import routes registered: {import_routes}")

# ---------------------------------------------------------------------------
# 5. Tier spread + signal coverage (prod sample)
# ---------------------------------------------------------------------------
print("\n5. Tier spread + signal coverage (prod sample)…")
from collections import Counter  # noqa: E402

tier_counts: Counter[str] = Counter(c.nivel.value for c in prod_claims)
signal_counts: Counter[str] = Counter(
    a.code for c in prod_claims for a in c.alertas
)

print("  Tier distribution:")
for tier, count in sorted(tier_counts.items()):
    print(f"    {tier}: {count}")

all_codes = [
    *[f"FS-{i:02d}" for i in range(1, 15)],
    *[f"RF-{i:02d}" for i in range(1, 8)],
]
missing = [c for c in all_codes if signal_counts.get(c, 0) < 3]
print(f"  Signal coverage (codes with < 3 exemplars): {missing or 'none'}")

print("\n" + "─" * 60)
print("IMPORT SMOKE OK")
