#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = BASE_DIR / "data" / "benchmarks"
DEFAULT_DATASET = BENCHMARK_DIR / "combined_sales_v1.parquet"
DEFAULT_SPLIT_PARQUET = BENCHMARK_DIR / "combined_sales_v1_time_split.parquet"
DEFAULT_SPLIT_JSON = BENCHMARK_DIR / "combined_sales_v1_time_split.json"
DEFAULT_SPLIT_MD = BENCHMARK_DIR / "combined_sales_v1_time_split.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create source-aware time split artifacts for combined price modeling"
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_SPLIT_PARQUET)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_SPLIT_JSON)
    parser.add_argument("--summary-md", type=Path, default=DEFAULT_SPLIT_MD)
    parser.add_argument("--folds", type=int, default=3)
    return parser.parse_args()


def assign_source_time_group(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["event_date"] = pd.to_datetime(
        result["event_date"], utc=True, errors="coerce"
    )
    result["time_group"] = "unknown"

    treasury_mask = result["source_type"] == "treasury"
    listing_mask = result["source_type"] == "listing"

    result.loc[treasury_mask, "time_group"] = (
        result.loc[treasury_mask, "event_date"]
        .dt.tz_localize(None)
        .dt.to_period("Q")
        .astype(str)
    )
    result.loc[listing_mask, "time_group"] = (
        result.loc[listing_mask, "event_date"]
        .dt.tz_localize(None)
        .dt.floor("D")
        .astype(str)
    )
    result["time_group"] = result["time_group"].fillna("unknown")
    return result


def build_time_bin_map(groups: list[str], folds: int) -> dict[str, int]:
    if len(groups) == 0:
        return {}
    ordered_groups = sorted(groups)
    bins = np.array_split(
        np.array(ordered_groups, dtype=object), min(folds, len(ordered_groups))
    )
    mapping: dict[str, int] = {}
    for fold_index, bucket in enumerate(bins):
        for value in bucket.tolist():
            mapping[str(value)] = int(fold_index)
    return mapping


def build_assignments(df: pd.DataFrame, folds: int) -> tuple[pd.DataFrame, dict]:
    work_df = assign_source_time_group(df)
    assignments = work_df[
        [
            "row_id",
            "source_type",
            "source_site",
            "property_type",
            "district",
            "duplicate_group",
            "event_date",
            "time_group",
        ]
    ].copy()
    assignments["cv_fold"] = 0

    source_time_bins: dict[str, dict[str, int]] = {}
    source_time_groups: dict[str, list[str]] = {}
    missing_event_rows = 0

    for source_type, group_df in assignments.groupby("source_type"):
        valid_groups = [
            str(value)
            for value in group_df.loc[group_df["time_group"] != "unknown", "time_group"]
            .dropna()
            .unique()
            .tolist()
        ]
        mapping = build_time_bin_map(valid_groups, folds=folds)
        source_time_bins[str(source_type)] = mapping
        source_time_groups[str(source_type)] = sorted(valid_groups)

        source_mask = assignments["source_type"] == source_type
        assignments.loc[source_mask, "cv_fold"] = assignments.loc[
            source_mask, "time_group"
        ].map(lambda value: int(mapping.get(str(value), 0)))
        missing_event_rows += int(
            assignments.loc[source_mask, "time_group"].eq("unknown").sum()
        )

    assignments["cv_fold"] = assignments["cv_fold"].astype(int)

    fold_summary = (
        assignments.groupby("cv_fold")
        .agg(
            total_rows=("row_id", "size"),
            treasury_rows=(
                "source_type",
                lambda values: int((values == "treasury").sum()),
            ),
            listing_rows=(
                "source_type",
                lambda values: int((values == "listing").sum()),
            ),
            source_sites=("source_site", "nunique"),
            property_types=("property_type", "nunique"),
            districts=("district", "nunique"),
        )
        .reset_index()
        .sort_values("cv_fold")
    )

    time_group_summary = []
    for source_type in sorted(source_time_bins):
        mapping = source_time_bins[source_type]
        reverse: dict[int, list[str]] = {}
        for group_name, fold_index in mapping.items():
            reverse.setdefault(int(fold_index), []).append(group_name)
        for fold_index, group_names in sorted(reverse.items()):
            time_group_summary.append(
                {
                    "source_type": source_type,
                    "cv_fold": int(fold_index),
                    "time_groups": group_names,
                }
            )

    summary = {
        "dataset_version": str(df["dataset_version"].iloc[0]),
        "split_name": "source_aware_time_forward_chaining_v1",
        "folds": int(folds),
        "evaluation_mode": "forward_chaining",
        "row_count": int(len(assignments)),
        "evaluated_folds": list(range(1, int(assignments["cv_fold"].max()) + 1)),
        "source_time_groups": source_time_groups,
        "time_group_summary": time_group_summary,
        "missing_event_rows": int(missing_event_rows),
        "fold_summary": fold_summary.to_dict(orient="records"),
        "notes": [
            "Treasury rows are grouped by event_date quarter.",
            "Listing rows are grouped by event_date day using scraped snapshot date as the current proxy.",
            "Folds are chronological buckets within each source type and must be trained with forward chaining.",
            "Fold 0 is warm-up only and is not used for validation because it has no prior training window.",
        ],
    }
    return assignments, summary


def build_summary_markdown(summary: dict) -> str:
    lines = [
        "# Combined Source-Aware Time Split",
        "",
        f"- Dataset version: `{summary['dataset_version']}`",
        f"- Split name: `{summary['split_name']}`",
        f"- Evaluation mode: `{summary['evaluation_mode']}`",
        f"- Total rows: `{summary['row_count']}`",
        f"- Folds: `{summary['folds']}`",
        f"- Evaluated folds: `{summary['evaluated_folds']}`",
        f"- Missing event-date rows: `{summary['missing_event_rows']}`",
        "",
        "## Source Time Groups",
        "",
    ]
    for row in summary["time_group_summary"]:
        joined = ", ".join(f"`{value}`" for value in row["time_groups"])
        lines.append(f"- `{row['source_type']}` fold `{row['cv_fold']}`: {joined}")

    lines.extend(
        [
            "",
            "## Fold Summary",
            "",
            "| Fold | Total Rows | Treasury Rows | Listing Rows | Source Sites | Property Types | Districts |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summary["fold_summary"]:
        lines.append(
            f"| {row['cv_fold']} | {row['total_rows']} | {row['treasury_rows']} | {row['listing_rows']} | {row['source_sites']} | {row['property_types']} | {row['districts']} |"
        )

    lines.extend(["", "## Notes", ""])
    for note in summary["notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_md.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(args.dataset)
    assignments, summary = build_assignments(df, folds=args.folds)

    assignments.to_parquet(args.output, index=False)
    args.summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    args.summary_md.write_text(build_summary_markdown(summary), encoding="utf-8")

    logger.info("Saved time split assignments to %s", args.output)
    logger.info("Saved time split summary to %s", args.summary_json)


if __name__ == "__main__":
    main()
