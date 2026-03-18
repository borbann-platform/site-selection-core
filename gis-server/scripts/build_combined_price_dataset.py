#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from pathlib import Path
import sys
from typing import Any

import h3
import numpy as np
import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config.database import engine

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
BENCHMARK_DIR = DATA_DIR / "benchmarks"
SCRAPED_JSONL_PATH = DATA_DIR / "scraped" / "baania_bangkok_houses.jsonl"
DEFAULT_OUTPUT_PATH = BENCHMARK_DIR / "combined_sales_v1.parquet"
DEFAULT_AUDIT_PATH = BENCHMARK_DIR / "combined_sales_v1_audit.json"
DEFAULT_AUDIT_MD_PATH = BENCHMARK_DIR / "combined_sales_v1_audit.md"
DEFAULT_DATASET_VERSION = "combined_sales_v1"
H3_RESOLUTION = 9

LEGACY_SOURCE_PRIOR = {
    "house_all.csv": 1.00,
    "townhome_all.csv": 0.95,
    "office_all.csv": 0.45,
    "apartment_all.csv": 0.35,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a combined Treasury + listing sale-price modeling table"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output parquet path",
    )
    parser.add_argument(
        "--audit-json",
        type=Path,
        default=DEFAULT_AUDIT_PATH,
        help="Output audit JSON path",
    )
    parser.add_argument(
        "--audit-md",
        type=Path,
        default=DEFAULT_AUDIT_MD_PATH,
        help="Output audit markdown path",
    )
    parser.add_argument(
        "--scraped-jsonl",
        type=Path,
        default=SCRAPED_JSONL_PATH,
        help="Normalized scraped listing JSONL file",
    )
    parser.add_argument(
        "--dataset-version",
        type=str,
        default=DEFAULT_DATASET_VERSION,
        help="Dataset version label stored in artifacts",
    )
    parser.add_argument(
        "--include-legacy-listings",
        action="store_true",
        help="Include rule-based salvage rows from legacy real_estate_listings",
    )
    return parser.parse_args()


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if np.isnan(value):
            return None
        return float(value)
    if isinstance(value, str):
        text_value = value.strip().replace(",", "")
        if not text_value:
            return None
        try:
            return float(text_value)
        except ValueError:
            return None
    return None


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    cleaned = " ".join(value.strip().split())
    return cleaned or None


def text_length(value: Any) -> int:
    cleaned = clean_text(value)
    return len(cleaned) if cleaned else 0


def normalize_property_type(value: Any) -> str:
    text_value = (clean_text(value) or "unknown").lower()

    mapping = {
        "บ้านเดี่ยว": "detached_house",
        "detached house": "detached_house",
        "house": "detached_house",
        "บ้าน": "detached_house",
        "บ้านแฝด": "twin_house",
        "twin house": "twin_house",
        "ทาวน์เฮ้าส์": "townhome",
        "ทาวน์โฮม": "townhome",
        "townhome": "townhome",
        "town house": "townhome",
        "townhouse": "townhome",
        "อาคารพาณิชย์": "commercial",
        "commercial": "commercial",
        "home office": "home_office",
        "โฮมออฟฟิศ": "home_office",
        "condo": "condo",
        "คอนโด": "condo",
        "สำนักงาน": "office",
        "office": "office",
    }
    if text_value in mapping:
        return mapping[text_value]
    if "town" in text_value:
        return "townhome"
    if "detached" in text_value or "single house" in text_value:
        return "detached_house"
    if "twin" in text_value:
        return "twin_house"
    if "condo" in text_value:
        return "condo"
    if "office" in text_value:
        return "office"
    if "commercial" in text_value:
        return "commercial"
    return text_value.replace(" ", "_") if text_value else "unknown"


def listing_primary_property_type(row: dict[str, Any]) -> str:
    property_types = row.get("property_types") or []
    if isinstance(property_types, list):
        for item in property_types:
            if isinstance(item, dict):
                for key in ("en", "th", "name"):
                    value = item.get(key)
                    if clean_text(value):
                        return normalize_property_type(value)
            elif clean_text(item):
                return normalize_property_type(item)
    return normalize_property_type(
        row.get("title_en") or row.get("title_th") or row.get("status")
    )


