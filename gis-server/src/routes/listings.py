import json
import re
import time
from collections import OrderedDict
from datetime import timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.database import get_db_session
from src.config.settings import settings
from src.dependencies.auth import get_current_user_optional
from src.models.user import User

router = APIRouter(prefix="/listings", tags=["Listings"])

_listings_tile_cache: OrderedDict[str, tuple[bytes, float]] = OrderedDict()
_listings_tile_cache_hits = 0
_listings_tile_cache_misses = 0


def _get_cached_listings_tile(cache_key: str) -> bytes | None:
    global _listings_tile_cache_hits, _listings_tile_cache_misses

    cached = _listings_tile_cache.get(cache_key)
    if not cached:
        _listings_tile_cache_misses += 1
        return None

    payload, ts = cached
    if time.time() - ts > settings.LISTINGS_TILE_CACHE_TTL_SECONDS:
        del _listings_tile_cache[cache_key]
        _listings_tile_cache_misses += 1
        return None

    _listings_tile_cache.move_to_end(cache_key)
    _listings_tile_cache_hits += 1
    return payload


def _set_cached_listings_tile(cache_key: str, payload: bytes) -> None:
    _listings_tile_cache[cache_key] = (payload, time.time())
    _listings_tile_cache.move_to_end(cache_key)
    while len(_listings_tile_cache) > settings.LISTINGS_TILE_CACHE_MAX_ENTRIES:
        _listings_tile_cache.popitem(last=False)


def get_listings_tile_cache_stats() -> dict[str, int | float]:
    total = _listings_tile_cache_hits + _listings_tile_cache_misses
    hit_rate = (_listings_tile_cache_hits / total) if total > 0 else 0.0
    return {
        "size": len(_listings_tile_cache),
        "max_entries": settings.LISTINGS_TILE_CACHE_MAX_ENTRIES,
        "ttl_seconds": settings.LISTINGS_TILE_CACHE_TTL_SECONDS,
        "hits": _listings_tile_cache_hits,
        "misses": _listings_tile_cache_misses,
        "hit_rate": round(hit_rate, 4),
    }


ListingSourceType = Literal[
    "house_price",
    "scraped_project",
    "market_listing",
    "condo_project",
]


def _load_known_districts(db: Session) -> list[str]:
    rows = db.execute(
        text(
            """
            SELECT DISTINCT amphur
            FROM house_prices
            WHERE amphur IS NOT NULL
              AND amphur <> ''
            ORDER BY amphur ASC
            """
        )
    ).fetchall()
    return sorted(
        [str(row._mapping["amphur"]) for row in rows if row._mapping["amphur"]],
        key=len,
        reverse=True,
    )


def _parse_price_to_float(price: str | None) -> float | None:
    if not price:
        return None

    cleaned = price.replace(",", "")
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    if not match:
        return None

    value = float(match.group(0))
    price_text = cleaned.lower()
    if "ล้าน" in price_text or "million" in price_text:
        return value * 1_000_000
    if "หมื่น" in price_text:
        return value * 10_000
    if "พัน" in price_text or "k" in price_text:
        return value * 1_000
    return value


def _parse_numeric(text_value: str | None) -> float | None:
    if not text_value:
        return None

    match = re.search(r"\d+(?:\.\d+)?", text_value.replace(",", ""))
    if not match:
        return None
    return float(match.group(0))


def _resolve_condo_image(images_raw: Any) -> str | None:
    if images_raw is None:
        return None

    if isinstance(images_raw, list):
        for item in images_raw:
            if isinstance(item, str) and item:
                return item
        return None

    if isinstance(images_raw, str):
        text_value = images_raw.strip()
        if not text_value:
            return None
        if text_value.startswith("["):
            try:
                parsed = json.loads(text_value)
            except json.JSONDecodeError:
                return text_value
            return _resolve_condo_image(parsed)
        return text_value

    return None


def _resolve_market_image(images_raw: Any) -> str | None:
    if images_raw is None:
        return None

    if isinstance(images_raw, str):
        for part in images_raw.split(","):
            candidate = part.strip()
            if candidate.startswith("http://") or candidate.startswith("https://"):
                return candidate
        return None

    if isinstance(images_raw, list):
        for item in images_raw:
            if isinstance(item, str) and (
                item.startswith("http://") or item.startswith("https://")
            ):
                return item
        return None

    return None


