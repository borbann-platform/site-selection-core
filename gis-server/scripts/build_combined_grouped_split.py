#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

import h3
import pandas as pd
from sklearn.model_selection import GroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = BASE_DIR / "data" / "benchmarks"
DEFAULT_DATASET = BENCHMARK_DIR / "combined_sales_v1.parquet"
DEFAULT_SPLIT_PARQUET = BENCHMARK_DIR / "combined_sales_v1_grouped_cv_splits.parquet"
DEFAULT_SPLIT_JSON = BENCHMARK_DIR / "combined_sales_v1_grouped_cv_splits.json"
DEFAULT_SPLIT_MD = BENCHMARK_DIR / "combined_sales_v1_grouped_cv_splits.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create strict grouped CV split artifacts for combined price modeling"
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_SPLIT_PARQUET)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_SPLIT_JSON)
    parser.add_argument("--summary-md", type=Path, default=DEFAULT_SPLIT_MD)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--h3-resolution", type=int, default=7)
    return parser.parse_args()


def add_group_columns(df: pd.DataFrame, h3_resolution: int) -> pd.DataFrame:
    result = df.copy()
    result["spatial_group"] = result.apply(
        lambda row: h3.latlng_to_cell(
            float(row["lat"]), float(row["lon"]), h3_resolution
        ),
        axis=1,
    )
    result["strict_group"] = (
        result["property_type"].fillna("unknown").astype(str)
        + "|"
        + result["spatial_group"].astype(str)
    )
    return result


def build_assignments(df: pd.DataFrame, folds: int) -> tuple[pd.DataFrame, dict]:
    assignments = df[
        [
            "row_id",
            "source_type",
            "source_site",
            "property_type",
            "district",
            "duplicate_group",
            "spatial_group",
            "strict_group",
        ]
    ].copy()
    assignments["cv_fold"] = -1
    gkf = GroupKFold(n_splits=folds)
    dummy_x = pd.DataFrame({"row_id": assignments["row_id"]})
    for fold_idx, (_, val_idx) in enumerate(
        gkf.split(dummy_x, groups=assignments["strict_group"])
    ):
        assignments.iloc[val_idx, assignments.columns.get_loc("cv_fold")] = fold_idx
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
            strict_groups=("strict_group", "nunique"),
            spatial_groups=("spatial_group", "nunique"),
            property_types=("property_type", "nunique"),
            districts=("district", "nunique"),
        )
        .reset_index()
        .sort_values("cv_fold")
    )

    summary = {
        "dataset_version": str(df["dataset_version"].iloc[0]),
        "split_name": "grouped_cv_h3_res7_property_type",
        "folds": folds,
        "group_definition": "property_type + h3_res7 spatial cell",
        "row_count": int(len(df)),
        "strict_group_count": int(assignments["strict_group"].nunique()),
        "spatial_group_count": int(assignments["spatial_group"].nunique()),
        "duplicate_group_count": int(assignments["duplicate_group"].nunique()),
        "fold_summary": fold_summary.to_dict(orient="records"),
    }
    return assignments, summary


def build_summary_markdown(summary: dict) -> str:
    lines = [
        "# Combined Grouped CV Split",
        "",
        f"- Dataset version: `{summary['dataset_version']}`",
        f"- Split name: `{summary['split_name']}`",
        f"- Group definition: `{summary['group_definition']}`",
        f"- Total rows: `{summary['row_count']}`",
        f"- Strict groups: `{summary['strict_group_count']}`",
        f"- Spatial groups: `{summary['spatial_group_count']}`",
        f"- Duplicate groups: `{summary['duplicate_group_count']}`",
        "",
        "## Fold Summary",
        "",
        "| Fold | Total Rows | Treasury Rows | Listing Rows | Strict Groups | Spatial Groups | Property Types | Districts |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["fold_summary"]:
        lines.append(
            f"| {row['cv_fold']} | {row['total_rows']} | {row['treasury_rows']} | {row['listing_rows']} | {row['strict_groups']} | {row['spatial_groups']} | {row['property_types']} | {row['districts']} |"
        )
    lines.append("")
    lines.append(
        "This split is stricter than the earlier hash-based grouping because all rows from the same `property_type + h3_res7` cluster stay in one fold."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_md.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(args.dataset)
    df = add_group_columns(df, h3_resolution=args.h3_resolution)
    assignments, summary = build_assignments(df, folds=args.folds)

    assignments.to_parquet(args.output, index=False)
    args.summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    args.summary_md.write_text(build_summary_markdown(summary), encoding="utf-8")

    logger.info("Saved split assignments to %s", args.output)
    logger.info("Saved split summary to %s", args.summary_json)


if __name__ == "__main__":
    main()