def choose_listing_unit(
    units: list[dict[str, Any]], project_price_start: float | None
) -> dict[str, Any]:
    parsed_units: list[dict[str, Any]] = []
    for unit in units or []:
        if not isinstance(unit, dict):
            continue
        unit_price = parse_float(unit.get("price_start"))
        parsed_units.append(
            {
                "unit_price_start": unit_price,
                "area_sqm": parse_float(unit.get("area_usable")),
                "land_area_raw": parse_float(unit.get("area_land")),
                "floors": parse_float(unit.get("num_floor")),
                "bedrooms": parse_float(unit.get("num_bed")),
                "bathrooms": parse_float(unit.get("num_bath")),
                "parking_spaces": parse_float(unit.get("num_parking")),
                "sold_out": bool(unit.get("sold_out")),
                "published": bool(unit.get("published")),
                "title": clean_text(unit.get("title") or unit.get("title_alt")),
            }
        )

    if not parsed_units:
        return {}

    candidates = [unit for unit in parsed_units if not unit["sold_out"]] or parsed_units
    candidates = [unit for unit in candidates if unit["published"]] or candidates

    if project_price_start is not None:
        priced = [unit for unit in candidates if unit["unit_price_start"] is not None]
        if priced:
            return min(
                priced,
                key=lambda unit: (
                    abs((unit["unit_price_start"] or 0.0) - project_price_start),
                    unit["unit_price_start"] or float("inf"),
                ),
            )

    return min(
        candidates,
        key=lambda unit: (
            unit["unit_price_start"] is None,
            unit["unit_price_start"] or float("inf"),
        ),
    )


