"""Runner: build the synthetic dataset and persist it to ``data/synthetic/``.

Design decisions documented here:
- **Deterministic generation**: all variability is derived from archetype index
  and a SHA-based hash — no ``random`` seeding needed.
- **Baked scores**: each claim is scored at generation time with a fully
  populated ``RuleContext`` (all signal flags set explicitly per archetype).
  The resulting ``score``/``nivel``/``alertas`` are baked into the JSON so
  ``get_claim_detail`` can return them as-is without re-scoring via the context-
  poor ``RuleContext.from_claim`` path (which would clobber the rich score).
  See ``loader.py`` and ``get_claim_detail.py`` for the skip-if-scored logic.
- **Coverage guarantee**: ARCHETYPES is engineered so each FS/RF code appears
  in ≥ 3 archetypes. The coverage report verifies this at generation time.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from app.schemas.claim import ClaimDetail
from app.schemas.risk import Tier
from app.use_cases.generate_dataset._archetypes import ARCHETYPES
from app.use_cases.generate_dataset._claim_builder import build_claim
from app.use_cases.generate_dataset._csv_export import export_csvs

_DATASET_PATH = Path("data/synthetic/claims.json")


def generate_claims() -> list[ClaimDetail]:
    """Build all synthetic claims deterministically from ARCHETYPES."""
    claims: list[ClaimDetail] = []
    for idx, archetype in enumerate(ARCHETYPES, start=1):
        claim, _ctx = build_claim(archetype, idx)
        claims.append(claim)
    return claims


def coverage_report(claims: list[ClaimDetail]) -> dict[str, object]:
    """Return a dict with signal coverage + tier counts."""
    signal_counts: Counter[str] = Counter()
    for claim in claims:
        for alert in claim.alertas:
            signal_counts[alert.code] += 1

    tier_counts: Counter[str] = Counter(c.nivel.value for c in claims)

    # All 21 rule codes that must appear
    all_codes = [
        *[f"FS-{i:02d}" for i in range(1, 15)],
        *[f"RF-{i:02d}" for i in range(1, 8)],
    ]
    missing = [c for c in all_codes if signal_counts.get(c, 0) < 3]

    return {
        "total": len(claims),
        "tier_distribution": dict(tier_counts),
        "signal_counts": dict(signal_counts.most_common()),
        "codes_below_3_exemplars": missing,
    }


def generate_and_save(out_path: Path = _DATASET_PATH) -> list[ClaimDetail]:
    """Generate claims, save JSON + CSVs, return the claim list."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    claims = generate_claims()

    # Serialize to JSON
    payload = [c.model_dump(mode="json") for c in claims]
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Emit §2.8 CSVs
    export_csvs(claims, out_path.parent)

    return claims


def load_saved(path: Path = _DATASET_PATH) -> list[ClaimDetail] | None:
    """Load the committed JSON dataset. Returns None if the file is absent."""
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))

    loaded: list[ClaimDetail] = []
    for item in raw:
        # nivel may be serialized as a string; Pydantic handles coercion
        tier_val = item.get("nivel")
        if isinstance(tier_val, str) and tier_val in {t.value for t in Tier}:
            item["nivel"] = tier_val
        loaded.append(ClaimDetail.model_validate(item))
    return loaded
