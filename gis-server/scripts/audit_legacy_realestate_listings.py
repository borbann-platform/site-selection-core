#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from src.config.database import engine


BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "data" / "benchmarks"
JSON_PATH = OUTPUT_DIR / "legacy_real_estate_listing_audit.json"
MD_PATH = OUTPUT_DIR / "legacy_real_estate_listing_audit.md"


SUMMARY_SQL = text(
    r"""
    SELECT
      COUNT(*) AS total_rows,
      COUNT(*) FILTER (WHERE geometry IS NOT NULL) AS geo_rows,
      COUNT(*) FILTER (
        WHERE geometry IS NOT NULL
          AND ST_Y(geometry::geometry) BETWEEN 13.4 AND 14.2
          AND ST_X(geometry::geometry) BETWEEN 100.3 AND 100.95
      ) AS bangkok_bbox_rows,
      COUNT(*) FILTER (WHERE price IS NOT NULL AND btrim(price) <> '') AS price_nonempty,
      COUNT(*) FILTER (WHERE usable_area_sqm IS NOT NULL AND btrim(usable_area_sqm) <> '') AS area_nonempty,
      COUNT(*) FILTER (WHERE bedrooms IS NOT NULL AND btrim(bedrooms) <> '') AS bed_nonempty,
      COUNT(*) FILTER (WHERE bathrooms IS NOT NULL AND btrim(bathrooms) <> '') AS bath_nonempty,
      COUNT(*) FILTER (WHERE last_updated IS NOT NULL AND btrim(last_updated) <> '') AS last_updated_nonempty
    FROM real_estate_listings
    """
)


SOURCE_FILE_SQL = text(
    r"""
    SELECT source_file, COUNT(*) AS rows
    FROM real_estate_listings
    GROUP BY source_file
    ORDER BY rows DESC, source_file
    """
)


PROPERTY_TYPE_SQL = text(
    r"""
    SELECT property_type, COUNT(*) AS rows
    FROM real_estate_listings
    GROUP BY property_type
    ORDER BY rows DESC, property_type
    LIMIT 30
    """
)


BANGKOK_PROPERTY_TYPE_SQL = text(
    r"""
    SELECT property_type, COUNT(*) AS rows
    FROM real_estate_listings
    WHERE geometry IS NOT NULL
      AND ST_Y(geometry::geometry) BETWEEN 13.4 AND 14.2
      AND ST_X(geometry::geometry) BETWEEN 100.3 AND 100.95
    GROUP BY property_type
    ORDER BY rows DESC, property_type
    LIMIT 30
    """
)


SALVAGE_SQL = text(
    r"""
    WITH base AS (
      SELECT
        source_file,
        property_type,
        price,
        usable_area_sqm,
        bedrooms,
        bathrooms,
        location,
        CASE
          WHEN price ~ '^[0-9,]+(\.[0-9]+)? THB$'
            THEN REPLACE(SPLIT_PART(price, ' ', 1), ',', '')::numeric
          ELSE NULL
        END AS price_thb,
        CASE
          WHEN usable_area_sqm ~ '^[0-9]+(\.[0-9]+)?$'
            THEN usable_area_sqm::numeric
          ELSE NULL
        END AS area_sqm_num
      FROM real_estate_listings
      WHERE geometry IS NOT NULL
        AND ST_Y(geometry::geometry) BETWEEN 13.4 AND 14.2
        AND ST_X(geometry::geometry) BETWEEN 100.3 AND 100.95
        AND property_type IN ('บ้าน', 'ทาวน์โฮม', 'บ้านแฝด')
    ), tagged AS (
      SELECT
        *,
        CASE
          WHEN location ILIKE '%กรุงเทพ%' OR location ILIKE '%กรุงเทพมหานคร%' OR location ILIKE '%กรุงเทพฯ%'
            THEN 1
          ELSE 0
        END AS location_mentions_bangkok,
        CASE
          WHEN price ~ '^[0-9,]+(\.[0-9]+)? THB$' THEN 1
          ELSE 0
        END AS strict_price_parse,
        CASE
          WHEN area_sqm_num IS NOT NULL AND area_sqm_num BETWEEN 20 AND 2000 THEN 1
          ELSE 0
        END AS plausible_area,
        CASE
          WHEN price_thb IS NOT NULL AND price_thb BETWEEN 300000 AND 100000000 THEN 1
          ELSE 0
        END AS plausible_sale_price,
        CASE
          WHEN price_thb IS NOT NULL
            AND area_sqm_num IS NOT NULL
            AND area_sqm_num > 0
            AND price_thb / area_sqm_num BETWEEN 5000 AND 500000 THEN 1
          ELSE 0
        END AS plausible_price_per_sqm,
        CASE
          WHEN bedrooms ~ '^[0-9]+$' OR bedrooms IS NULL OR btrim(bedrooms) = '' THEN 1
          ELSE 0
        END AS simple_bed,
        CASE
          WHEN bathrooms ~ '^[0-9]+$' OR bathrooms IS NULL OR btrim(bathrooms) = '' THEN 1
          ELSE 0
        END AS simple_bath
      FROM base
    )
    SELECT
      COUNT(*) AS candidate_rows,
      COUNT(*) FILTER (WHERE strict_price_parse = 1) AS strict_price_parse_rows,
      COUNT(*) FILTER (WHERE plausible_sale_price = 1) AS plausible_sale_price_rows,
      COUNT(*) FILTER (WHERE plausible_sale_price = 1 AND plausible_area = 1) AS sale_plus_area_rows,
      COUNT(*) FILTER (WHERE plausible_sale_price = 1 AND plausible_area = 1 AND plausible_price_per_sqm = 1) AS sale_area_ppsm_rows,
      COUNT(*) FILTER (
        WHERE plausible_sale_price = 1
          AND plausible_area = 1
          AND plausible_price_per_sqm = 1
          AND simple_bed = 1
          AND simple_bath = 1
      ) AS structured_rows,
      COUNT(*) FILTER (WHERE plausible_sale_price = 1 AND location_mentions_bangkok = 1) AS location_bangkok_sale_rows
    FROM tagged
    """
)


