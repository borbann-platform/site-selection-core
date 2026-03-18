"""Helpers for exposing explainability benchmark artifacts."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from src.services.price_prediction import MODELS_DIR, PredictorType


@dataclass(frozen=True)
class ExplainabilityTopFeature:
    """Single top-ranked SHAP feature from offline analysis."""

    feature: str
    importance: float


@dataclass(frozen=True)
class ExplainabilityEvidence:
    """Serializable explainability evidence for stakeholder-facing UI."""

    model_type: str
    runtime_explanation_method: str
    evidence_available: bool
    evaluation_complete: bool
    generated_at: str | None
    summary: str
    model_performance: dict[str, float] = field(default_factory=dict)
    explanation_metrics: dict[str, float] = field(default_factory=dict)
    top_shap_features: list[ExplainabilityTopFeature] = field(default_factory=list)
    missing_artifacts: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _artifact_directory(model_type: str) -> tuple[Path | None, str]:
    if model_type == PredictorType.BASELINE.value:
        return MODELS_DIR / "baseline", "global_gain"
    if model_type == PredictorType.BASELINE_HEX2VEC.value:
        return MODELS_DIR / "baseline_hex2vec", "global_gain"
    if model_type == PredictorType.HGT.value:
        return None, "attention_weight"
    return None, "unknown"


def _read_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _read_top_shap_features(
    path: Path, limit: int = 8
) -> list[ExplainabilityTopFeature]:
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            try:
                rows.append(
                    ExplainabilityTopFeature(
                        feature=row["feature"],
                        importance=float(row["importance"]),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
    return rows[:limit]


def _artifact_timestamp(paths: list[Path]) -> str | None:
    if not paths:
        return None
    latest = max(path.stat().st_mtime for path in paths)
    return datetime.fromtimestamp(latest, tz=UTC).isoformat()


def load_explainability_evidence(model_type: str) -> ExplainabilityEvidence:
    """Load offline explainability evidence for a given runtime model."""
    artifact_dir, runtime_method = _artifact_directory(model_type)
    if artifact_dir is None:
        return ExplainabilityEvidence(
            model_type=model_type,
            runtime_explanation_method=runtime_method,
            evidence_available=False,
            evaluation_complete=False,
            generated_at=None,
            summary="No offline explainability benchmark artifacts are registered for this model yet.",
            notes=[
                "This model does not yet expose benchmarked offline explainability artifacts in the UI.",
            ],
        )

    artifact_paths = {
        "cv_metrics": artifact_dir / "cv_metrics.json",
        "shap_importance": artifact_dir / "shap_importance.csv",
        "explainability_report": artifact_dir / "explainability_report.json",
        "feature_alignment": artifact_dir / "explainability_feature_alignment.csv",
    }
    existing_paths = [path for path in artifact_paths.values() if path.exists()]
    missing_artifacts = [
        name for name, path in artifact_paths.items() if not path.exists()
    ]

    if not existing_paths:
        return ExplainabilityEvidence(
            model_type=model_type,
            runtime_explanation_method=runtime_method,
            evidence_available=False,
            evaluation_complete=False,
            generated_at=None,
            summary="No explainability artifacts were found for the selected model.",
            missing_artifacts=missing_artifacts,
            notes=[
                "Run the baseline training pipeline again to regenerate SHAP and explainability evaluation artifacts.",
            ],
        )

    model_performance: dict[str, float] = {}
    cv_metrics_path = artifact_paths["cv_metrics"]
    if cv_metrics_path.exists():
        cv_metrics = _read_json(cv_metrics_path)
        avg = cv_metrics.get("avg", {}) if isinstance(cv_metrics, dict) else {}
        for metric in ["mae", "mape", "rmse", "r2"]:
            value = avg.get(metric)
            if isinstance(value, int | float):
                model_performance[metric] = float(value)

    notes = [
        "Runtime explanations currently use model signals in the UI; SHAP evidence comes from offline training artifacts.",
    ]

    explanation_metrics: dict[str, float] = {}
    explainability_report_path = artifact_paths["explainability_report"]
    if explainability_report_path.exists():
        report = _read_json(explainability_report_path)
        if isinstance(report, dict):
            for metric in [
                "shap_rank_correlation",
                "top5_overlap",
                "top10_overlap",
                "faithfulness_delta_top5",
                "faithfulness_delta_random",
                "faithfulness_lift",
                "expected_feature_coverage",
            ]:
                value = report.get(metric)
                if isinstance(value, int | float):
                    explanation_metrics[metric] = float(value)

            expected_found = report.get("expected_features_found", [])
            if isinstance(expected_found, list) and expected_found:
                notes.append(
                    "Expected domain drivers found in SHAP top features: "
                    + ", ".join(str(item) for item in expected_found)
                    + "."
                )

            expected_missing = report.get("expected_features_missing", [])
            if isinstance(expected_missing, list) and expected_missing:
                notes.append(
                    "Expected domain drivers still missing from SHAP top features: "
                    + ", ".join(str(item) for item in expected_missing)
                    + "."
                )

    top_shap_features: list[ExplainabilityTopFeature] = []
    shap_importance_path = artifact_paths["shap_importance"]
    if shap_importance_path.exists():
        top_shap_features = _read_top_shap_features(shap_importance_path)
    if explainability_report_path.exists():
        notes.append(
            "Faithfulness metrics compare prediction changes after perturbing top-ranked SHAP features versus random features."
        )
        faithfulness_lift = explanation_metrics.get("faithfulness_lift")
        if faithfulness_lift is not None:
            notes.append(
                "Top SHAP-ranked features cause about "
                f"{faithfulness_lift:.2f}x more prediction change than random features in the current benchmark."
            )

        rank_correlation = explanation_metrics.get("shap_rank_correlation")
        if rank_correlation is not None:
            notes.append(
                "SHAP and gain importance are "
                f"{'well aligned' if rank_correlation >= 0.8 else 'only partially aligned'} "
                f"in this run (rank correlation {rank_correlation:.2f})."
            )
    else:
        notes.append(
            "The explainability benchmark report is missing, so the evidence below is only partial."
        )

    summary = (
        "Explainability evidence is available from offline SHAP and benchmark artifacts."
        if explainability_report_path.exists()
        else "Partial explainability evidence is available from offline SHAP artifacts, but the benchmark report is missing."
    )

    return ExplainabilityEvidence(
        model_type=model_type,
        runtime_explanation_method=runtime_method,
        evidence_available=True,
        evaluation_complete=explainability_report_path.exists(),
        generated_at=_artifact_timestamp(existing_paths),
        summary=summary,
        model_performance=model_performance,
        explanation_metrics=explanation_metrics,
        top_shap_features=top_shap_features,
        missing_artifacts=missing_artifacts,
        notes=notes,
    )
