"""Synthetic dataset generation — public surface.

``generate_and_save`` produces the JSON dataset + §2.8 CSVs and writes them
under ``data/synthetic/``. The runtime path no longer serves claims from
these files — they are ingested into the database via ``load_dataset`` and
the DB is the source of truth.
"""

from app.use_cases.generate_dataset.runner import generate_and_save

__all__ = ["generate_and_save"]
