#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = BASE_DIR / "data" / "benchmarks"
DEFAULT_INPUT = BENCHMARK_DIR / "combined_sales_v1_legacy_salvage.parquet"
DEFAULT_OUTPUT = BENCHMARK_DIR / "listing_sales_v1_legacy_salvage.parquet"
DEFAULT_AUDIT_JSON = BENCHMARK_DIR / "listing_sales_v1_legacy_salvage_audit.json"
DEFAULT_AUDIT_MD = BENCHMARK_DIR / "listing_sales_v1_legacy_salvage_audit.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a listing-only benchmark dataset from a combined dataset"
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-json", type=Path, default=DEFAULT_AUDIT_JSON)
    parser.add_argument("--audit-md", type=Path, default=DEFAULT_AUDIT_MD)
    parser.add_argument(
        "--dataset-version",
        type=str,
        default="listing_sales_v1_legacy_salvage",
    )
    return parser.parse_args()


def build_audit(df: pd.DataFrame, dataset_version: str) -> dict[str, Any]:
    def missing_pct(column: str) -> float:
        if len(df) == 0:
            return 0.0
        return float(df[column].isna().mean() * 100)

    property_dist = (
        df.groupby(["source_site", "property_type"])
        .size()
        .reset_index(name="rows")
        .sort_values(["source_site", "rows"], ascending=[True, False])
    )

    report = {
        "dataset_version": dataset_version,
        "row_count_total": int(len(df)),
        "row_count_by_source": {
            source: int(count)
            for source, count in df["source_site"].value_counts().items()
        },
        "date_coverage_by_source": {
            source: {
                "min": str(group["event_date"].min()),
                "max": str(group["event_date"].max()),
            }
            for source, group in df.groupby("source_site")
        },
        "image_summary": {
            "has_image_rate_pct": float(df["has_images"].mean() * 100),
            "has_uploaded_image_rate_pct": float(
                df["has_uploaded_images"].mean() * 100
            ),
            "avg_image_count": float(df["image_count"].mean()),
            "avg_uploaded_image_count": float(df["uploaded_image_count"].mean()),
        },
        "missingness_pct": {
            "area_sqm": missing_pct("area_sqm"),
            "land_area": missing_pct("land_area"),
            "floors": missing_pct("floors"),
            "building_age": missing_pct("building_age"),
            "bedrooms": missing_pct("bedrooms"),
            "bathrooms": missing_pct("bathrooms"),
            "parking_spaces": missing_pct("parking_spaces"),
        },
        "duplicate_risk": {
            "exact_duplicates": int(df["duplicate_group"].value_counts().gt(1).sum()),
            "fuzzy_duplicate_keys": int(
                df["fuzzy_duplicate_key"].value_counts().gt(1).sum()
            ),
        },
        "property_type_distribution": property_dist.to_dict(orient="records"),
        "notes": [
            "This dataset is listing-only and is intended for source-segment benchmark analysis.",
            "It is derived from a combined benchmark artifact so schema stays aligned with the main mixed benchmark.",
            "Legacy listing rows may have missing event_date semantics and should not be treated as trustworthy time-benchmark rows.",
        ],
    }
    return report


def build_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# Listing-Only Dataset Audit",
        "",
        f"- Dataset version: `{audit['dataset_version']}`",
        f"- Total rows: `{audit['row_count_total']}`",
        "",
        "## Source Coverage",
        "",
    ]
    for source, count in audit["row_count_by_source"].items():
        lines.append(f"- `{source}`: `{count}` rows")

    lines.extend(
        [
            "",
            "## Date Coverage By Source",
            "",
        ]
    )
    for source, coverage in audit["date_coverage_by_source"].items():
        lines.append(f"- `{source}`: `{coverage['min']}` to `{coverage['max']}`")

    lines.extend(
        [
            "",
            "## Image Coverage",
            "",
            f"- Has image rate: `{audit['image_summary']['has_image_rate_pct']:.1f}%`",
            f"- Has uploaded image rate: `{audit['image_summary']['has_uploaded_image_rate_pct']:.1f}%`",
            f"- Avg image count: `{audit['image_summary']['avg_image_count']:.2f}`",
            f"- Avg uploaded image count: `{audit['image_summary']['avg_uploaded_image_count']:.2f}`",
            "",
            "## Missingness",
            "",
        ]
    )
    for field, value in audit["missingness_pct"].items():
        lines.append(f"- `{field}`: `{value:.1f}%`")

    lines.extend(
        [
            "",
            "## Duplicate Risk",
            "",
            f"- Exact duplicates: `{audit['duplicate_risk']['exact_duplicates']}`",
            f"- Fuzzy duplicate keys: `{audit['duplicate_risk']['fuzzy_duplicate_keys']}`",
            "",
            "## Notes",
            "",
        ]
    )
    for note in audit["notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.audit_json.parent.mkdir(parents=True, exist_ok=True)
    args.audit_md.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(args.input)
    listing_df = df.loc[df["source_type"] == "listing"].copy()
    listing_df["dataset_version"] = args.dataset_version
    listing_df = listing_df.sort_values(["event_date", "row_id"], na_position="last")
    listing_df = listing_df.reset_index(drop=True)

    audit = build_audit(listing_df, dataset_version=args.dataset_version)
    markdown = build_markdown(audit)

    listing_df.to_parquet(args.output, index=False)
    args.audit_json.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    args.audit_md.write_text(markdown, encoding="utf-8")

    logger.info("Saved listing-only dataset to %s", args.output)
    logger.info("Saved listing-only audit JSON to %s", args.audit_json)
    logger.info("Saved listing-only audit markdown to %s", args.audit_md)
    logger.info("Listing-only rows: %s", len(listing_df))


if __name__ == "__main__":
    main()
