"""Unit tests for explainability evaluation utilities."""

import numpy as np

from src.services.explanation_evaluation import (
    build_importance_table,
    compute_expected_feature_coverage,
    compute_perturbation_delta,
    compute_random_reference_delta,
    compute_rank_correlation,
    compute_topk_overlap,
)


def test_build_importance_table_sorts_descending():
    table = build_importance_table(["a", "b", "c"], np.array([0.2, 0.9, 0.5]), "score")

    assert table["feature"].tolist() == ["b", "c", "a"]


def test_compute_topk_overlap_matches_shared_features():
    overlap = compute_topk_overlap(["a", "b", "c"], ["b", "a", "d"], 2)
    assert overlap == 1.0


def test_compute_rank_correlation_handles_reordered_lists():
    correlation = compute_rank_correlation(["a", "b", "c", "d"], ["a", "c", "b", "d"])
    assert correlation < 1.0
    assert correlation > 0.0


def test_compute_expected_feature_coverage_reports_missing_items():
    coverage, found, missing = compute_expected_feature_coverage(
        ["building_area", "dist_to_bts", "poi_total"],
        ["building_area", "dist_to_bts", "dist_to_cbd_min"],
        3,
    )

    assert coverage == 2 / 3
    assert found == ["building_area", "dist_to_bts"]
    assert missing == ["dist_to_cbd_min"]


def test_compute_perturbation_delta_changes_predictions():
    X = np.array(
        [
            [10.0, 1.0, 0.0],
            [12.0, 0.5, 0.1],
            [9.0, 1.5, 0.0],
        ]
    )
    replacement_values = np.median(X, axis=0)

    def predict_fn(values: np.ndarray) -> np.ndarray:
        return values[:, 0] * 2.0 + values[:, 1]

    delta = compute_perturbation_delta(
        predict_fn,
        X,
        ["building_area", "dist_to_bts", "poi_total"],
        ["building_area", "dist_to_bts", "poi_total"],
        replacement_values,
        top_k=1,
        sample_size=3,
    )

    assert delta > 0


def test_random_reference_delta_is_non_negative():
    X = np.array(
        [
            [10.0, 1.0, 0.0],
            [12.0, 0.5, 0.1],
            [9.0, 1.5, 0.0],
        ]
    )
    replacement_values = np.median(X, axis=0)

    def predict_fn(values: np.ndarray) -> np.ndarray:
        return values[:, 0] * 2.0 + values[:, 1]

    delta = compute_random_reference_delta(
        predict_fn,
        X,
        ["building_area", "dist_to_bts", "poi_total"],
        replacement_values,
        top_k=1,
        sample_size=3,
        trials=4,
    )

    assert delta >= 0