def load_listing_enrichment(scraped_jsonl_path: Path) -> pd.DataFrame:
    if not scraped_jsonl_path.exists():
        logger.warning("Scraped JSONL not found at %s", scraped_jsonl_path)
        return pd.DataFrame(columns=["source_listing_id"])

    rows: list[dict[str, Any]] = []
    with scraped_jsonl_path.open(encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            source_listing_id = clean_text(payload.get("listing_id"))
            if not source_listing_id:
                continue

            financial = payload.get("financial") or {}
            detail = payload.get("detail") or {}
            general = payload.get("general") or {}
            unit = choose_listing_unit(
                payload.get("unit_types") or [],
                project_price_start=parse_float(financial.get("price_start")),
            )

            facility = payload.get("facility")
            if isinstance(facility, list):
                facility_count = len(facility)
            elif isinstance(facility, dict):
                facility_count = len(facility)
            else:
                facility_count = 0

            rows.append(
                {
                    "source_listing_id": source_listing_id,
                    "property_type_norm": listing_primary_property_type(payload),
                    "unit_area_sqm": unit.get("area_sqm"),
                    "unit_land_area_raw": unit.get("land_area_raw"),
                    "unit_floors": unit.get("floors"),
                    "bedrooms": unit.get("bedrooms"),
                    "bathrooms": unit.get("bathrooms"),
                    "parking_spaces": unit.get("parking_spaces"),
                    "unit_price_start": unit.get("unit_price_start"),
                    "unit_title": unit.get("title"),
                    "sale_condition": clean_text(general.get("sale_condition")),
                    "listing_status_detail": clean_text(general.get("status")),
                    "highlight_text": clean_text(general.get("highlight")),
                    "detail_text": clean_text(general.get("detail")),
                    "detail_area_total": parse_float(detail.get("area_total")),
                    "num_unit": parse_float(detail.get("num_unit")),
                    "num_unit_type": parse_float(detail.get("num_unit_type")),
                    "developer": clean_text(payload.get("developer")),
                    "facility_count": facility_count,
                    "image_url_count_jsonl": len(payload.get("image_urls") or []),
                    "has_video": int(bool(payload.get("video"))),
                    "title_length_jsonl": max(
                        text_length(payload.get("title_en")),
                        text_length(payload.get("title_th")),
                    ),
                    "highlight_length": text_length(general.get("highlight")),
                    "detail_length": text_length(general.get("detail")),
                }
            )

    enrichment = pd.DataFrame(rows)
    logger.info("Loaded listing enrichment for %s scraped rows", len(enrichment))
    return enrichment


def fetch_uploaded_image_stats() -> pd.DataFrame:
    query = """
    SELECT
        listing_id,
        COUNT(*) FILTER (WHERE fetch_status = 'uploaded') AS uploaded_image_count,
        COUNT(*) FILTER (WHERE fetch_status = 'pending') AS pending_image_count,
        COUNT(*) FILTER (WHERE fetch_status = 'failed') AS failed_image_count
    FROM scraped_listing_images
    GROUP BY listing_id
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    if df.empty:
        return pd.DataFrame(columns=["listing_id", "uploaded_image_count"])
    df["has_uploaded_images"] = (df["uploaded_image_count"] > 0).astype(int)
    return df


def fetch_treasury_rows() -> pd.DataFrame:
    query = """
    SELECT
        id,
        updated_date,
        building_area AS area_sqm,
        land_area,
        no_of_floor AS floors,
        building_age,
        building_style_desc,
        amphur AS district,
        tumbon AS subdistrict,
        province,
        total_price,
        ST_X(geometry::geometry) AS lon,
        ST_Y(geometry::geometry) AS lat
    FROM house_prices
    WHERE geometry IS NOT NULL
      AND total_price > 0
      AND building_area > 0
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)

    df["row_id"] = df["id"].map(lambda value: f"treasury:{value}")
    df["source_type"] = "treasury"
    df["source_site"] = "treasury"
    df["source_listing_id"] = None
    df["target_price_thb"] = df["total_price"].astype(float)
    df["target_log_price"] = np.log1p(df["target_price_thb"])
    df["event_date"] = pd.to_datetime(df["updated_date"])
    df["property_type"] = df["building_style_desc"].map(normalize_property_type)
    df["has_images"] = 0
    df["image_count"] = 0
    df["uploaded_image_count"] = 0
    df["has_uploaded_images"] = 0
    df["bedrooms"] = np.nan
    df["bathrooms"] = np.nan
    df["parking_spaces"] = np.nan
    df["unit_count"] = np.nan
    df["unit_type_count"] = np.nan
    df["developer_present"] = 0
    df["facility_count"] = 0
    df["listing_status"] = None
    df["sale_condition"] = None
    df["title_length"] = 0
    df["highlight_length"] = 0
    df["detail_length"] = 0
    df["has_video"] = 0
    df["land_area_is_ambiguous"] = 0
    return df[
        [
            "row_id",
            "source_type",
            "source_site",
            "id",
            "source_listing_id",
            "target_price_thb",
            "target_log_price",
            "event_date",
            "property_type",
            "area_sqm",
            "land_area",
            "floors",
            "building_age",
            "lat",
            "lon",
            "district",
            "subdistrict",
            "province",
            "has_images",
            "image_count",
            "uploaded_image_count",
            "has_uploaded_images",
            "bedrooms",
            "bathrooms",
            "parking_spaces",
            "unit_count",
            "unit_type_count",
            "developer_present",
            "facility_count",
            "listing_status",
            "sale_condition",
            "title_length",
            "highlight_length",
            "detail_length",
            "has_video",
            "land_area_is_ambiguous",
        ]
    ]


