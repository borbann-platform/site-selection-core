#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Any

import pandas as pd
from sqlalchemy import bindparam, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config.database import engine


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = BASE_DIR / "data" / "benchmarks"
DEFAULT_DATASET = BENCHMARK_DIR / "combined_sales_v1.parquet"
DEFAULT_OUTPUT_JSON = BENCHMARK_DIR / "listing_image_quality_v1.json"
DEFAULT_OUTPUT_MD = BENCHMARK_DIR / "listing_image_quality_v1.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit listing image quality and coverage for benchmark rows"
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args()


def load_dataset(dataset_path: Path) -> pd.DataFrame:
    df = pd.read_parquet(dataset_path)
    required = {
        "row_id",
        "source_type",
        "source_site",
        "source_listing_id",
        "has_images",
        "image_count",
        "has_uploaded_images",
        "uploaded_image_count",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Dataset missing required columns: {missing}")
    listing_df = df.loc[df["source_type"] == "listing"].copy()
    listing_df["source_listing_id"] = listing_df["source_listing_id"].astype(str)
    listing_df["source_site"] = listing_df["source_site"].fillna("unknown").astype(str)
    return listing_df


def fetch_scraped_listing_map(listing_df: pd.DataFrame) -> pd.DataFrame:
    sources = sorted(
        {
            source
            for source in listing_df["source_site"].unique().tolist()
            if source not in {"legacy_bania", "unknown"}
        }
    )
    if not sources:
        return pd.DataFrame(columns=["listing_id", "source", "source_listing_id"])

    stmt = text(
        """
        SELECT
            id AS listing_id,
            source,
            source_listing_id,
            main_image_url,
            image_count,
            scraped_at
        FROM scraped_listings
        WHERE source IN :sources
        """
    ).bindparams(bindparam("sources", expanding=True))

    with engine.connect() as conn:
        rows = conn.execute(stmt, {"sources": sources}).mappings().all()
    if not rows:
        return pd.DataFrame(columns=["listing_id", "source", "source_listing_id"])

    scraped_df = pd.DataFrame([dict(row) for row in rows])
    scraped_df["source"] = scraped_df["source"].astype(str)
    scraped_df["source_listing_id"] = scraped_df["source_listing_id"].astype(str)

    key_df = listing_df[["source_site", "source_listing_id"]].drop_duplicates()
    merged = key_df.merge(
        scraped_df,
        left_on=["source_site", "source_listing_id"],
        right_on=["source", "source_listing_id"],
        how="left",
    )
    return merged


def fetch_image_rows(listing_ids: list[int]) -> pd.DataFrame:
    if not listing_ids:
        return pd.DataFrame(
            columns=[
                "id",
                "listing_id",
                "fetch_status",
                "is_primary",
                "image_order",
                "image_role",
                "object_uri",
                "source_url",
                "checksum_sha256",
                "width",
                "height",
                "size_bytes",
                "mime_type",
            ]
        )

    stmt = text(
        """
        SELECT
            id,
            listing_id,
            fetch_status,
            is_primary,
            image_order,
            image_role,
            object_uri,
            source_url,
            checksum_sha256,
            width,
            height,
            size_bytes,
            mime_type
        FROM scraped_listing_images
        WHERE listing_id IN :listing_ids
        """
    ).bindparams(bindparam("listing_ids", expanding=True))

    with engine.connect() as conn:
        rows = conn.execute(stmt, {"listing_ids": listing_ids}).mappings().all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(row) for row in rows])


def pct(numer: int, denom: int) -> float:
    if denom <= 0:
        return 0.0
    return float((numer / denom) * 100.0)


