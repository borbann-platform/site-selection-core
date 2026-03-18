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
DEFAULT_OUTPUT = BENCHMARK_DIR / "listing_image_embedding_manifest_v2.parquet"
DEFAULT_AUDIT_JSON = BENCHMARK_DIR / "listing_image_embedding_manifest_v2_audit.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build benchmark-aligned listing image manifest for embedding extraction"
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-json", type=Path, default=DEFAULT_AUDIT_JSON)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--prefer-uploaded",
        action="store_true",
        help="Prioritize uploaded images with object_uri; fallback to source_url",
    )
    parser.add_argument(
        "--drop-missing-dim",
        action="store_true",
        help="Drop rows where width or height is missing",
    )
    parser.add_argument(
        "--min-width",
        type=int,
        default=0,
        help="Optional minimum width threshold (0 disables)",
    )
    parser.add_argument(
        "--min-height",
        type=int,
        default=0,
        help="Optional minimum height threshold (0 disables)",
    )
    parser.add_argument(
        "--dedupe-checksum-per-listing",
        action="store_true",
        help="Keep one image per listing and checksum",
    )
    return parser.parse_args()


def load_listing_keys(dataset_path: Path) -> pd.DataFrame:
    df = pd.read_parquet(dataset_path)
    required = {
        "row_id",
        "source_type",
        "source_site",
        "source_listing_id",
        "event_date",
        "has_images",
        "has_uploaded_images",
        "image_count",
        "uploaded_image_count",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Dataset missing required columns: {missing}")

    listing_df = df.loc[df["source_type"] == "listing"].copy()
    listing_df["source_site"] = listing_df["source_site"].fillna("unknown").astype(str)
    listing_df["source_listing_id"] = listing_df["source_listing_id"].astype(str)
    listing_df = listing_df[
        [
            "row_id",
            "source_site",
            "source_listing_id",
            "event_date",
            "has_images",
            "has_uploaded_images",
            "image_count",
            "uploaded_image_count",
        ]
    ].drop_duplicates()
    return listing_df


def fetch_listing_mapping(listing_df: pd.DataFrame) -> pd.DataFrame:
    sources = sorted(
        {
            source
            for source in listing_df["source_site"].unique().tolist()
            if source not in {"legacy_bania", "unknown"}
        }
    )
    if not sources:
        return pd.DataFrame(columns=["source_site", "source_listing_id", "listing_id"])

    stmt = text(
        """
        SELECT
            id AS listing_id,
            source,
            source_listing_id,
            scraped_at
        FROM scraped_listings
        WHERE source IN :sources
        """
    ).bindparams(bindparam("sources", expanding=True))

    with engine.connect() as conn:
        rows = conn.execute(stmt, {"sources": sources}).mappings().all()
    if not rows:
        return pd.DataFrame(columns=["source_site", "source_listing_id", "listing_id"])

    scraped = pd.DataFrame([dict(row) for row in rows])
    scraped["source"] = scraped["source"].astype(str)
    scraped["source_listing_id"] = scraped["source_listing_id"].astype(str)

    keys = listing_df[["source_site", "source_listing_id"]].drop_duplicates()
    mapped = keys.merge(
        scraped,
        left_on=["source_site", "source_listing_id"],
        right_on=["source", "source_listing_id"],
        how="left",
    )
    return mapped[["source_site", "source_listing_id", "listing_id", "scraped_at"]]


def fetch_images(listing_ids: list[int]) -> pd.DataFrame:
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


def build_priority_order(
    images_df: pd.DataFrame, prefer_uploaded: bool
) -> pd.DataFrame:
    ranked = images_df.copy()
    ranked["fetch_status"] = ranked["fetch_status"].fillna("unknown").astype(str)

    if prefer_uploaded:
        ranked["status_rank"] = ranked["fetch_status"].map(
            {"uploaded": 0, "pending": 1, "failed": 2}
        )
        ranked["status_rank"] = ranked["status_rank"].fillna(3).astype(int)
    else:
        ranked["status_rank"] = 0

    ranked["is_primary_rank"] = (~ranked["is_primary"].fillna(False)).astype(int)
    ranked["image_order_rank"] = pd.to_numeric(
        ranked["image_order"], errors="coerce"
    ).fillna(999999)
    ranked["area_rank"] = -(
        pd.to_numeric(ranked["width"], errors="coerce").fillna(0)
        * pd.to_numeric(ranked["height"], errors="coerce").fillna(0)
    )

    ranked = ranked.sort_values(
        [
            "listing_id",
            "status_rank",
            "is_primary_rank",
            "image_order_rank",
            "area_rank",
            "id",
        ],
        ascending=[True, True, True, True, True, True],
    )
    return ranked


def apply_quality_filters(
    images_df: pd.DataFrame,
    drop_missing_dim: bool,
    min_width: int,
    min_height: int,
    dedupe_checksum_per_listing: bool,
) -> pd.DataFrame:
    result = images_df.copy()
    if result.empty:
        return result

    result["width"] = pd.to_numeric(result["width"], errors="coerce")
    result["height"] = pd.to_numeric(result["height"], errors="coerce")

    if drop_missing_dim:
        result = result.loc[result["width"].notna() & result["height"].notna()].copy()
    if min_width > 0:
        result = result.loc[
            result["width"].isna() | (result["width"] >= float(min_width))
        ].copy()
    if min_height > 0:
        result = result.loc[
            result["height"].isna() | (result["height"] >= float(min_height))
        ].copy()

    if dedupe_checksum_per_listing:
        result["checksum_sha256"] = result["checksum_sha256"].fillna("").astype(str)
        with_checksum = result["checksum_sha256"].str.len() > 0
        deduped = result.loc[with_checksum].drop_duplicates(
            subset=["listing_id", "checksum_sha256"],
            keep="first",
        )
        without_checksum = result.loc[~with_checksum]
        result = pd.concat([deduped, without_checksum], ignore_index=True)

    return result


def select_top_k_manifest(
    listing_df: pd.DataFrame,
    mapped_df: pd.DataFrame,
    images_df: pd.DataFrame,
    top_k: int,
    prefer_uploaded: bool,
) -> pd.DataFrame:
    work_df = listing_df.merge(
        mapped_df,
        on=["source_site", "source_listing_id"],
        how="left",
    )

    if images_df.empty:
        work_df["listing_id"] = work_df["listing_id"].astype("Int64")
        return work_df.assign(
            image_rank=pd.Series(dtype="Int64"),
            image_row_id=pd.Series(dtype="Int64"),
            fetch_status=pd.Series(dtype="object"),
            object_uri=pd.Series(dtype="object"),
            source_url=pd.Series(dtype="object"),
            checksum_sha256=pd.Series(dtype="object"),
            width=pd.Series(dtype="float"),
            height=pd.Series(dtype="float"),
            size_bytes=pd.Series(dtype="float"),
            mime_type=pd.Series(dtype="object"),
            image_selected=pd.Series(dtype="int"),
            image_selection_reason=pd.Series(dtype="object"),
            image_reference_uri=pd.Series(dtype="object"),
            selected_by_prefer_uploaded=pd.Series(dtype="int"),
        )

    ranked = build_priority_order(images_df, prefer_uploaded=prefer_uploaded)
    ranked["image_rank"] = ranked.groupby("listing_id").cumcount() + 1
    selected = ranked.loc[ranked["image_rank"] <= max(top_k, 1)].copy()

    selected = selected.rename(columns={"id": "image_row_id"})
    selected["image_selected"] = 1
    selected["image_selection_reason"] = "top_k_ranked"
    selected["selected_by_prefer_uploaded"] = int(prefer_uploaded)
    selected["image_reference_uri"] = selected["object_uri"].fillna(
        selected["source_url"]
    )

    merged = work_df.merge(selected, on="listing_id", how="left")

    merged["image_selected"] = merged["image_selected"].fillna(0).astype(int)
    merged["selected_by_prefer_uploaded"] = (
        merged["selected_by_prefer_uploaded"].fillna(int(prefer_uploaded)).astype(int)
    )
    merged["image_selection_reason"] = merged["image_selection_reason"].fillna(
        "no_image_candidate"
    )
    merged["image_reference_uri"] = merged["image_reference_uri"].fillna("")
    return merged


def build_audit(
    manifest_df: pd.DataFrame, top_k: int, prefer_uploaded: bool
) -> dict[str, Any]:
    listing_rows = int(manifest_df["row_id"].nunique())
    selected_rows = manifest_df.loc[manifest_df["image_selected"] == 1].copy()
    listings_with_selected = int(selected_rows["row_id"].nunique())
    uploaded_selected = int((selected_rows["fetch_status"] == "uploaded").sum())

    by_source = []
    unique_rows = manifest_df[
        ["row_id", "source_site", "has_uploaded_images"]
    ].drop_duplicates()
    selected_counts = (
        selected_rows.groupby(["row_id"]).size().rename("selected_count").reset_index()
        if not selected_rows.empty
        else pd.DataFrame(columns=["row_id", "selected_count"])
    )
    source_frame = unique_rows.merge(selected_counts, on="row_id", how="left")
    source_frame["selected_count"] = (
        source_frame["selected_count"].fillna(0).astype(int)
    )

    for source_site, group in source_frame.groupby("source_site"):
        rows = int(len(group))
        selected = int((group["selected_count"] > 0).sum())
        by_source.append(
            {
                "source_site": str(source_site),
                "rows": rows,
                "rows_with_selected_images": selected,
                "selected_coverage_pct": float((selected / rows) * 100.0)
                if rows > 0
                else 0.0,
                "avg_selected_images_per_row": float(group["selected_count"].mean()),
            }
        )
    by_source = sorted(by_source, key=lambda item: item["rows"], reverse=True)

    return {
        "manifest_version": "listing_image_embedding_manifest_v1",
        "top_k": int(top_k),
        "prefer_uploaded": bool(prefer_uploaded),
        "listing_rows": listing_rows,
        "manifest_rows": int(len(manifest_df)),
        "selected_image_rows": int(len(selected_rows)),
        "listings_with_selected_images": listings_with_selected,
        "selected_listing_coverage_pct": float(
            (listings_with_selected / listing_rows) * 100.0
        )
        if listing_rows > 0
        else 0.0,
        "selected_uploaded_rows": uploaded_selected,
        "selected_uploaded_rate_pct": float(
            (uploaded_selected / max(len(selected_rows), 1)) * 100.0
        ),
        "rows_with_uploaded_flag": int((unique_rows["has_uploaded_images"] == 1).sum()),
        "by_source": by_source,
        "notes": [
            "Manifest is benchmark-aligned and keyed by row_id/source/source_listing_id.",
            "When --prefer-uploaded is set, uploaded object_uri images are ranked ahead of pending/failed images.",
            "Rows without selected images remain in the manifest to preserve join stability and explicit fallback handling.",
        ],
    }


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.audit_json.parent.mkdir(parents=True, exist_ok=True)

    listing_df = load_listing_keys(args.dataset)
    mapped_df = fetch_listing_mapping(listing_df)
    listing_ids = (
        mapped_df["listing_id"].dropna().astype(int).drop_duplicates().tolist()
    )
    images_df = fetch_images(listing_ids)
    images_df = apply_quality_filters(
        images_df,
        drop_missing_dim=args.drop_missing_dim,
        min_width=max(args.min_width, 0),
        min_height=max(args.min_height, 0),
        dedupe_checksum_per_listing=args.dedupe_checksum_per_listing,
    )

    manifest_df = select_top_k_manifest(
        listing_df=listing_df,
        mapped_df=mapped_df,
        images_df=images_df,
        top_k=max(args.top_k, 1),
        prefer_uploaded=args.prefer_uploaded,
    )

    columns = [
        "row_id",
        "source_site",
        "source_listing_id",
        "event_date",
        "has_images",
        "has_uploaded_images",
        "image_count",
        "uploaded_image_count",
        "listing_id",
        "scraped_at",
        "image_rank",
        "image_row_id",
        "fetch_status",
        "is_primary",
        "image_order",
        "image_role",
        "object_uri",
        "source_url",
        "image_reference_uri",
        "checksum_sha256",
        "width",
        "height",
        "size_bytes",
        "mime_type",
        "image_selected",
        "image_selection_reason",
        "selected_by_prefer_uploaded",
    ]
    manifest_df = manifest_df[
        [column for column in columns if column in manifest_df.columns]
    ].copy()
    manifest_df.to_parquet(args.output, index=False)

    audit = build_audit(
        manifest_df=manifest_df,
        top_k=max(args.top_k, 1),
        prefer_uploaded=args.prefer_uploaded,
    )
    audit["quality_filters"] = {
        "drop_missing_dim": bool(args.drop_missing_dim),
        "min_width": int(max(args.min_width, 0)),
        "min_height": int(max(args.min_height, 0)),
        "dedupe_checksum_per_listing": bool(args.dedupe_checksum_per_listing),
    }
    args.audit_json.write_text(json.dumps(audit, indent=2), encoding="utf-8")

    logger.info("Saved listing image embedding manifest: %s", args.output)
    logger.info("Saved listing image embedding manifest audit: %s", args.audit_json)
    logger.info(
        "Manifest rows=%s, selected image rows=%s, listing coverage=%.1f%%",
        len(manifest_df),
        int((manifest_df["image_selected"] == 1).sum()),
        audit["selected_listing_coverage_pct"],
    )


if __name__ == "__main__":
    main()