def fetch_listing_rows(listing_enrichment: pd.DataFrame) -> pd.DataFrame:
    query = """
    SELECT
        id AS listing_id,
        source,
        source_listing_id,
        title,
        property_type,
        district,
        subdistrict,
        province,
        status,
        price_start,
        price_end,
        image_count,
        main_image_url,
        scraped_at,
        latitude AS lat,
        longitude AS lon
    FROM scraped_listings
    WHERE price_start IS NOT NULL
      AND price_start > 0
      AND price_end IS NULL
      AND latitude IS NOT NULL
      AND longitude IS NOT NULL
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)

    image_stats = fetch_uploaded_image_stats()
    if not listing_enrichment.empty:
        df = df.merge(listing_enrichment, on="source_listing_id", how="left")
    if not image_stats.empty:
        df = df.merge(image_stats, on="listing_id", how="left")

    df["row_id"] = (
        df["source"].fillna("listing") + ":" + df["source_listing_id"].astype(str)
    )
    df["source_type"] = "listing"
    df["source_site"] = df["source"].fillna("unknown")
    df["target_price_thb"] = df["price_start"].astype(float)
    df["target_log_price"] = np.log1p(df["target_price_thb"])
    df["event_date"] = pd.to_datetime(df["scraped_at"])
    if "property_type_norm" not in df.columns:
        df["property_type_norm"] = pd.Series(index=df.index, dtype=object)
    df["property_type"] = df["property_type_norm"].fillna(
        df["property_type"].map(normalize_property_type)
    )
    df["area_sqm"] = df["unit_area_sqm"].combine_first(df["detail_area_total"])
    df["land_area"] = np.nan
    df["floors"] = df["unit_floors"]
    df["building_age"] = np.nan
    df["has_images"] = (df["image_count"].fillna(0) > 0).astype(int)
    df["image_count"] = df["image_count"].fillna(0).astype(int)
    df["uploaded_image_count"] = df["uploaded_image_count"].fillna(0).astype(int)
    df["has_uploaded_images"] = (df["uploaded_image_count"] > 0).astype(int)
    df["unit_count"] = df["num_unit"]
    df["unit_type_count"] = df["num_unit_type"]
    df["developer_present"] = df["developer"].notna().astype(int)
    df["listing_status"] = df["status"].combine_first(df.get("listing_status_detail"))
    df["sale_condition"] = df["sale_condition"].astype(object)
    df["title_length"] = np.maximum(
        df["title"].map(text_length), df["title_length_jsonl"].fillna(0)
    ).astype(int)
    df["highlight_length"] = df["highlight_length"].fillna(0).astype(int)
    df["detail_length"] = df["detail_length"].fillna(0).astype(int)
    df["has_video"] = df["has_video"].fillna(0).astype(int)
    df["facility_count"] = df["facility_count"].fillna(0).astype(int)
    df["land_area_is_ambiguous"] = (df["unit_land_area_raw"].notna()).astype(int)
    return df[
        [
            "row_id",
            "source_type",
            "source_site",
            "listing_id",
            "source_listing_id",
            "target_price_thb",
            "target_log_price",
            "event_date",
            "property_type",
            "area_sqm",
            "land_area",
            "floors",
            "building_age",
            "lat",
            "lon",
            "district",
            "subdistrict",
            "province",
            "has_images",
            "image_count",
            "uploaded_image_count",
            "has_uploaded_images",
            "bedrooms",
            "bathrooms",
            "parking_spaces",
            "unit_count",
            "unit_type_count",
            "developer_present",
            "facility_count",
            "listing_status",
            "sale_condition",
            "title_length",
            "highlight_length",
            "detail_length",
            "has_video",
            "land_area_is_ambiguous",
        ]
    ]


def fetch_legacy_listing_rows() -> pd.DataFrame:
    query = r"""
    WITH base AS (
        SELECT
            id,
            source_file,
            title,
            property_type,
            price,
            description,
            location,
            bathrooms,
            bedrooms,
            floors,
            usable_area_sqm,
            land_size_sqw,
            developer,
            status,
            image_count,
            ST_X(geometry::geometry) AS lon,
            ST_Y(geometry::geometry) AS lat,
            CASE
                WHEN price ~ '^[0-9,]+(\.[0-9]+)? THB$'
                    THEN REPLACE(SPLIT_PART(price, ' ', 1), ',', '')::double precision
                ELSE NULL
            END AS price_thb,
            CASE
                WHEN usable_area_sqm ~ '^[0-9]+(\.[0-9]+)?$'
                    THEN usable_area_sqm::double precision
                ELSE NULL
            END AS area_sqm_num,
            CASE
                WHEN land_size_sqw ~ '^[0-9]+(\.[0-9]+)?$'
                    THEN land_size_sqw::double precision * 4.0
                ELSE NULL
            END AS land_area_sqm,
            CASE
                WHEN floors ~ '^[0-9]+(\.[0-9]+)?$'
                    THEN floors::double precision
                ELSE NULL
            END AS floors_num,
            CASE
                WHEN bedrooms ~ '^[0-9]+(\.[0-9]+)?$'
                    THEN bedrooms::double precision
                ELSE NULL
            END AS bedrooms_num,
            CASE
                WHEN bathrooms ~ '^[0-9]+(\.[0-9]+)?$'
                    THEN bathrooms::double precision
                ELSE NULL
            END AS bathrooms_num
        FROM real_estate_listings
        WHERE geometry IS NOT NULL
          AND ST_Y(geometry::geometry) BETWEEN 13.4 AND 14.2
          AND ST_X(geometry::geometry) BETWEEN 100.3 AND 100.95
          AND property_type IN ('บ้าน', 'ทาวน์โฮม', 'บ้านแฝด')
    )
    SELECT *
    FROM base
    WHERE price_thb BETWEEN 300000 AND 100000000
      AND area_sqm_num BETWEEN 20 AND 2000
      AND price_thb / area_sqm_num BETWEEN 5000 AND 500000
      AND (
        location ILIKE '%กรุงเทพ%'
        OR location ILIKE '%กรุงเทพมหานคร%'
        OR location ILIKE '%กรุงเทพฯ%'
      )
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)

    if df.empty:
        return pd.DataFrame()

    df["row_id"] = df["id"].map(lambda value: f"legacy_bania:{value}")
    df["source_type"] = "listing"
    df["source_site"] = "legacy_bania"
    df["legacy_listing_id"] = df["id"]
    df["source_listing_id"] = df["id"].astype(str)
    df["target_price_thb"] = df["price_thb"].astype(float)
    df["target_log_price"] = np.log1p(df["target_price_thb"])
    df["event_date"] = pd.NaT
    df["property_type"] = df["property_type"].map(normalize_property_type)
    df["area_sqm"] = df["area_sqm_num"].astype(float)
    df["land_area"] = df["land_area_sqm"].astype(float)
    df["floors"] = df["floors_num"].astype(float)
    df["building_age"] = np.nan
    df["district"] = None
    df["subdistrict"] = None
    df["province"] = "Bangkok"
    df["has_images"] = (df["image_count"].fillna(0) > 0).astype(int)
    df["image_count"] = df["image_count"].fillna(0).astype(int)
    df["uploaded_image_count"] = 0
    df["has_uploaded_images"] = 0
    df["bedrooms"] = df["bedrooms_num"].astype(float)
    df["bathrooms"] = df["bathrooms_num"].astype(float)
    df["parking_spaces"] = np.nan
    df["unit_count"] = np.nan
    df["unit_type_count"] = np.nan
    df["developer_present"] = df["developer"].map(
        lambda value: int(clean_text(value) is not None)
    )
    df["facility_count"] = 0
    df["listing_status"] = df["status"].map(clean_text)
    df["sale_condition"] = "sale_listing_legacy_rule_based"
    df["title_length"] = df["title"].map(text_length).astype(int)
    df["highlight_length"] = 0
    df["detail_length"] = df["description"].map(text_length).astype(int)
    df["has_video"] = 0
    df["land_area_is_ambiguous"] = 0

    source_file = df["source_file"].fillna("unknown").astype(str)
    source_prior = source_file.map(LEGACY_SOURCE_PRIOR).fillna(0.40)
    has_floors = df["floors"].notna().astype(float)
    has_bedrooms = df["bedrooms"].notna().astype(float)
    has_bathrooms = df["bathrooms"].notna().astype(float)
    has_land_area = df["land_area"].notna().astype(float)
    has_images = df["has_images"].astype(float)
    text_rich = ((df["title_length"] >= 12) | (df["detail_length"] >= 80)).astype(float)
    strong_text = ((df["title_length"] >= 20) | (df["detail_length"] >= 180)).astype(
        float
    )
    property_type_normalized = df["property_type"].fillna("unknown").astype(str)

    source_property_penalty = pd.Series(0.0, index=df.index, dtype=float)
    source_property_penalty = np.where(
        (source_file == "office_all.csv")
        & (property_type_normalized.isin(["detached_house", "twin_house", "townhome"])),
        -0.22,
        source_property_penalty,
    )
    source_property_penalty = np.where(
        (source_file == "apartment_all.csv")
        & (property_type_normalized.isin(["detached_house", "twin_house", "townhome"])),
        -0.26,
        source_property_penalty,
    )
    source_property_penalty = np.where(
        (source_file == "house_all.csv") & (property_type_normalized == "townhome"),
        -0.08,
        source_property_penalty,
    )

    duplicate_key = (
        df["source_file"].fillna("unknown").astype(str)
        + "|"
        + (df["target_price_thb"].round(-4)).astype(int).astype(str)
        + "|"
        + (df["lat"].round(3)).astype(str)
        + "|"
        + (df["lon"].round(3)).astype(str)
        + "|"
        + df["area_sqm"].round(1).astype(str)
    )
    duplicate_count = duplicate_key.value_counts()
    duplicate_penalty = duplicate_key.map(
        lambda key: (
            -0.32
            if duplicate_count.get(key, 1) >= 4
            else -0.22
            if duplicate_count.get(key, 1) == 3
            else -0.14
            if duplicate_count.get(key, 1) == 2
            else 0.0
        )
    )

    missing_core = (
        (1.0 - has_floors)
        + (1.0 - has_bedrooms)
        + (1.0 - has_bathrooms)
        + (1.0 - has_land_area)
    ) / 4.0

    confidence_raw = (
        0.42 * source_prior
        + 0.08 * has_floors
        + 0.08 * has_bedrooms
        + 0.08 * has_bathrooms
        + 0.06 * has_land_area
        + 0.07 * has_images
        + 0.06 * text_rich
        + 0.05 * strong_text
        + source_property_penalty
        + duplicate_penalty
        - 0.22 * missing_core
    )
    df["legacy_confidence_score"] = confidence_raw.clip(0.05, 1.00).astype(float)
    df["legacy_quality_bucket"] = pd.cut(
        df["legacy_confidence_score"],
        bins=[0.0, 0.35, 0.65, 1.01],
        labels=["low", "medium", "high"],
        right=False,
    ).astype(str)

    return df[
        [
            "row_id",
            "source_type",
            "source_site",
            "legacy_listing_id",
            "source_listing_id",
            "target_price_thb",
            "target_log_price",
            "event_date",
            "property_type",
            "area_sqm",
            "land_area",
            "floors",
            "building_age",
            "lat",
            "lon",
            "district",
            "subdistrict",
            "province",
            "has_images",
            "image_count",
            "uploaded_image_count",
            "has_uploaded_images",
            "bedrooms",
            "bathrooms",
            "parking_spaces",
            "unit_count",
            "unit_type_count",
            "developer_present",
            "facility_count",
            "listing_status",
            "sale_condition",
            "title_length",
            "highlight_length",
            "detail_length",
            "has_video",
            "land_area_is_ambiguous",
            "legacy_confidence_score",
            "legacy_quality_bucket",
        ]
    ]