def build_report(listing_df: pd.DataFrame) -> dict[str, Any]:
    listing_map = fetch_scraped_listing_map(listing_df)
    matched_listing_ids = (
        listing_map["listing_id"].dropna().astype(int).drop_duplicates().tolist()
    )
    images_df = fetch_image_rows(matched_listing_ids)

    total_rows = int(len(listing_df))
    uploaded_rows = int((listing_df["has_uploaded_images"] == 1).sum())
    has_images_rows = int((listing_df["has_images"] == 1).sum())
    legacy_rows = int((listing_df["source_site"] == "legacy_bania").sum())
    mapped_rows = int(listing_map["listing_id"].notna().sum())

    summary: dict[str, Any] = {
        "listing_rows_total": total_rows,
        "listing_rows_with_image_flag": has_images_rows,
        "listing_rows_with_uploaded_images": uploaded_rows,
        "has_images_rate_pct": pct(has_images_rows, total_rows),
        "has_uploaded_images_rate_pct": pct(uploaded_rows, total_rows),
        "legacy_listing_rows": legacy_rows,
        "rows_mapped_to_scraped_listings": mapped_rows,
        "mapped_rows_rate_pct": pct(mapped_rows, max(total_rows - legacy_rows, 1)),
    }

    by_source = []
    for source_site, group in listing_df.groupby("source_site"):
        source_rows = int(len(group))
        source_uploaded = int((group["has_uploaded_images"] == 1).sum())
        source_has_images = int((group["has_images"] == 1).sum())
        by_source.append(
            {
                "source_site": str(source_site),
                "rows": source_rows,
                "has_images_rate_pct": pct(source_has_images, source_rows),
                "has_uploaded_images_rate_pct": pct(source_uploaded, source_rows),
                "avg_image_count": float(group["image_count"].fillna(0).mean()),
                "avg_uploaded_image_count": float(
                    group["uploaded_image_count"].fillna(0).mean()
                ),
            }
        )
    by_source = sorted(by_source, key=lambda item: item["rows"], reverse=True)

    image_quality: dict[str, Any] = {
        "image_rows_in_catalog": 0,
        "uploaded_image_rows": 0,
        "pending_image_rows": 0,
        "failed_image_rows": 0,
        "uploaded_rows_with_object_uri": 0,
        "uploaded_rows_missing_dimensions": 0,
        "uploaded_rows_small_lt_320": 0,
        "duplicate_checksum_rows": 0,
        "unique_checksum_count": 0,
        "listings_with_primary_uploaded": 0,
    }
    if not images_df.empty:
        images_df["fetch_status"] = (
            images_df["fetch_status"].fillna("unknown").astype(str)
        )
        uploaded_mask = images_df["fetch_status"] == "uploaded"
        pending_mask = images_df["fetch_status"] == "pending"
        failed_mask = images_df["fetch_status"] == "failed"

        uploaded_df = images_df.loc[uploaded_mask].copy()
        if not uploaded_df.empty:
            width = pd.to_numeric(uploaded_df["width"], errors="coerce")
            height = pd.to_numeric(uploaded_df["height"], errors="coerce")
            missing_dim_mask = width.isna() | height.isna()
            small_mask = (~missing_dim_mask) & ((width < 320) | (height < 320))
            checksum_counts = (
                uploaded_df["checksum_sha256"].dropna().value_counts()
                if "checksum_sha256" in uploaded_df.columns
                else pd.Series(dtype=int)
            )
            duplicate_checksum_rows = int(checksum_counts[checksum_counts > 1].sum())
            primary_uploaded = uploaded_df.loc[
                uploaded_df["is_primary"].fillna(False).astype(bool), "listing_id"
            ].dropna()
            listings_with_primary_uploaded = int(primary_uploaded.nunique())
        else:
            missing_dim_mask = pd.Series(dtype=bool)
            small_mask = pd.Series(dtype=bool)
            duplicate_checksum_rows = 0
            listings_with_primary_uploaded = 0

        image_quality = {
            "image_rows_in_catalog": int(len(images_df)),
            "uploaded_image_rows": int(uploaded_mask.sum()),
            "pending_image_rows": int(pending_mask.sum()),
            "failed_image_rows": int(failed_mask.sum()),
            "uploaded_rows_with_object_uri": int(
                uploaded_df["object_uri"].notna().sum() if not uploaded_df.empty else 0
            ),
            "uploaded_rows_missing_dimensions": int(missing_dim_mask.sum()),
            "uploaded_rows_small_lt_320": int(small_mask.sum()),
            "duplicate_checksum_rows": duplicate_checksum_rows,
            "unique_checksum_count": int(
                uploaded_df["checksum_sha256"].dropna().nunique()
                if not uploaded_df.empty
                else 0
            ),
            "listings_with_primary_uploaded": listings_with_primary_uploaded,
        }

    notes = [
        "This audit focuses on benchmark listing rows and the scraped image catalog linkage.",
        "legacy_bania rows currently do not map to scraped_listings and are expected to have zero uploaded-image linkage.",
        "Small-image and missing-dimension checks are lightweight quality heuristics for M1 readiness.",
    ]

    return {
        "summary": summary,
        "by_source": by_source,
        "image_catalog_quality": image_quality,
        "notes": notes,
    }


def build_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    q = report["image_catalog_quality"]

    lines = [
        "# Listing Image Quality Audit",
        "",
        "## Summary",
        "",
        f"- Listing rows total: `{s['listing_rows_total']}`",
        f"- Rows with images: `{s['listing_rows_with_image_flag']}` (`{s['has_images_rate_pct']:.1f}%`)",
        f"- Rows with uploaded images: `{s['listing_rows_with_uploaded_images']}` (`{s['has_uploaded_images_rate_pct']:.1f}%`)",
        f"- Legacy listing rows: `{s['legacy_listing_rows']}`",
        f"- Rows mapped to `scraped_listings`: `{s['rows_mapped_to_scraped_listings']}` (`{s['mapped_rows_rate_pct']:.1f}%` of non-legacy)",
        "",
        "## Source Coverage",
        "",
        "| Source | Rows | Has Images % | Has Uploaded % | Avg Image Count | Avg Uploaded Count |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["by_source"]:
        lines.append(
            f"| {row['source_site']} | {row['rows']} | {row['has_images_rate_pct']:.1f} | {row['has_uploaded_images_rate_pct']:.1f} | {row['avg_image_count']:.2f} | {row['avg_uploaded_image_count']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Image Catalog Quality",
            "",
            f"- Image rows in catalog: `{q['image_rows_in_catalog']}`",
            f"- Uploaded image rows: `{q['uploaded_image_rows']}`",
            f"- Pending image rows: `{q['pending_image_rows']}`",
            f"- Failed image rows: `{q['failed_image_rows']}`",
            f"- Uploaded rows with object URI: `{q['uploaded_rows_with_object_uri']}`",
            f"- Uploaded rows missing dimensions: `{q['uploaded_rows_missing_dimensions']}`",
            f"- Uploaded rows with min side < 320 px: `{q['uploaded_rows_small_lt_320']}`",
            f"- Duplicate-checksum uploaded rows: `{q['duplicate_checksum_rows']}`",
            f"- Unique uploaded checksums: `{q['unique_checksum_count']}`",
            f"- Listings with primary uploaded image: `{q['listings_with_primary_uploaded']}`",
            "",
            "## Notes",
            "",
        ]
    )
    for note in report["notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)

    listing_df = load_dataset(args.dataset)
    report = build_report(listing_df)

    args.output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    args.output_md.write_text(build_markdown(report), encoding="utf-8")

    logger.info("Saved listing image quality audit JSON: %s", args.output_json)
    logger.info("Saved listing image quality audit markdown: %s", args.output_md)


if __name__ == "__main__":
    main()