def _infer_district_from_location(
    location_text: str | None, known_districts: list[str]
) -> str | None:
    if not location_text:
        return None
    for district in known_districts:
        if district in location_text:
            return district
    return None


def _build_scraped_image_url(
    image_id: int | None, image_status: str | None
) -> str | None:
    if image_id is None or image_status != "uploaded":
        return None
    return f"/api/v1/listings/images/{image_id}"


class ListingItem(BaseModel):
    listing_key: str
    source_type: ListingSourceType
    source: str
    source_id: str
    title: str | None = None
    building_style_desc: str | None = None
    amphur: str | None = None
    tumbon: str | None = None
    total_price: float | None = None
    building_area: float | None = None
    no_of_floor: float | None = None
    building_age: float | None = None
    lat: float
    lon: float
    image_url: str | None = None
    image_status: str | None = None
    has_image: bool = False
    detail_url: str | None = None


class ListingListResponse(BaseModel):
    count: int
    items: list[ListingItem]


class ListingDistrictOption(BaseModel):
    amphur: str
    count: int


class ListingBuildingStyleOption(BaseModel):
    building_style_desc: str
    count: int


def _to_count(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _row_count(row: Any) -> int:
    return _to_count(row._mapping["count"])


def _build_common_filters(
    amphur: str | None,
    building_style: str | None,
    min_price: float | None,
    max_price: float | None,
    min_area: float | None,
    max_area: float | None,
) -> tuple[list[str], list[str], list[str], list[str], dict[str, Any]]:
    house_filters: list[str] = ["h.geometry IS NOT NULL"]
    scraped_filters: list[str] = ["s.geometry IS NOT NULL"]
    market_filters: list[str] = ["r.geometry IS NOT NULL"]
    condo_filters: list[str] = ["c.geometry IS NOT NULL"]
    params: dict[str, Any] = {}

    if amphur:
        house_filters.append("h.amphur = :amphur")
        scraped_filters.append("s.district = :amphur")
        market_filters.append("r.location ILIKE :amphur_like")
        condo_filters.append("c.location ILIKE :amphur_like")
        params["amphur"] = amphur
        params["amphur_like"] = f"%{amphur}%"

    if building_style:
        house_filters.append("h.building_style_desc = :building_style")
        scraped_filters.append("s.property_type = :building_style")
        market_filters.append("r.property_type = :building_style")
        condo_filters.append("c.name ILIKE :building_style_like")
        params["building_style"] = building_style
        params["building_style_like"] = f"%{building_style}%"

    if min_price is not None:
        house_filters.append("h.total_price >= :min_price")
        scraped_filters.append("COALESCE(s.price_start, s.price_end) >= :min_price")
        market_filters.append(
            "COALESCE(NULLIF(regexp_replace(r.price, '[^0-9.]', '', 'g'), '')::double precision, 0) >= :min_price"
        )
        condo_filters.append(
            "COALESCE(NULLIF(regexp_replace(c.price_sale, '[^0-9.]', '', 'g'), '')::double precision, 0) >= :min_price"
        )
        params["min_price"] = min_price

    if max_price is not None:
        house_filters.append("h.total_price <= :max_price")
        scraped_filters.append("COALESCE(s.price_start, s.price_end) <= :max_price")
        market_filters.append(
            "COALESCE(NULLIF(regexp_replace(r.price, '[^0-9.]', '', 'g'), '')::double precision, 0) <= :max_price"
        )
        condo_filters.append(
            "COALESCE(NULLIF(regexp_replace(c.price_sale, '[^0-9.]', '', 'g'), '')::double precision, 0) <= :max_price"
        )
        params["max_price"] = max_price

    if min_area is not None:
        house_filters.append("h.building_area >= :min_area")
        scraped_filters.append("1=1")
        market_filters.append(
            "COALESCE(NULLIF(regexp_replace(r.usable_area_sqm, '[^0-9.]', '', 'g'), '')::double precision, 0) >= :min_area"
        )
        condo_filters.append("1=1")
        params["min_area"] = min_area

    if max_area is not None:
        house_filters.append("h.building_area <= :max_area")
        scraped_filters.append("1=1")
        market_filters.append(
            "COALESCE(NULLIF(regexp_replace(r.usable_area_sqm, '[^0-9.]', '', 'g'), '')::double precision, 0) <= :max_area"
        )
        condo_filters.append("1=1")
        params["max_area"] = max_area

    return house_filters, scraped_filters, market_filters, condo_filters, params


def _rows_to_items(rows: Any, known_districts: list[str]) -> list[ListingItem]:
    items: list[ListingItem] = []
    for row in rows:
        proxy_image = _build_scraped_image_url(row.image_id, row.image_status)

        market_image = (
            _resolve_market_image(row.image_source_url)
            if row.source_type == "market_listing"
            else None
        )

        condo_image = (
            _resolve_condo_image(row.image_source_url)
            if row.source_type == "condo_project"
            else None
        )

        fallback_image = (
            row.main_image_url or market_image or condo_image or row.image_source_url
        )
        final_image = proxy_image or fallback_image

        raw_price = str(row.total_price) if row.total_price is not None else None
        price_value = _parse_price_to_float(raw_price)

        raw_area = str(row.building_area) if row.building_area is not None else None
        area_value = _parse_numeric(raw_area)

        raw_floors = str(row.no_of_floor) if row.no_of_floor is not None else None
        floor_value = _parse_numeric(raw_floors)

        amphur_value = row.amphur
        if not amphur_value and row.location_text:
            amphur_value = _infer_district_from_location(
                str(row.location_text), known_districts
            )

        items.append(
            ListingItem(
                listing_key=row.listing_key,
                source_type=row.source_type,
                source=row.source,
                source_id=row.source_id,
                title=row.title,
                building_style_desc=row.building_style_desc,
                amphur=amphur_value,
                tumbon=row.tumbon,
                total_price=price_value,
                building_area=area_value,
                no_of_floor=floor_value,
                building_age=row.building_age,
                lat=row.lat,
                lon=row.lon,
                image_url=final_image,
                image_status=row.image_status,
                has_image=bool(final_image),
                detail_url=row.detail_url,
            )
        )

    return items


@router.get("", response_model=ListingListResponse)
def list_listings(
    amphur: str | None = Query(None, description="Filter by district"),
    building_style: str | None = Query(None, description="Filter by building style"),
    min_price: float | None = Query(None, ge=0, description="Minimum price in THB"),
    max_price: float | None = Query(None, ge=0, description="Maximum price in THB"),
    min_area: float | None = Query(None, ge=0, description="Minimum area (sqm)"),
    max_area: float | None = Query(None, ge=0, description="Maximum area (sqm)"),
    limit: int = Query(100, ge=1, le=1000, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Results offset for pagination"),
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    (
        house_filters,
        scraped_filters,
        market_filters,
        condo_filters,
        params,
    ) = _build_common_filters(
        amphur, building_style, min_price, max_price, min_area, max_area
    )
    params["limit"] = limit
    params["offset"] = offset

    house_where = " AND ".join(house_filters)
    scraped_where = " AND ".join(scraped_filters)
    market_where = " AND ".join(market_filters)
    condo_where = " AND ".join(condo_filters)

    count_sql = text(
        f"""
        SELECT COUNT(*)
        FROM (
            SELECT h.id FROM house_prices h WHERE {house_where}
            UNION ALL
            SELECT s.id FROM scraped_listings s WHERE {scraped_where}
            UNION ALL
            SELECT r.id FROM real_estate_listings r WHERE {market_where}
            UNION ALL
            SELECT c.id FROM condo_projects c WHERE {condo_where}
        ) c
        """
    )

    data_sql = text(
        f"""
        SELECT *
        FROM (
            SELECT
                ('house:' || h.id::text) AS listing_key,
                'house_price' AS source_type,
                'treasury' AS source,
                h.id::text AS source_id,
                COALESCE(h.village, h.amphur || ' ' || COALESCE(h.building_style_desc, 'Property')) AS title,
                h.building_style_desc,
                h.amphur,
                h.tumbon,
                h.total_price::text AS total_price,
                h.building_area::text AS building_area,
                h.no_of_floor::text AS no_of_floor,
                h.building_age,
                ST_Y(h.geometry) AS lat,
                ST_X(h.geometry) AS lon,
                NULL::bigint AS image_id,
                NULL::text AS image_status,
                NULL::text AS image_source_url,
                NULL::text AS main_image_url,
                NULL::text AS detail_url,
                NULL::text AS location_text
            FROM house_prices h
            WHERE {house_where}

            UNION ALL

            SELECT
                ('scraped:' || s.source || ':' || s.id::text) AS listing_key,
                'scraped_project' AS source_type,
                s.source,
                s.source_listing_id AS source_id,
                COALESCE(s.title, s.title_en, s.title_th) AS title,
                s.property_type AS building_style_desc,
                s.district AS amphur,
                s.subdistrict AS tumbon,
                COALESCE(s.price_start, s.price_end)::text AS total_price,
                NULL::text AS building_area,
                NULL::text AS no_of_floor,
                NULL::double precision AS building_age,
                COALESCE(s.latitude, ST_Y(s.geometry)) AS lat,
                COALESCE(s.longitude, ST_X(s.geometry)) AS lon,
                img.image_id,
                img.fetch_status AS image_status,
                img.source_url AS image_source_url,
                s.main_image_url,
                s.detail_url,
                NULL::text AS location_text
            FROM scraped_listings s
            LEFT JOIN LATERAL (
                SELECT
                    i.id AS image_id,
                    i.fetch_status,
                    i.source_url
                FROM scraped_listing_images i
                WHERE i.listing_id = s.id
                ORDER BY i.is_primary DESC, i.image_order ASC NULLS LAST, i.id ASC
                LIMIT 1
            ) img ON TRUE
            WHERE {scraped_where}

            UNION ALL

            SELECT
                ('market:' || r.id::text) AS listing_key,
                'market_listing' AS source_type,
                'baania' AS source,
                r.id::text AS source_id,
                r.title,
                r.property_type AS building_style_desc,
                NULL::text AS amphur,
                NULL::text AS tumbon,
                r.price::text AS total_price,
                r.usable_area_sqm::text AS building_area,
                r.floors::text AS no_of_floor,
                NULL::double precision AS building_age,
                ST_Y(r.geometry) AS lat,
                ST_X(r.geometry) AS lon,
                NULL::bigint AS image_id,
                NULL::text AS image_status,
                r.images AS image_source_url,
                NULL::text AS main_image_url,
                NULL::text AS detail_url,
                r.location AS location_text
            FROM real_estate_listings r
            WHERE {market_where}

            UNION ALL

            SELECT
                ('condo:' || c.id::text) AS listing_key,
                'condo_project' AS source_type,
                'hipflat' AS source,
                c.id::text AS source_id,
                c.name AS title,
                'Condominium' AS building_style_desc,
                NULL::text AS amphur,
                NULL::text AS tumbon,
                c.price_sale::text AS total_price,
                NULL::text AS building_area,
                NULL::text AS no_of_floor,
                NULL::double precision AS building_age,
                ST_Y(c.geometry) AS lat,
                ST_X(c.geometry) AS lon,
                NULL::bigint AS image_id,
                NULL::text AS image_status,
                c.images::text AS image_source_url,
                NULL::text AS main_image_url,
                c.project_base_url AS detail_url,
                c.location AS location_text
            FROM condo_projects c
            WHERE {condo_where}
        ) merged
        ORDER BY
            COALESCE(NULLIF(regexp_replace(total_price::text, '[^0-9.]', '', 'g'), '')::double precision, 0) DESC,
            listing_key
        LIMIT :limit OFFSET :offset
        """
    )

    total = int(db.execute(count_sql, params).scalar() or 0)
    rows = db.execute(data_sql, params).fetchall()
    known_districts = _load_known_districts(db)
    items = _rows_to_items(rows, known_districts)
    return ListingListResponse(count=total, items=items)


@router.get("/districts", response_model=list[ListingDistrictOption])
def get_listing_districts(
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    sql = text(
        """
        SELECT amphur, SUM(count) AS count
        FROM (
            SELECT h.amphur AS amphur, COUNT(*) AS count
            FROM house_prices h
            WHERE h.geometry IS NOT NULL
              AND h.amphur IS NOT NULL
              AND h.amphur <> ''
            GROUP BY h.amphur
            UNION ALL
            SELECT s.district AS amphur, COUNT(*) AS count
            FROM scraped_listings s
            WHERE s.geometry IS NOT NULL
              AND s.district IS NOT NULL
              AND s.district <> ''
            GROUP BY s.district
            UNION ALL
            SELECT d.amphur, COUNT(*) AS count
            FROM real_estate_listings r
            JOIN (
                SELECT DISTINCT amphur
                FROM house_prices
                WHERE amphur IS NOT NULL
                  AND amphur <> ''
            ) d ON r.location ILIKE ('%' || d.amphur || '%')
            WHERE r.geometry IS NOT NULL
            GROUP BY d.amphur
            UNION ALL
            SELECT d.amphur, COUNT(*) AS count
            FROM condo_projects c
            JOIN (
                SELECT DISTINCT amphur
                FROM house_prices
                WHERE amphur IS NOT NULL
                  AND amphur <> ''
            ) d ON c.location ILIKE ('%' || d.amphur || '%')
            WHERE c.geometry IS NOT NULL
            GROUP BY d.amphur
        ) d
        GROUP BY amphur
        ORDER BY count DESC, amphur ASC
        """
    )
    rows = db.execute(sql).fetchall()
    return [
        ListingDistrictOption(amphur=r._mapping["amphur"], count=_row_count(r))
        for r in rows
    ]


@router.get("/building-styles", response_model=list[ListingBuildingStyleOption])
def get_listing_building_styles(
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    sql = text(
        """
        SELECT building_style_desc, SUM(count) AS count
        FROM (
            SELECT h.building_style_desc AS building_style_desc, COUNT(*) AS count
            FROM house_prices h
            WHERE h.geometry IS NOT NULL
              AND h.building_style_desc IS NOT NULL
              AND h.building_style_desc <> ''
            GROUP BY h.building_style_desc
            UNION ALL
            SELECT s.property_type AS building_style_desc, COUNT(*) AS count
            FROM scraped_listings s
            WHERE s.geometry IS NOT NULL
              AND s.property_type IS NOT NULL
              AND s.property_type <> ''
            GROUP BY s.property_type
            UNION ALL
            SELECT r.property_type AS building_style_desc, COUNT(*) AS count
            FROM real_estate_listings r
            WHERE r.geometry IS NOT NULL
              AND r.property_type IS NOT NULL
              AND r.property_type <> ''
            GROUP BY r.property_type
            UNION ALL
            SELECT 'Condominium' AS building_style_desc, COUNT(*) AS count
            FROM condo_projects c
            WHERE c.geometry IS NOT NULL
        ) s
        GROUP BY building_style_desc
        ORDER BY count DESC, building_style_desc ASC
        """
    )
    rows = db.execute(sql).fetchall()
    return [
        ListingBuildingStyleOption(
            building_style_desc=r._mapping["building_style_desc"],
            count=_row_count(r),
        )
        for r in rows
    ]


@router.get("/{listing_key}", response_model=ListingItem)
def get_listing_by_key(
    listing_key: str,
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    if listing_key.startswith("house:"):
        source_id = listing_key.replace("house:", "", 1)
        sql = text(
            """
            SELECT
                ('house:' || h.id::text) AS listing_key,
                'house_price' AS source_type,
                'treasury' AS source,
                h.id::text AS source_id,
                COALESCE(h.village, h.amphur || ' ' || COALESCE(h.building_style_desc, 'Property')) AS title,
                h.building_style_desc,
                h.amphur,
                h.tumbon,
                h.total_price,
                h.building_area,
                h.no_of_floor,
                h.building_age,
                ST_Y(h.geometry) AS lat,
                ST_X(h.geometry) AS lon,
                NULL::bigint AS image_id,
                NULL::text AS image_status,
                NULL::text AS image_source_url,
                NULL::text AS main_image_url,
                NULL::text AS detail_url,
                NULL::text AS location_text
            FROM house_prices h
            WHERE h.id::text = :source_id
              AND h.geometry IS NOT NULL
            LIMIT 1
            """
        )
        row = db.execute(sql, {"source_id": source_id}).fetchone()
    elif listing_key.startswith("scraped:"):
        key_parts = listing_key.split(":", 2)
        if len(key_parts) != 3:
            raise HTTPException(status_code=400, detail="Invalid scraped listing key")
        source = key_parts[1]
        source_db_id = key_parts[2]
        sql = text(
            """
            SELECT
                ('scraped:' || s.source || ':' || s.id::text) AS listing_key,
                'scraped_project' AS source_type,
                s.source,
                s.source_listing_id AS source_id,
                COALESCE(s.title, s.title_en, s.title_th) AS title,
                s.property_type AS building_style_desc,
                s.district AS amphur,
                s.subdistrict AS tumbon,
                COALESCE(s.price_start, s.price_end)::text AS total_price,
                NULL::text AS building_area,
                NULL::text AS no_of_floor,
                NULL::double precision AS building_age,
                COALESCE(s.latitude, ST_Y(s.geometry)) AS lat,
                COALESCE(s.longitude, ST_X(s.geometry)) AS lon,
                img.image_id,
                img.fetch_status AS image_status,
                img.source_url AS image_source_url,
                s.main_image_url,
                s.detail_url,
                NULL::text AS location_text
            FROM scraped_listings s
            LEFT JOIN LATERAL (
                SELECT
                    i.id AS image_id,
                    i.fetch_status,
                    i.source_url
                FROM scraped_listing_images i
                WHERE i.listing_id = s.id
                ORDER BY i.is_primary DESC, i.image_order ASC NULLS LAST, i.id ASC
                LIMIT 1
            ) img ON TRUE
            WHERE s.source = :source
              AND s.id::text = :source_db_id
              AND s.geometry IS NOT NULL
            LIMIT 1
            """
        )
        row = db.execute(
            sql,
            {
                "source": source,
                "source_db_id": source_db_id,
            },
        ).fetchone()
    elif listing_key.startswith("market:"):
        source_id = listing_key.replace("market:", "", 1)
        sql = text(
            """
            SELECT
                ('market:' || r.id::text) AS listing_key,
                'market_listing' AS source_type,
                'baania' AS source,
                r.id::text AS source_id,
                r.title,
                r.property_type AS building_style_desc,
                NULL::text AS amphur,
                NULL::text AS tumbon,
                r.price::text AS total_price,
                r.usable_area_sqm::text AS building_area,
                r.floors::text AS no_of_floor,
                NULL::double precision AS building_age,
                ST_Y(r.geometry) AS lat,
                ST_X(r.geometry) AS lon,
                NULL::bigint AS image_id,
                NULL::text AS image_status,
                r.images AS image_source_url,
                NULL::text AS main_image_url,
                NULL::text AS detail_url,
                r.location AS location_text
            FROM real_estate_listings r
            WHERE r.id::text = :source_id
              AND r.geometry IS NOT NULL
            LIMIT 1
            """
        )
        row = db.execute(sql, {"source_id": source_id}).fetchone()
    elif listing_key.startswith("condo:"):
        source_id = listing_key.replace("condo:", "", 1)
        sql = text(
            """
            SELECT
                ('condo:' || c.id::text) AS listing_key,
                'condo_project' AS source_type,
                'hipflat' AS source,
                c.id::text AS source_id,
                c.name AS title,
                'Condominium' AS building_style_desc,
                NULL::text AS amphur,
                NULL::text AS tumbon,
                c.price_sale::text AS total_price,
                NULL::text AS building_area,
                NULL::text AS no_of_floor,
                NULL::double precision AS building_age,
                ST_Y(c.geometry) AS lat,
                ST_X(c.geometry) AS lon,
                NULL::bigint AS image_id,
                NULL::text AS image_status,
                c.images::text AS image_source_url,
                NULL::text AS main_image_url,
                c.project_base_url AS detail_url,
                c.location AS location_text
            FROM condo_projects c
            WHERE c.id::text = :source_id
              AND c.geometry IS NOT NULL
            LIMIT 1
            """
        )
        row = db.execute(sql, {"source_id": source_id}).fetchone()
    else:
        raise HTTPException(status_code=400, detail="Unsupported listing key")

    if row is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    known_districts = _load_known_districts(db)
    items = _rows_to_items([row], known_districts)
    return items[0]


@router.get("/tile/{z}/{x}/{y}", tags=["Maps"])
def get_listings_tile(
    z: int,
    x: int,
    y: int,
    amphur: str | None = Query(None, description="Filter by district"),
    building_style: str | None = Query(None, description="Filter by building style"),
    min_price: float | None = Query(None, ge=0, description="Minimum price"),
    max_price: float | None = Query(None, ge=0, description="Maximum price"),
    min_area: float | None = Query(None, ge=0, description="Minimum area"),
    max_area: float | None = Query(None, ge=0, description="Maximum area"),
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    (
        house_filters,
        scraped_filters,
        market_filters,
        condo_filters,
        params,
    ) = _build_common_filters(
        amphur, building_style, min_price, max_price, min_area, max_area
    )

    house_filters.append(
        "ST_Intersects(ST_Transform(h.geometry, 3857), ST_TileEnvelope(:z, :x, :y))"
    )
    scraped_filters.append(
        "ST_Intersects(ST_Transform(s.geometry, 3857), ST_TileEnvelope(:z, :x, :y))"
    )
    market_filters.append(
        "ST_Intersects(ST_Transform(r.geometry, 3857), ST_TileEnvelope(:z, :x, :y))"
    )
    condo_filters.append(
        "ST_Intersects(ST_Transform(c.geometry, 3857), ST_TileEnvelope(:z, :x, :y))"
    )

    params["z"] = z
    params["x"] = x
    params["y"] = y

    cache_key = (
        f"{z}:{x}:{y}|{amphur or ''}|{building_style or ''}|"
        f"{min_price if min_price is not None else ''}|"
        f"{max_price if max_price is not None else ''}|"
        f"{min_area if min_area is not None else ''}|"
        f"{max_area if max_area is not None else ''}"
    )
    cached_tile = _get_cached_listings_tile(cache_key)
    if cached_tile is not None:
        return Response(
            content=cached_tile,
            media_type="application/vnd.mapbox-vector-tile",
            headers={
                "Cache-Control": "public, max-age=600",
                "X-Cache": "HIT",
            },
        )

    house_where = " AND ".join(house_filters)
    scraped_where = " AND ".join(scraped_filters)
    market_where = " AND ".join(market_filters)
    condo_where = " AND ".join(condo_filters)

    sql = text(
        f"""
        WITH merged AS (
            SELECT
                ST_AsMVTGeom(
                    ST_Transform(h.geometry, 3857),
                    ST_TileEnvelope(:z, :x, :y)
                ) AS geom,
                ('house:' || h.id::text) AS listing_key,
                h.id::text AS id,
                'house_price' AS source_type,
                'treasury' AS source,
                h.total_price,
                h.building_area,
                h.no_of_floor,
                h.building_age,
                h.building_style_desc,
                h.amphur,
                h.tumbon,
                NULL::text AS image_url,
                NULL::text AS detail_url,
                COALESCE(h.village, h.amphur || ' ' || COALESCE(h.building_style_desc, 'Property')) AS title
            FROM house_prices h
            WHERE {house_where}

            UNION ALL

            SELECT
                ST_AsMVTGeom(
                    ST_Transform(s.geometry, 3857),
                    ST_TileEnvelope(:z, :x, :y)
                ) AS geom,
                ('scraped:' || s.source || ':' || s.id::text) AS listing_key,
                s.source_listing_id AS id,
                'scraped_project' AS source_type,
                s.source,
                COALESCE(s.price_start, s.price_end) AS total_price,
                NULL::double precision AS building_area,
                NULL::double precision AS no_of_floor,
                NULL::double precision AS building_age,
                s.property_type AS building_style_desc,
                s.district AS amphur,
                s.subdistrict AS tumbon,
                s.main_image_url AS image_url,
                s.detail_url,
                COALESCE(s.title, s.title_en, s.title_th) AS title
            FROM scraped_listings s
            WHERE {scraped_where}

            UNION ALL

            SELECT
                ST_AsMVTGeom(
                    ST_Transform(r.geometry, 3857),
                    ST_TileEnvelope(:z, :x, :y)
                ) AS geom,
                ('market:' || r.id::text) AS listing_key,
                r.id::text AS id,
                'market_listing' AS source_type,
                'baania' AS source,
                COALESCE(NULLIF(regexp_replace(r.price, '[^0-9.]', '', 'g'), '')::double precision, 0) AS total_price,
                COALESCE(NULLIF(regexp_replace(r.usable_area_sqm, '[^0-9.]', '', 'g'), '')::double precision, NULL) AS building_area,
                COALESCE(NULLIF(regexp_replace(r.floors, '[^0-9.]', '', 'g'), '')::double precision, NULL) AS no_of_floor,
                NULL::double precision AS building_age,
                r.property_type AS building_style_desc,
                NULL::text AS amphur,
                NULL::text AS tumbon,
                substring(r.images from '(https?://[^,\s\]"\'']+)') AS image_url,
                NULL::text AS detail_url,
                r.title
            FROM real_estate_listings r
            WHERE {market_where}

            UNION ALL

            SELECT
                ST_AsMVTGeom(
                    ST_Transform(c.geometry, 3857),
                    ST_TileEnvelope(:z, :x, :y)
                ) AS geom,
                ('condo:' || c.id::text) AS listing_key,
                c.id::text AS id,
                'condo_project' AS source_type,
                'hipflat' AS source,
                COALESCE(NULLIF(regexp_replace(c.price_sale, '[^0-9.]', '', 'g'), '')::double precision, 0) AS total_price,
                NULL::double precision AS building_area,
                NULL::double precision AS no_of_floor,
                NULL::double precision AS building_age,
                'Condominium' AS building_style_desc,
                NULL::text AS amphur,
                NULL::text AS tumbon,
                NULL::text AS image_url,
                c.project_base_url AS detail_url,
                c.name AS title
            FROM condo_projects c
            WHERE {condo_where}
        )
        SELECT ST_AsMVT(merged.*, 'listings', 4096, 'geom') AS mvt
        FROM merged;
        """
    )

    result = db.execute(sql, params).scalar()
    payload = bytes(result) if result else b""
    _set_cached_listings_tile(cache_key, payload)

    return Response(
        content=payload,
        media_type="application/vnd.mapbox-vector-tile",
        headers={
            "Cache-Control": "public, max-age=600",
            "X-Cache": "MISS",
        },
    )


@router.get("/images/{image_id}")
def get_listing_image(
    image_id: int,
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    row = db.execute(
        text(
            """
            SELECT id, source_url, storage_bucket, object_key, fetch_status
            FROM scraped_listing_images
            WHERE id = :image_id
            LIMIT 1
            """
        ),
        {"image_id": image_id},
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Image not found")

    if row.fetch_status != "uploaded" or not row.object_key or not row.storage_bucket:
        if row.source_url:
            return RedirectResponse(url=row.source_url, status_code=307)
        raise HTTPException(status_code=404, detail="Image not available")

    try:
        from minio import Minio
    except ImportError:
        if row.source_url:
            return RedirectResponse(url=row.source_url, status_code=307)
        raise HTTPException(status_code=503, detail="Image proxy unavailable")

    endpoint = settings.MINIO_ENDPOINT
    secure = settings.MINIO_SECURE
    if endpoint.startswith("http://"):
        endpoint = endpoint.replace("http://", "", 1)
        secure = False
    elif endpoint.startswith("https://"):
        endpoint = endpoint.replace("https://", "", 1)
        secure = True

    client = Minio(
        endpoint,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=secure,
    )

    try:
        signed_url = client.presigned_get_object(
            bucket_name=row.storage_bucket,
            object_name=row.object_key,
            expires=timedelta(minutes=30),
        )
    except Exception:
        if row.source_url:
            return RedirectResponse(url=row.source_url, status_code=307)
        raise HTTPException(status_code=502, detail="Failed to access image storage")

    return RedirectResponse(url=signed_url, status_code=307)
