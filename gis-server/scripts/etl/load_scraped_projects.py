import argparse
import glob
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

# Add project root to path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from scripts.etl.utils import clean_float, clean_int
from src.config.database import SessionLocal
from src.models.realestate import ScrapedListing, ScrapedListingImage

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "scraped"
SOURCE_HINTS = ("baania", "hipflat")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load normalized scraped project JSONL data into Postgres/PostGIS"
    )
    parser.add_argument(
        "--input-glob",
        default=str(DATA_DIR / "*.jsonl"),
        help="Glob pattern for input JSONL files (default: data/scraped/*.jsonl)",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Optional explicit source override for all rows (e.g. baania, hipflat)",
    )
    parser.add_argument(
        "--include-raw",
        action="store_true",
        help="Store the full source record in raw_payload",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete existing scraped_listings and scraped_listing_images before loading",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Maximum number of JSONL rows to process",
    )
    parser.add_argument(
        "--commit-batch",
        type=int,
        default=250,
        help="Commit every N processed rows",
    )
    return parser.parse_args()


def infer_source(file_path: Path, payload: dict, override: str | None) -> str:
    if override:
        return override.strip().lower()

    source_value = payload.get("source")
    if isinstance(source_value, str) and source_value.strip():
        return source_value.strip().lower()

    file_name = file_path.name.lower()
    for hint in SOURCE_HINTS:
        if hint in file_name:
            return hint
    return "unknown"


def parse_iso_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except Exception:
            return None
    if not isinstance(value, str):
        return None

    candidate = value.strip()
    if not candidate:
        return None

    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def extract_listing_id(payload: dict) -> str | None:
    candidate_fields = [
        "listing_id",
        "project_id",
        "id",
        "source_listing_id",
        "search_hit_id",
    ]
    for field in candidate_fields:
        value = payload.get(field)
        if isinstance(value, (str, int)):
            value_str = str(value).strip()
            if value_str:
                return value_str

    fallback_url = (
        payload.get("source_url")
        or payload.get("project_url")
        or payload.get("detail_url")
    )
    if isinstance(fallback_url, str) and fallback_url.strip():
        return fallback_url.strip()
    return None


