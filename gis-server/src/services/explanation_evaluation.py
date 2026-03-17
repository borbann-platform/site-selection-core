"""Utilities for benchmarking explainability outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


class PredictorFn(Protocol):
    """Callable prediction interface used by perturbation checks."""

    def __call__(self, features: np.ndarray) -> np.ndarray: ...


@dataclass(frozen=True)
class GlobalExplainabilityReport:
    """Summary of global explainability evaluation metrics."""

    shap_rank_correlation: float
    top5_overlap: float
    top10_overlap: float
    faithfulness_delta_top5: float
    faithfulness_delta_random: float
    faithfulness_lift: float
    expected_feature_coverage: float
    expected_features_found: list[str]
    expected_features_missing: list[str]


def build_importance_table(
    feature_names: list[str], scores: np.ndarray, score_name: str
) -> pd.DataFrame:
    """Create a sorted feature-importance table."""
    if len(feature_names) != len(scores):
        raise ValueError("feature_names and scores must have the same length")

    table = pd.DataFrame(
        {
            "feature": feature_names,
            score_name: np.asarray(scores, dtype=float),
        }
    )
    return table.sort_values(score_name, ascending=False).reset_index(drop=True)


def compute_topk_overlap(
    reference_features: list[str], candidate_features: list[str], k: int
) -> float:
    """Return the fraction of overlapping features in the top-k rankings."""
    if k <= 0:
        raise ValueError("k must be positive")

    ref = set(reference_features[:k])
    cand = set(candidate_features[:k])
    if not ref:
        return 0.0
    return len(ref & cand) / len(ref)


def compute_rank_correlation(
    reference_features: list[str], candidate_features: list[str]
) -> float:
    """Compute Spearman correlation across two ranked feature lists."""
    shared = [
        feature for feature in reference_features if feature in set(candidate_features)
    ]
    if len(shared) < 2:
        return 0.0

    reference_ranks = [reference_features.index(feature) for feature in shared]
    candidate_ranks = [candidate_features.index(feature) for feature in shared]
    corr, _ = spearmanr(reference_ranks, candidate_ranks)
    if corr is None or np.isnan(corr):
        return 0.0
    return float(corr)


def compute_expected_feature_coverage(
    ranked_features: list[str], expected_features: list[str], k: int
) -> tuple[float, list[str], list[str]]:
    """Check whether expected domain features appear in the top-k list."""
    top_features = ranked_features[:k]
    found = [feature for feature in expected_features if feature in top_features]
    missing = [feature for feature in expected_features if feature not in top_features]
    coverage = len(found) / len(expected_features) if expected_features else 0.0
    return coverage, found, missing


def compute_perturbation_delta(
    predict_fn: PredictorFn,
    X: np.ndarray,
    feature_names: list[str],
    ranked_features: list[str],
    replacement_values: np.ndarray,
    *,
    top_k: int,
    sample_size: int,
    random_state: int = 42,
) -> float:
    """Measure prediction change after replacing top-ranked features."""
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")

    row_count = min(sample_size, len(X))
    rng = np.random.default_rng(random_state)
    row_indices = rng.choice(len(X), size=row_count, replace=False)
    X_sample = np.asarray(X[row_indices], dtype=float)
    baseline_predictions = np.asarray(predict_fn(X_sample), dtype=float)

    feature_lookup = {feature: idx for idx, feature in enumerate(feature_names)}
    target_indices = [
        feature_lookup[feature]
        for feature in ranked_features[:top_k]
        if feature in feature_lookup
    ]
    if not target_indices:
        return 0.0

    X_perturbed = X_sample.copy()
    X_perturbed[:, target_indices] = replacement_values[target_indices]
    perturbed_predictions = np.asarray(predict_fn(X_perturbed), dtype=float)
    return float(np.mean(np.abs(perturbed_predictions - baseline_predictions)))


def compute_random_reference_delta(
    predict_fn: PredictorFn,
    X: np.ndarray,
    feature_names: list[str],
    replacement_values: np.ndarray,
    *,
    top_k: int,
    sample_size: int,
    trials: int,
    random_state: int = 42,
) -> float:
    """Estimate a random-feature perturbation baseline."""
    if trials <= 0:
        raise ValueError("trials must be positive")

    rng = np.random.default_rng(random_state)
    deltas: list[float] = []
    for _ in range(trials):
        shuffled = list(feature_names)
        rng.shuffle(shuffled)
        deltas.append(
            compute_perturbation_delta(
                predict_fn,
                X,
                feature_names,
                shuffled,
                replacement_values,
                top_k=top_k,
                sample_size=sample_size,
                random_state=int(rng.integers(0, 1_000_000)),
            )
        )
    return float(np.mean(deltas))