def add_common_fields(df: pd.DataFrame, dataset_version: str) -> pd.DataFrame:
    result = df.copy()
    result["district"] = result["district"].map(clean_text)
    result["subdistrict"] = result["subdistrict"].map(clean_text)
    result["province"] = result["province"].map(clean_text)
    result["listing_status"] = result["listing_status"].map(clean_text)
    result["sale_condition"] = result["sale_condition"].map(clean_text)
    result["property_type"] = result["property_type"].fillna("unknown")
    result["h3_index"] = result.apply(
        lambda row: h3.latlng_to_cell(
            float(row["lat"]), float(row["lon"]), H3_RESOLUTION
        ),
        axis=1,
    )
    result["duplicate_group"] = np.where(
        result["source_type"] == "listing",
        result["source_site"].astype(str)
        + ":"
        + result["source_listing_id"].astype(str),
        result["row_id"],
    )
    result["fuzzy_duplicate_key"] = (
        result["source_site"].fillna("unknown").astype(str)
        + "|"
        + result["district"].fillna("unknown").astype(str).str.lower()
        + "|"
        + result["property_type"].fillna("unknown").astype(str)
        + "|"
        + result["target_price_thb"].round(-4).astype(int).astype(str)
        + "|"
        + result["lat"].round(3).astype(str)
        + "|"
        + result["lon"].round(3).astype(str)
    )
    result["dataset_version"] = dataset_version
    result["event_date"] = pd.to_datetime(result["event_date"], utc=True)
    if "legacy_confidence_score" not in result.columns:
        result["legacy_confidence_score"] = 1.0
    result["legacy_confidence_score"] = pd.to_numeric(
        result["legacy_confidence_score"], errors="coerce"
    ).fillna(1.0)
    if "legacy_quality_bucket" not in result.columns:
        result["legacy_quality_bucket"] = "clean"
    result["legacy_quality_bucket"] = (
        result["legacy_quality_bucket"].fillna("clean").astype(str)
    )
    return result