def parse_number(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    normalized = text.replace(",", "")
    matches = re.findall(r"-?\d+(?:\.\d+)?", normalized)
    if not matches:
        return None
    try:
        return float(matches[0])
    except ValueError:
        return None


def pick_primary_property_type(payload: dict) -> str | None:
    if isinstance(payload.get("property_type"), str):
        return payload["property_type"]

    property_types = payload.get("property_types")
    if not isinstance(property_types, list) or not property_types:
        return None

    first = property_types[0]
    if isinstance(first, str):
        return first
    if isinstance(first, dict):
        for key in ("en", "th", "name"):
            value = first.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return None


def pick_property_types(payload: dict):
    if payload.get("property_types") is not None:
        return payload.get("property_types")
    if payload.get("property_type") is not None:
        return [payload.get("property_type")]
    return None


def extract_location(payload: dict) -> tuple[float | None, float | None]:
    location = payload.get("location")
    if isinstance(location, dict):
        lat = clean_float(location.get("lat"))
        lon = clean_float(location.get("lon"))
        return lat, lon

    lat = clean_float(payload.get("latitude") or payload.get("lat"))
    lon = clean_float(payload.get("longitude") or payload.get("lon"))
    return lat, lon


def extract_prices(payload: dict) -> tuple[float | None, float | None]:
    financial = payload.get("financial")
    if isinstance(financial, dict):
        return parse_number(financial.get("price_start")), parse_number(
            financial.get("price_end")
        )

    sale_price = parse_number(payload.get("sale_price"))
    rent_price = parse_number(payload.get("rent_price"))
    return sale_price, rent_price


def extract_title(payload: dict) -> str | None:
    candidates = [
        payload.get("project_name"),
        payload.get("listing_title"),
        payload.get("title_en"),
        payload.get("title_th"),
        payload.get("title"),
    ]
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value
    return None


def normalize_image_urls(payload: dict) -> list[str]:
    urls: list[str] = []

    main_url = payload.get("main_image_url")
    if isinstance(main_url, str) and main_url.startswith("http"):
        urls.append(main_url)

    image_urls = payload.get("image_urls")
    if isinstance(image_urls, list):
        for value in image_urls:
            if isinstance(value, str) and value.startswith("http"):
                urls.append(value)

    deduped: list[str] = []
    seen = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def image_role(url: str, is_primary: bool) -> str:
    lowered = url.lower()
    if is_primary:
        return "main"
    if "thumbnail" in lowered:
        return "thumbnail"
    if ".webp" in lowered or "/webp/" in lowered:
        return "webp"
    return "gallery"


def upsert_listing(
    db: Session, payload: dict, source: str, include_raw: bool
) -> int | None:
    source_listing_id = extract_listing_id(payload)
    if not source_listing_id:
        return None

    lat, lon = extract_location(payload)
    geometry = None
    if lat is not None and lon is not None:
        geometry = from_shape(Point(lon, lat), srid=4326)

    price_start, price_end = extract_prices(payload)
    source_url = payload.get("source_url") or payload.get("project_url")
    detail_url = payload.get("detail_url") or payload.get("project_url")

    address = payload.get("address") if isinstance(payload.get("address"), dict) else {}

    province = (
        payload.get("province_en")
        or payload.get("province_th")
        or address.get("region")
    )
    district = (
        payload.get("district_en")
        or payload.get("district_th")
        or address.get("district_or_locality")
    )
    subdistrict = payload.get("subdistrict_en") or payload.get("subdistrict_th")

    row = {
        "source": source,
        "source_listing_id": source_listing_id,
        "source_url": source_url,
        "detail_url": detail_url,
        "source_search_url": payload.get("source_list_url"),
        "title": extract_title(payload),
        "title_th": payload.get("title_th"),
        "title_en": payload.get("title_en") or payload.get("project_name"),
        "property_type": pick_primary_property_type(payload),
        "property_types": pick_property_types(payload),
        "province_id": clean_int(payload.get("province_id")),
        "province": province,
        "district_id": clean_int(payload.get("district_id")),
        "district": district,
        "subdistrict_id": clean_int(payload.get("subdistrict_id")),
        "subdistrict": subdistrict,
        "status": payload.get("status"),
        "price_start": price_start,
        "price_end": price_end,
        "latitude": lat,
        "longitude": lon,
        "geometry": geometry,
        "main_image_url": payload.get("main_image_url"),
        "image_count": len(normalize_image_urls(payload)),
        "scraped_at": parse_iso_datetime(payload.get("scraped_at")),
        "raw_payload": payload if include_raw else None,
    }

    update_fields = {
        "source_url": row["source_url"],
        "detail_url": row["detail_url"],
        "source_search_url": row["source_search_url"],
        "title": row["title"],
        "title_th": row["title_th"],
        "title_en": row["title_en"],
        "property_type": row["property_type"],
        "property_types": row["property_types"],
        "province_id": row["province_id"],
        "province": row["province"],
        "district_id": row["district_id"],
        "district": row["district"],
        "subdistrict_id": row["subdistrict_id"],
        "subdistrict": row["subdistrict"],
        "status": row["status"],
        "price_start": row["price_start"],
        "price_end": row["price_end"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "geometry": row["geometry"],
        "main_image_url": row["main_image_url"],
        "image_count": row["image_count"],
        "scraped_at": row["scraped_at"],
        "updated_at": func.now(),
    }
    if include_raw:
        update_fields["raw_payload"] = row["raw_payload"]

    stmt = (
        insert(ScrapedListing)
        .values(**row)
        .on_conflict_do_update(
            constraint="uq_scraped_listings_source_listing",
            set_=update_fields,
        )
        .returning(ScrapedListing.id)
    )

    return db.execute(stmt).scalar_one()


def upsert_images(db: Session, listing_id: int, payload: dict) -> int:
    urls = normalize_image_urls(payload)
    if not urls:
        return 0

    main_url = (
        payload.get("main_image_url")
        if isinstance(payload.get("main_image_url"), str)
        else None
    )
    count = 0

    for index, url in enumerate(urls):
        parsed = urlparse(url)
        source_host = parsed.netloc.lower() if parsed.netloc else None
        is_primary = bool(main_url and url == main_url) or index == 0

        row = {
            "listing_id": listing_id,
            "source_url": url,
            "source_host": source_host,
            "image_role": image_role(url, is_primary=is_primary),
            "image_order": index,
            "is_primary": is_primary,
            "fetch_status": "pending",
        }

        stmt = (
            insert(ScrapedListingImage)
            .values(**row)
            .on_conflict_do_update(
                constraint="uq_scraped_listing_images_listing_url",
                set_={
                    "source_host": row["source_host"],
                    "image_role": row["image_role"],
                    "image_order": row["image_order"],
                    "is_primary": row["is_primary"],
                    "updated_at": func.now(),
                },
            )
        )
        db.execute(stmt)
        count += 1

    return count


def load_jsonl_file(
    db: Session,
    file_path: Path,
    source_override: str | None,
    include_raw: bool,
    commit_batch: int,
    max_rows: int | None,
) -> tuple[int, int, int]:
    processed = 0
    loaded = 0
    images = 0

    logger.info("Loading file: %s", file_path)
    with file_path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if max_rows is not None and processed >= max_rows:
                break

            raw = line.strip()
            if not raw:
                continue

            processed += 1
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                logger.warning("Invalid JSON at %s:%s (%s)", file_path, line_no, exc)
                continue

            if not isinstance(payload, dict):
                logger.warning("Skipping non-object JSON at %s:%s", file_path, line_no)
                continue

            source = infer_source(file_path, payload, source_override)
            listing_id = upsert_listing(
                db, payload, source=source, include_raw=include_raw
            )
            if listing_id is None:
                logger.warning(
                    "Skipping row with no listing identifier at %s:%s",
                    file_path,
                    line_no,
                )
                continue

            image_rows = upsert_images(db, listing_id=listing_id, payload=payload)
            loaded += 1
            images += image_rows

            if loaded % commit_batch == 0:
                db.commit()
                logger.info("Committed %s listings from %s", loaded, file_path.name)

    db.commit()
    return processed, loaded, images


def load_scraped_projects(
    db: Session,
    input_glob: str = str(DATA_DIR / "*.jsonl"),
    source_override: str | None = None,
    include_raw: bool = False,
    commit_batch: int = 250,
    max_rows: int | None = None,
) -> tuple[int, int, int, int]:
    files = [Path(p) for p in sorted(glob.glob(input_glob))]
    if not files:
        logger.warning("No JSONL files found for pattern: %s", input_glob)
        return 0, 0, 0, 0

    total_processed = 0
    total_loaded = 0
    total_images = 0
    remaining_rows = max_rows

    for file_path in files:
        processed, loaded, images = load_jsonl_file(
            db,
            file_path=file_path,
            source_override=source_override,
            include_raw=include_raw,
            commit_batch=max(commit_batch, 1),
            max_rows=remaining_rows,
        )
        total_processed += processed
        total_loaded += loaded
        total_images += images

        if remaining_rows is not None:
            remaining_rows = max(remaining_rows - processed, 0)
            if remaining_rows == 0:
                break

    logger.info(
        "Scraped load done. processed=%s loaded=%s image_rows=%s files=%s",
        total_processed,
        total_loaded,
        total_images,
        len(files),
    )
    return total_processed, total_loaded, total_images, len(files)


def truncate_tables(db: Session) -> None:
    logger.warning("Truncating scraped tables before load")
    db.query(ScrapedListingImage).delete()
    db.query(ScrapedListing).delete()
    db.commit()


def main() -> None:
    args = parse_args()

    db = SessionLocal()
    try:
        if args.truncate:
            truncate_tables(db)
        total_processed, total_loaded, total_images, file_count = load_scraped_projects(
            db,
            input_glob=args.input_glob,
            source_override=args.source,
            include_raw=args.include_raw,
            commit_batch=args.commit_batch,
            max_rows=args.max_rows,
        )
        logger.info(
            "Done. processed=%s loaded=%s image_rows=%s files=%s",
            total_processed,
            total_loaded,
            total_images,
            file_count,
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
