"""Unit tests for explainability artifact loading."""

import json

from src.services.explainability_artifacts import load_explainability_evidence


def test_load_explainability_evidence_for_hgt_returns_placeholder():
    evidence = load_explainability_evidence("hgt")

    assert evidence.model_type == "hgt"
    assert evidence.evidence_available is False
    assert evidence.runtime_explanation_method == "attention_weight"


def test_load_explainability_evidence_reads_artifacts(tmp_path, monkeypatch):
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir(parents=True)
    (baseline_dir / "cv_metrics.json").write_text(
        json.dumps({"avg": {"mae": 12345.0, "r2": 0.88}})
    )
    (baseline_dir / "explainability_report.json").write_text(
        json.dumps(
            {
                "shap_rank_correlation": 0.9,
                "faithfulness_lift": 1.7,
                "top5_overlap": 0.8,
                "expected_feature_coverage": 1.0,
            }
        )
    )
    (baseline_dir / "shap_importance.csv").write_text(
        "feature,importance\nbuilding_area,0.4\ndist_to_bts,0.2\n"
    )
    (baseline_dir / "explainability_feature_alignment.csv").write_text(
        "feature,mean_abs_shap,gain_importance\nbuilding_area,0.4,12.0\n"
    )

    from src.services import explainability_artifacts as module

    monkeypatch.setattr(module, "MODELS_DIR", tmp_path)

    evidence = load_explainability_evidence("baseline")

    assert evidence.evidence_available is True
    assert evidence.evaluation_complete is True
    assert evidence.model_performance["mae"] == 12345.0
    assert evidence.explanation_metrics["faithfulness_lift"] == 1.7
    assert evidence.top_shap_features[0].feature == "building_area"