def build_audit_report(
    df: pd.DataFrame, dataset_version: str, include_legacy_listings: bool
) -> dict[str, Any]:
    listing_mask = df["source_type"] == "listing"
    treasury_mask = df["source_type"] == "treasury"

    def missing_pct(mask: pd.Series, column: str) -> float:
        subset = df.loc[mask, column]
        if len(subset) == 0:
            return 0.0
        return float(subset.isna().mean() * 100)

    fuzzy_duplicates = (
        df.loc[listing_mask, "fuzzy_duplicate_key"].value_counts().gt(1).sum()
    )
    property_dist = (
        df.groupby(["source_type", "property_type"]).size().reset_index(name="rows")
    )

    notes = [
        "Current combined dataset uses Treasury rows plus normalized scraped listing rows.",
        "Primary listing target is exact project-level price_start where price_end is null.",
        "Listing date coverage is still scrape-driven, so a true source-aware time benchmark remains blocked.",
        "Listing unit area/floor/bed/bath metadata comes from the closest-priced published unit type in the JSONL source.",
        "Listing land_area is intentionally left null for normalized scraped listings because unit area_land units are ambiguous in the current scraped schema.",
    ]
    if include_legacy_listings:
        notes.extend(
            [
                "Legacy Baania bulk rows are included through a conservative rule-based salvage policy for Bangkok house/townhome/twin-house listings.",
                "Legacy listing event_date is unavailable, so those rows currently carry NaT and should not be trusted for time-aware evaluation.",
                "Legacy listing district/subdistrict fields are left null because location parsing is not yet robust enough for benchmark-grade normalization.",
            ]
        )

    report = {
        "dataset_version": dataset_version,
        "row_count_total": int(len(df)),
        "row_count_by_source": {
            source: int(count)
            for source, count in df["source_site"].value_counts().items()
        },
        "usable_rows_by_source_type": {
            "treasury": int(treasury_mask.sum()),
            "listing": int(listing_mask.sum()),
        },
        "date_coverage": {
            "treasury": {
                "min": str(df.loc[treasury_mask, "event_date"].min()),
                "max": str(df.loc[treasury_mask, "event_date"].max()),
            },
            "listing": {
                "min": str(df.loc[listing_mask, "event_date"].min()),
                "max": str(df.loc[listing_mask, "event_date"].max()),
            },
        },
        "listing_image_summary": {
            "rows": int(listing_mask.sum()),
            "has_image_rate_pct": float(
                df.loc[listing_mask, "has_images"].mean() * 100
            ),
            "has_uploaded_image_rate_pct": float(
                df.loc[listing_mask, "has_uploaded_images"].mean() * 100
            ),
            "avg_image_count": float(df.loc[listing_mask, "image_count"].mean()),
            "avg_uploaded_image_count": float(
                df.loc[listing_mask, "uploaded_image_count"].mean()
            ),
        },
        "missingness_pct": {
            "area_sqm": {
                "treasury": missing_pct(treasury_mask, "area_sqm"),
                "listing": missing_pct(listing_mask, "area_sqm"),
            },
            "land_area": {
                "treasury": missing_pct(treasury_mask, "land_area"),
                "listing": missing_pct(listing_mask, "land_area"),
            },
            "floors": {
                "treasury": missing_pct(treasury_mask, "floors"),
                "listing": missing_pct(listing_mask, "floors"),
            },
            "building_age": {
                "treasury": missing_pct(treasury_mask, "building_age"),
                "listing": missing_pct(listing_mask, "building_age"),
            },
            "bedrooms": {
                "treasury": missing_pct(treasury_mask, "bedrooms"),
                "listing": missing_pct(listing_mask, "bedrooms"),
            },
            "bathrooms": {
                "treasury": missing_pct(treasury_mask, "bathrooms"),
                "listing": missing_pct(listing_mask, "bathrooms"),
            },
            "parking_spaces": {
                "treasury": missing_pct(treasury_mask, "parking_spaces"),
                "listing": missing_pct(listing_mask, "parking_spaces"),
            },
        },
        "duplicate_risk": {
            "listing_exact_duplicates": int(
                df.loc[listing_mask, "duplicate_group"].value_counts().gt(1).sum()
            ),
            "listing_fuzzy_duplicate_keys": int(fuzzy_duplicates),
        },
        "property_type_distribution": property_dist.to_dict(orient="records"),
        "notes": notes,
    }
    return report