SALVAGE_BY_SOURCE_SQL = text(
    r"""
    WITH tagged AS (
      SELECT
        source_file,
        CASE
          WHEN price ~ '^[0-9,]+(\.[0-9]+)? THB$'
            THEN REPLACE(SPLIT_PART(price, ' ', 1), ',', '')::numeric
          ELSE NULL
        END AS price_thb,
        CASE
          WHEN usable_area_sqm ~ '^[0-9]+(\.[0-9]+)?$'
            THEN usable_area_sqm::numeric
          ELSE NULL
        END AS area_sqm_num
      FROM real_estate_listings
      WHERE geometry IS NOT NULL
        AND ST_Y(geometry::geometry) BETWEEN 13.4 AND 14.2
        AND ST_X(geometry::geometry) BETWEEN 100.3 AND 100.95
        AND property_type IN ('บ้าน', 'ทาวน์โฮม', 'บ้านแฝด')
    )
    SELECT
      source_file,
      COUNT(*) AS rows,
      COUNT(*) FILTER (WHERE price_thb BETWEEN 300000 AND 100000000) AS plausible_sale_price_rows,
      COUNT(*) FILTER (
        WHERE price_thb BETWEEN 300000 AND 100000000
          AND area_sqm_num BETWEEN 20 AND 2000
      ) AS sale_plus_area_rows,
      COUNT(*) FILTER (
        WHERE price_thb BETWEEN 300000 AND 100000000
          AND area_sqm_num BETWEEN 20 AND 2000
          AND price_thb / area_sqm_num BETWEEN 5000 AND 500000
      ) AS sale_area_ppsm_rows
    FROM tagged
    GROUP BY source_file
    ORDER BY rows DESC, source_file
    """
)


def fetch_all(query: text) -> list[dict[str, object]]:
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return [dict(row) for row in rows]


def fetch_one(query: text) -> dict[str, object]:
    with engine.connect() as conn:
        row = conn.execute(query).mappings().one()
    return dict(row)


def as_int(value: object) -> int:
    if value is None:
        return 0
    return int(value)


