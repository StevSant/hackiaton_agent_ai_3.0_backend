"""Build the training matrices ``X``, ``y``, and the parallel ``claim_ids`` list.

Loads the 62-archetype JSON, perturbs each into ``VARIANTS_PER_ARCHETYPE``
variants, re-scores every variant via the rules engine so the label is
recomputed (and thus moves when a perturbation crosses a threshold), and
materializes ``X`` in the canonical feature order from ``FEATURE_NAMES``.

The output is a single ``TrainingDataset`` value object — callers don't need
to know anything about how it was assembled.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.domain.ml import FEATURE_NAMES, extract_features
from app.domain.rules.context import RuleContext
from app.schemas.claim import ClaimDetail
from app.schemas.risk import Tier
from app.use_cases.generate_dataset.runner import load_saved
from app.use_cases.score_claim import score_claim
from notebooks._training.paths import SYNTHETIC_CLAIMS_JSON
from notebooks._training.perturbations import VARIANTS_PER_ARCHETYPE, perturb_claim


@dataclass(slots=True)
class TrainingDataset:
    X: np.ndarray  # shape (N, len(FEATURE_NAMES)), float64
    y: np.ndarray  # shape (N,), int8 — 1 = rojo (etiqueta_fraude_simulada)
    claim_ids: list[str]  # length N, parallel to X / y
    feature_names: list[str]  # == list(FEATURE_NAMES)

    @property
    def positive_rate(self) -> float:
        return float(self.y.mean()) if len(self.y) else 0.0


def _label_from_tier(tier: Tier) -> int:
    """Match the ``claim_to_row`` convention: 1 iff tier == rojo."""
    return 1 if tier == Tier.rojo else 0


def _score_and_label(claim: ClaimDetail) -> tuple[ClaimDetail, int]:
    """Re-score a perturbed claim via the rules engine and derive the label."""
    ctx = RuleContext.from_claim(claim)
    risk = score_claim(claim, ctx=ctx)
    relabeled = claim.model_copy(update={"score": risk.score, "nivel": risk.tier})
    return relabeled, _label_from_tier(risk.tier)


def build_dataset(*, variants_per_archetype: int = VARIANTS_PER_ARCHETYPE) -> TrainingDataset:
    """Load + perturb + re-score → ``TrainingDataset``.

    The original (variant_idx=0) carries the archetype's baked label. Perturbed
    variants get re-labeled from the freshly computed tier so the label moves
    when the perturbation crosses a threshold.
    """
    claims = load_saved(SYNTHETIC_CLAIMS_JSON)
    if not claims:
        raise FileNotFoundError(
            f"Cannot train without {SYNTHETIC_CLAIMS_JSON}. "
            "Run `uv run app generate-dataset` (or the equivalent) first."
        )

    rows: list[list[float]] = []
    labels: list[int] = []
    ids: list[str] = []
    feature_order = list(FEATURE_NAMES)

    for parent in claims:
        # Variant 0 = original claim; keep its baked tier as the label.
        original_label = _label_from_tier(parent.nivel)
        original_ctx = RuleContext.from_claim(parent)
        original_features = extract_features(parent, original_ctx)
        rows.append([original_features[name] for name in feature_order])
        labels.append(original_label)
        ids.append(parent.id)

        # Perturbed variants — re-score so the label tracks the new tier.
        for v in range(1, variants_per_archetype):
            perturbed = perturb_claim(parent, v)
            relabeled, label = _score_and_label(perturbed)
            ctx = RuleContext.from_claim(relabeled)
            features = extract_features(relabeled, ctx)
            rows.append([features[name] for name in feature_order])
            labels.append(label)
            ids.append(f"{parent.id}#v{v}")

    return TrainingDataset(
        X=np.asarray(rows, dtype=np.float64),
        y=np.asarray(labels, dtype=np.int8),
        claim_ids=ids,
        feature_names=feature_order,
    )
