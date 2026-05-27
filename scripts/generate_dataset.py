"""CLI entry point: generate the synthetic dataset and print the coverage report.

Usage:
    uv run python scripts/generate_dataset.py

Output:
    - data/synthetic/claims.json       (pre-scored ClaimDetail list)
    - data/synthetic/siniestros.csv
    - data/synthetic/polizas.csv
    - data/synthetic/asegurados.csv
    - data/synthetic/beneficiarios_proveedores.csv
    - data/synthetic/documentos.csv
"""

import sys
from pathlib import Path

# Make the repo root importable when running via `uv run python scripts/…`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.use_cases.generate_dataset.runner import coverage_report, generate_and_save

if __name__ == "__main__":
    print("Generating synthetic dataset …")
    claims = generate_and_save()
    report = coverage_report(claims)

    print(f"\n{'─' * 50}")
    print(f"Total claims     : {report['total']}")
    print(f"Tier distribution: {report['tier_distribution']}")
    print("\nSignal coverage (code → exemplar count):")
    for code, count in sorted(report["signal_counts"].items()):  # type: ignore[union-attr]
        flag = "  ✓" if count >= 3 else "  ✗ BELOW 3"
        print(f"  {code:8s} {count:3d}{flag}")

    missing = report["codes_below_3_exemplars"]
    if missing:
        print(f"\nWARNING: codes below 3 exemplars → {missing}")
    else:
        print("\nAll 21 signals have ≥ 3 exemplars ✓")

    print("\nCSVs written to data/synthetic/")
    print("Done.")