def build_audit_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# Combined Sales Dataset Audit",
        "",
        f"- Dataset version: `{audit['dataset_version']}`",
        f"- Total rows: `{audit['row_count_total']}`",
        f"- Treasury rows: `{audit['usable_rows_by_source_type']['treasury']}`",
        f"- Listing rows: `{audit['usable_rows_by_source_type']['listing']}`",
        "",
        "## Source Coverage",
        "",
    ]
    for source, count in audit["row_count_by_source"].items():
        lines.append(f"- `{source}`: `{count}` rows")

    lines.extend(
        [
            "",
            "## Date Coverage",
            "",
            f"- Treasury: `{audit['date_coverage']['treasury']['min']}` to `{audit['date_coverage']['treasury']['max']}`",
            f"- Listing: `{audit['date_coverage']['listing']['min']}` to `{audit['date_coverage']['listing']['max']}`",
            "",
            "## Listing Image Coverage",
            "",
            f"- Has image rate: `{audit['listing_image_summary']['has_image_rate_pct']:.1f}%`",
            f"- Has uploaded image rate: `{audit['listing_image_summary']['has_uploaded_image_rate_pct']:.1f}%`",
            f"- Avg image count: `{audit['listing_image_summary']['avg_image_count']:.2f}`",
            f"- Avg uploaded image count: `{audit['listing_image_summary']['avg_uploaded_image_count']:.2f}`",
            "",
            "## Missingness",
            "",
        ]
    )

    for field, values in audit["missingness_pct"].items():
        lines.append(
            f"- `{field}`: Treasury `{values['treasury']:.1f}%`, Listing `{values['listing']:.1f}%`"
        )

    lines.extend(
        [
            "",
            "## Duplicate Risk",
            "",
            f"- Exact listing duplicates: `{audit['duplicate_risk']['listing_exact_duplicates']}`",
            f"- Fuzzy listing duplicate keys: `{audit['duplicate_risk']['listing_fuzzy_duplicate_keys']}`",
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

    logger.info("Building combined sale-price dataset")
    listing_enrichment = load_listing_enrichment(args.scraped_jsonl)
    treasury_df = fetch_treasury_rows()
    listing_df = fetch_listing_rows(listing_enrichment)
    frames = [treasury_df, listing_df]
    legacy_df = pd.DataFrame()
    if args.include_legacy_listings:
        legacy_df = fetch_legacy_listing_rows()
        frames.append(legacy_df)
        logger.info("Loaded %s legacy salvage rows", len(legacy_df))
    combined_df = pd.concat(frames, ignore_index=True)
    combined_df = add_common_fields(combined_df, dataset_version=args.dataset_version)
    combined_df = combined_df.sort_values(
        ["source_type", "event_date", "row_id"]
    ).reset_index(drop=True)

    audit = build_audit_report(
        combined_df,
        dataset_version=args.dataset_version,
        include_legacy_listings=args.include_legacy_listings,
    )
    markdown = build_audit_markdown(audit)

    combined_df.to_parquet(args.output, index=False)
    args.audit_json.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    args.audit_md.write_text(markdown, encoding="utf-8")

    logger.info("Saved dataset to %s", args.output)
    logger.info("Saved audit JSON to %s", args.audit_json)
    logger.info("Saved audit markdown to %s", args.audit_md)
    logger.info(
        "Combined rows: %s (treasury=%s, listing=%s)",
        len(combined_df),
        len(treasury_df),
        len(combined_df) - len(treasury_df),
    )


if __name__ == "__main__":
    main()
