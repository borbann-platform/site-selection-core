#!/usr/bin/env python3
"""
Export MLflow leaderboard for multi-model experiment comparison.

Usage:
    python -m scripts.export_experiment_leaderboard --experiment-name property-valuation-baseline
    python -m scripts.export_experiment_leaderboard --all-experiments --metric test_mape --mode min
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import mlflow
from mlflow.entities import Run
from mlflow.tracking import MlflowClient

from src.config.mlflow_config import MLFLOW_TRACKING_URI

DEFAULT_COLUMNS = [
    "run_id",
    "experiment_name",
    "status",
    "selected_metric",
    "cv_mape_mean",
    "cv_r2_mean",
    "test_mape",
    "test_r2",
    "cold_mape",
    "cold_r2",
    "model_family",
    "model_variant",
    "feature_set",
    "dataset_version",
    "split_seed",
    "git_sha",
    "git_branch",
    "train_timestamp_utc",
    "start_time_utc",
    "duration_seconds",
]


def _to_iso(ms: int | None) -> str:
    if not ms:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=UTC).replace(microsecond=0).isoformat()


def _duration_seconds(run: Run) -> float | None:
    start = run.info.start_time
    end = run.info.end_time
    if start is None or end is None:
        return None
    return round((end - start) / 1000, 2)


def _extract_row(
    run: Run, experiment_name: str, selected_metric: str
) -> dict[str, str]:
    metrics = run.data.metrics
    params = run.data.params
    tags = run.data.tags

    metric_value = metrics.get(selected_metric)
    row: dict[str, str] = {
        "run_id": run.info.run_id,
        "experiment_name": experiment_name,
        "status": run.info.status,
        "selected_metric": "" if metric_value is None else str(metric_value),
        "cv_mape_mean": str(metrics.get("cv_mape_mean", "")),
        "cv_r2_mean": str(metrics.get("cv_r2_mean", "")),
        "test_mape": str(metrics.get("test_mape", "")),
        "test_r2": str(metrics.get("test_r2", "")),
        "cold_mape": str(metrics.get("cold_mape", "")),
        "cold_r2": str(metrics.get("cold_r2", "")),
        "model_family": tags.get("model_family", ""),
        "model_variant": tags.get("model_variant", ""),
        "feature_set": tags.get("feature_set", params.get("feature_set", "")),
        "dataset_version": tags.get(
            "dataset_version", params.get("dataset_version", "")
        ),
        "split_seed": tags.get("split_seed", params.get("split_seed", "")),
        "git_sha": tags.get("git_sha", ""),
        "git_branch": tags.get("git_branch", ""),
        "train_timestamp_utc": tags.get("train_timestamp_utc", ""),
        "start_time_utc": _to_iso(run.info.start_time),
        "duration_seconds": "",
    }
    duration = _duration_seconds(run)
    if duration is not None:
        row["duration_seconds"] = str(duration)
    return row


def _sort_rows(rows: list[dict[str, str]], mode: str) -> list[dict[str, str]]:
    reverse = mode == "max"

    def key_fn(row: dict[str, str]) -> tuple[int, float]:
        value = row.get("selected_metric", "")
        if value in {"", "None"}:
            return (1, 0.0)
        return (0, float(value))

    ordered = sorted(rows, key=key_fn, reverse=reverse)
    # Always push rows without selected metric to the end.
    with_metric = [r for r in ordered if r.get("selected_metric") not in {"", "None"}]
    without_metric = [r for r in ordered if r.get("selected_metric") in {"", "None"}]
    return with_metric + without_metric


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(
    path: Path, rows: list[dict[str, str]], metadata: dict[str, str]
) -> None:
    payload = {
        "metadata": metadata,
        "rows": rows,
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


def _write_markdown(path: Path, rows: list[dict[str, str]], top_n: int = 20) -> None:
    subset = rows[:top_n]
    lines = [
        "| rank | run_id | selected_metric | model_family | model_variant | feature_set | dataset_version |",
        "|---:|---|---:|---|---|---|---|",
    ]
    for idx, row in enumerate(subset, start=1):
        lines.append(
            "| {rank} | {run_id} | {metric} | {family} | {variant} | {feature_set} | {dataset} |".format(
                rank=idx,
                run_id=row["run_id"],
                metric=row["selected_metric"] or "-",
                family=row["model_family"] or "-",
                variant=row["model_variant"] or "-",
                feature_set=row["feature_set"] or "-",
                dataset=row["dataset_version"] or "-",
            )
        )
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export MLflow experiment leaderboard")
    parser.add_argument(
        "--experiment-name",
        default=None,
        help="Single experiment name to export (omit with --all-experiments)",
    )
    parser.add_argument(
        "--all-experiments",
        action="store_true",
        help="Export runs from all active experiments",
    )
    parser.add_argument(
        "--metric",
        default="cv_mape_mean",
        help="Metric used for ranking (e.g., cv_mape_mean, test_mape, test_r2)",
    )
    parser.add_argument(
        "--mode",
        choices=["min", "max"],
        default="min",
        help="Sort direction for selected metric",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=200,
        help="Maximum runs to fetch per search",
    )
    parser.add_argument(
        "--include-failed",
        action="store_true",
        help="Include FAILED/KILLED runs in the leaderboard",
    )
    parser.add_argument(
        "--output-dir",
        default="reports/mlops",
        help="Output directory for leaderboard files",
    )
    parser.add_argument(
        "--output-prefix",
        default="leaderboard",
        help="File prefix for exported leaderboard artifacts",
    )
    parser.add_argument(
        "--tracking-uri",
        default=MLFLOW_TRACKING_URI,
        help="MLflow tracking URI",
    )
    args = parser.parse_args()

    mlflow.set_tracking_uri(args.tracking_uri)
    client = MlflowClient(tracking_uri=args.tracking_uri)

    if args.all_experiments:
        experiments = client.search_experiments()
    else:
        if not args.experiment_name:
            raise ValueError(
                "--experiment-name is required when --all-experiments is not set"
            )
        experiment = client.get_experiment_by_name(args.experiment_name)
        if experiment is None:
            raise ValueError(f"Experiment not found: {args.experiment_name}")
        experiments = [experiment]

    experiment_ids = [exp.experiment_id for exp in experiments]
    experiment_name_map = {exp.experiment_id: exp.name for exp in experiments}

    runs = client.search_runs(
        experiment_ids=experiment_ids,
        order_by=["attributes.start_time DESC"],
        max_results=args.max_runs,
    )

    rows: list[dict[str, str]] = []
    for run in runs:
        if not args.include_failed and run.info.status != "FINISHED":
            continue
        exp_name = experiment_name_map.get(
            run.info.experiment_id, run.info.experiment_id
        )
        rows.append(_extract_row(run, exp_name, args.metric))

    sorted_rows = _sort_rows(rows, args.mode)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    csv_path = output_dir / f"{args.output_prefix}_{ts}.csv"
    json_path = output_dir / f"{args.output_prefix}_{ts}.json"
    md_path = output_dir / f"{args.output_prefix}_{ts}.md"

    _write_csv(csv_path, sorted_rows, DEFAULT_COLUMNS)
    _write_json(
        json_path,
        sorted_rows,
        metadata={
            "tracking_uri": args.tracking_uri,
            "metric": args.metric,
            "mode": args.mode,
            "experiments": ",".join([e.name for e in experiments]),
            "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        },
    )
    _write_markdown(md_path, sorted_rows)

    print(f"Exported leaderboard rows: {len(sorted_rows)}")
    print(f"- CSV: {csv_path}")
    print(f"- JSON: {json_path}")
    print(f"- Markdown: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
