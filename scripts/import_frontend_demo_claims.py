"""Convert the frontend mock claims into a backend `ClaimDetail` JSON seed.

Source : `../hackiaton_agent_ai_3.0_frontend/src/app/features/claims/services/claims-mock.data.ts`
Output : `data/synthetic/demo_claims.json`

The frontend keeps the demo claims (the 18 cases the analyst sees on the
dashboard, including SIN-2026-08412) as a hand-authored TypeScript array. This
script extracts that array, translates the TS literal to JSON, derives `nivel`
from `score`, validates each entry through pydantic, and writes a JSON file the
backend's `SyntheticClaimQueries` loader picks up at startup.

Run once after editing the TS mocks::

    uv run python scripts/import_frontend_demo_claims.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
TS_PATH = (
    REPO_ROOT
    / "hackiaton_agent_ai_3.0_frontend"
    / "src"
    / "app"
    / "features"
    / "claims"
    / "services"
    / "claims-mock.data.ts"
)
JSON_OUT_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "synthetic" / "demo_claims.json"
)


def _tier_for_score(score: int) -> str:
    if score >= 76:
        return "rojo"
    if score >= 41:
        return "amarillo"
    return "verde"


def _extract_raw_literal(ts_source: str) -> str:
    """Return just the `[ ... ]` body of the `RAW` declaration."""
    start = ts_source.find("const RAW")
    if start == -1:
        raise RuntimeError("Could not locate `const RAW` in TS source")
    assign = ts_source.index("=", start)
    bracket_open = ts_source.index("[", assign)
    depth = 0
    for idx in range(bracket_open, len(ts_source)):
        ch = ts_source[idx]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return ts_source[bracket_open : idx + 1]
    raise RuntimeError("Unbalanced brackets in RAW literal")


def _ts_array_to_json(literal: str) -> str:
    """Heuristic TS-object-literal → JSON converter.

    Assumptions verified against the source file:
      - Strings use single quotes; no embedded apostrophes inside string bodies.
      - Object keys are bare identifiers (no quoted keys, no computed keys).
      - No spreads, no method shorthand, no template strings inside the RAW array.
    """
    text = literal
    text = re.sub(r"([{,]\s*)([A-Za-z_][\w]*)\s*:", r'\1"\2":', text)
    text = re.sub(r"'((?:[^'\\]|\\.)*)'", r'"\1"', text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return text


def _enrich(entry: dict) -> dict:
    entry = dict(entry)
    entry["nivel"] = _tier_for_score(int(entry["score"]))
    return entry


def main() -> int:
    if not TS_PATH.exists():
        print(f"ERR: {TS_PATH} not found", file=sys.stderr)
        return 1

    from app.schemas.claim import ClaimDetail

    ts_source = TS_PATH.read_text(encoding="utf-8")
    raw_literal = _extract_raw_literal(ts_source)
    as_json = _ts_array_to_json(raw_literal)

    try:
        entries = json.loads(as_json)
    except json.JSONDecodeError as exc:
        print(f"ERR: JSON parse failed at line {exc.lineno}: {exc.msg}", file=sys.stderr)
        return 2

    validated: list[dict] = []
    for idx, entry in enumerate(entries):
        enriched = _enrich(entry)
        try:
            claim = ClaimDetail.model_validate(enriched)
        except ValidationError as exc:
            print(f"ERR: entry #{idx} ({entry.get('id', '?')}) failed: {exc}", file=sys.stderr)
            return 3
        validated.append(claim.model_dump(mode="json"))

    JSON_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT_PATH.write_text(
        json.dumps(validated, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(validated)} demo claims to {JSON_OUT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
