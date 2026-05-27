"""Synthetic dataset generation — public surface.

``generate_and_save`` produces the JSON dataset + §2.8 CSVs and writes them
under ``data/synthetic/``.  ``SyntheticClaimQueries`` is the ``ClaimQueries``
implementation that loads and serves the pre-scored dataset.
"""

from app.use_cases.generate_dataset.loader import SyntheticClaimQueries
from app.use_cases.generate_dataset.runner import generate_and_save

__all__ = ["SyntheticClaimQueries", "generate_and_save"]