def render_markdown(audit: dict[str, object]) -> str:
    summary = audit["summary"]
    salvage = audit["salvage_estimate"]
    source_files = audit["source_files"]
    by_source = audit["salvage_by_source_file"]
    property_types = audit["top_property_types_bangkok_bbox"]

    lines: list[str] = []
    lines.append("# Legacy Real Estate Listing Audit")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total rows: `{summary['total_rows']:,}`")
    lines.append(f"- Rows with geometry: `{summary['geo_rows']:,}`")
    lines.append(f"- Bangkok bbox rows: `{summary['bangkok_bbox_rows']:,}`")
    lines.append(f"- Price non-empty rows: `{summary['price_nonempty']:,}`")
    lines.append(f"- Area non-empty rows: `{summary['area_nonempty']:,}`")
    lines.append(f"- Bedroom non-empty rows: `{summary['bed_nonempty']:,}`")
    lines.append(f"- Bathroom non-empty rows: `{summary['bath_nonempty']:,}`")
    lines.append(
        f"- `last_updated` non-empty rows: `{summary['last_updated_nonempty']:,}`"
    )
    lines.append("")
    lines.append("## Salvage Estimate For Bangkok Sale-Like House Rows")
    lines.append("")
    lines.append(
        f"- Candidate Bangkok house/townhome/twin-house rows: `{salvage['candidate_rows']:,}`"
    )
    lines.append(
        f"- Strictly parseable `price` rows: `{salvage['strict_price_parse_rows']:,}`"
    )
    lines.append(
        f"- Plausible sale-price rows (`300k-100M THB`): `{salvage['plausible_sale_price_rows']:,}`"
    )
    lines.append(f"- Plausible sale + area rows: `{salvage['sale_plus_area_rows']:,}`")
    lines.append(
        f"- Plausible sale + area + price-per-sqm rows: `{salvage['sale_area_ppsm_rows']:,}`"
    )
    lines.append(f"- Structured salvage estimate: `{salvage['structured_rows']:,}`")
    lines.append(
        f"- Rows explicitly mentioning Bangkok in `location`: `{salvage['location_bangkok_sale_rows']:,}`"
    )
    lines.append("")
    lines.append("## Source Files")
    lines.append("")
    for row in source_files:
        lines.append(f"- `{row['source_file']}`: `{row['rows']:,}`")
    lines.append("")
    lines.append("## Bangkok Property Types")
    lines.append("")
    for row in property_types[:12]:
        prop = row["property_type"] or "<blank>"
        lines.append(f"- `{prop}`: `{row['rows']:,}`")
    lines.append("")
    lines.append("## Salvage By Source File")
    lines.append("")
    lines.append("| Source File | Rows | Plausible Sale | Sale+Area | Sale+Area+PPSM |")
    lines.append("|---|---:|---:|---:|---:|")
    for row in by_source:
        lines.append(
            "| "
            f"{row['source_file']} | {row['rows']:,} | {row['plausible_sale_price_rows']:,} | "
            f"{row['sale_plus_area_rows']:,} | {row['sale_area_ppsm_rows']:,} |"
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "- The legacy table is much larger than the normalized `scraped_listings` benchmark source."
    )
    lines.append(
        "- A large Bangkok house/townhome subset looks salvageable with rule-based price parsing and type filtering."
    )
    lines.append(
        "- `last_updated` is empty, so this source is weak for time-aware evaluation."
    )
    lines.append(
        "- Source-file labels are noisy because house-like rows appear in `office_all.csv` and `apartment_all.csv`."
    )
    lines.append(
        "- This source looks promising for a controlled expansion experiment, but it should not replace the cleaner normalized benchmark without an explicit cleanup policy."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    audit = {
        "summary": fetch_one(SUMMARY_SQL),
        "source_files": fetch_all(SOURCE_FILE_SQL),
        "top_property_types": fetch_all(PROPERTY_TYPE_SQL),
        "top_property_types_bangkok_bbox": fetch_all(BANGKOK_PROPERTY_TYPE_SQL),
        "salvage_estimate": fetch_one(SALVAGE_SQL),
        "salvage_by_source_file": fetch_all(SALVAGE_BY_SOURCE_SQL),
        "notes": [
            "Legacy real_estate_listings comes from bulk Bania CSV loads, not the newer normalized scraped JSONL pipeline.",
            "The salvage estimate focuses on Bangkok bbox rows with property_type in บ้าน / ทาวน์โฮม / บ้านแฝด.",
            "Structured salvage estimate applies strict price parsing, plausible sale-price bounds, plausible area bounds, and plausible price-per-sqm bounds.",
            "This audit is intended for source-selection decisions, not as a final benchmark-inclusion approval.",
        ],
    }

    JSON_PATH.write_text(
        json.dumps(audit, ensure_ascii=True, indent=2), encoding="utf-8"
    )
    MD_PATH.write_text(render_markdown(audit), encoding="utf-8")

    structured_rows = as_int(audit["salvage_estimate"]["structured_rows"])
    print(f"Saved legacy listing audit to {JSON_PATH}")
    print(f"Saved legacy listing markdown to {MD_PATH}")
    print(f"Structured salvage estimate: {structured_rows:,} rows")


if __name__ == "__main__":
    main()
