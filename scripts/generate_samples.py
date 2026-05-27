"""CLI entry point: regenerate the per-variant sample files under ``data/samples/``.

Usage:
    uv run python scripts/generate_samples.py

Output:
    - data/samples/claims.dev.json    (~40 claims)
    - data/samples/claims.test.json   (~80 claims)
    - data/samples/claims.prod.json   (~180 claims)
    - data/samples/claims.sample.csv  (first 10 rows of dev variant)
"""

import sys
from pathlib import Path

# Make the repo root importable when running via `uv run python scripts/…`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.use_cases.generate_dataset._samples import generate_samples

if __name__ == "__main__":
    print("Regenerating sample files …")
    counts = generate_samples()
    for name, n in counts.items():
        print(f"  {name:30s} {n} rows")
    print("\nDone — data/samples/ refreshed.")
