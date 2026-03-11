from datetime import timedelta
from typing import Annotated, Any

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


def _build_scraped_image_url(
    image_id: int | None, image_status: str | None
) -> str | None:
    if image_id is None:
        return None
    if image_status != "uploaded":
        return None
    return f"/api/v1/listings/images/{image_id}"


class ListingItem(BaseModel):
    listing_key: str
    source_type: str
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


@router.get("", response_model=ListingListResponse)
def list_listings(
    amphur: str | None = Query(None, description="Filter by district"),
    building_style: str | None = Query(None, description="Filter by building style"),
    min_price: float | None = Query(None, ge=0, description="Minimum price in THB"),
    max_price: float | None = Query(None, ge=0, description="Maximum price in THB"),
    limit: int = Query(100, ge=1, le=1000, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Results offset for pagination"),
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    house_filters: list[str] = ["h.geometry IS NOT NULL"]
    scraped_filters: list[str] = ["s.geometry IS NOT NULL"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if amphur:
        house_filters.append("h.amphur = :amphur")
        scraped_filters.append("s.district = :amphur")
        params["amphur"] = amphur

    if building_style:
        house_filters.append("h.building_style_desc = :building_style")
        scraped_filters.append("s.property_type = :building_style")
        params["building_style"] = building_style

    if min_price is not None:
        house_filters.append("h.total_price >= :min_price")
        scraped_filters.append("COALESCE(s.price_start, s.price_end) >= :min_price")
        params["min_price"] = min_price

    if max_price is not None:
        house_filters.append("h.total_price <= :max_price")
        scraped_filters.append("COALESCE(s.price_start, s.price_end) <= :max_price")
        params["max_price"] = max_price

    house_where = " AND ".join(house_filters)
    scraped_where = " AND ".join(scraped_filters)

    count_sql = text(
        f"""
        SELECT COUNT(*)
        FROM (
            SELECT h.id
            FROM house_prices h
            WHERE {house_where}
            UNION ALL
            SELECT s.id
            FROM scraped_listings s
            WHERE {scraped_where}
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
                NULL::text AS detail_url
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
                COALESCE(s.price_start, s.price_end) AS total_price,
                NULL::double precision AS building_area,
                NULL::double precision AS no_of_floor,
                NULL::double precision AS building_age,
                COALESCE(s.latitude, ST_Y(s.geometry)) AS lat,
                COALESCE(s.longitude, ST_X(s.geometry)) AS lon,
                img.image_id,
                img.fetch_status AS image_status,
                img.source_url AS image_source_url,
                s.main_image_url,
                s.detail_url
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
        ) merged
        ORDER BY total_price DESC NULLS LAST, listing_key
        LIMIT :limit OFFSET :offset
        """
    )

    total = int(db.execute(count_sql, params).scalar() or 0)
    rows = db.execute(data_sql, params).fetchall()

    items: list[ListingItem] = []
    for row in rows:
        proxy_image = _build_scraped_image_url(row.image_id, row.image_status)
        fallback_image = row.main_image_url or row.image_source_url
        final_image = proxy_image or fallback_image

        items.append(
            ListingItem(
                listing_key=row.listing_key,
                source_type=row.source_type,
                source=row.source,
                source_id=row.source_id,
                title=row.title,
                building_style_desc=row.building_style_desc,
                amphur=row.amphur,
                tumbon=row.tumbon,
                total_price=row.total_price,
                building_area=row.building_area,
                no_of_floor=row.no_of_floor,
                building_age=row.building_age,
                lat=row.lat,
                lon=row.lon,
                image_url=final_image,
                image_status=row.image_status,
                has_image=bool(final_image),
                detail_url=row.detail_url,
            )
        )

    return ListingListResponse(count=total, items=items)


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
                NULL::text AS detail_url
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
                COALESCE(s.price_start, s.price_end) AS total_price,
                NULL::double precision AS building_area,
                NULL::double precision AS no_of_floor,
                NULL::double precision AS building_age,
                COALESCE(s.latitude, ST_Y(s.geometry)) AS lat,
                COALESCE(s.longitude, ST_X(s.geometry)) AS lon,
                img.image_id,
                img.fetch_status AS image_status,
                img.source_url AS image_source_url,
                s.main_image_url,
                s.detail_url
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
    else:
        raise HTTPException(status_code=400, detail="Unsupported listing key")

    if row is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    proxy_image = _build_scraped_image_url(row.image_id, row.image_status)
    fallback_image = row.main_image_url or row.image_source_url
    final_image = proxy_image or fallback_image

    return ListingItem(
        listing_key=row.listing_key,
        source_type=row.source_type,
        source=row.source,
        source_id=row.source_id,
        title=row.title,
        building_style_desc=row.building_style_desc,
        amphur=row.amphur,
        tumbon=row.tumbon,
        total_price=row.total_price,
        building_area=row.building_area,
        no_of_floor=row.no_of_floor,
        building_age=row.building_age,
        lat=row.lat,
        lon=row.lon,
        image_url=final_image,
        image_status=row.image_status,
        has_image=bool(final_image),
        detail_url=row.detail_url,
    )


@router.get("/tile/{z}/{x}/{y}", tags=["Maps"])
def get_listings_tile(
    z: int,
    x: int,
    y: int,
    amphur: str | None = Query(None, description="Filter by district"),
    building_style: str | None = Query(None, description="Filter by building style"),
    min_price: float | None = Query(None, ge=0, description="Minimum price"),
    max_price: float | None = Query(None, ge=0, description="Maximum price"),
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    house_filters = [
        "h.geometry IS NOT NULL",
        "ST_Intersects(ST_Transform(h.geometry, 3857), ST_TileEnvelope(:z, :x, :y))",
    ]
    scraped_filters = [
        "s.geometry IS NOT NULL",
        "ST_Intersects(ST_Transform(s.geometry, 3857), ST_TileEnvelope(:z, :x, :y))",
    ]

    params: dict[str, int | float | str] = {"z": z, "x": x, "y": y}

    if amphur:
        house_filters.append("h.amphur = :amphur")
        scraped_filters.append("s.district = :amphur")
        params["amphur"] = amphur
    if building_style:
        house_filters.append("h.building_style_desc = :building_style")
        scraped_filters.append("s.property_type = :building_style")
        params["building_style"] = building_style
    if min_price is not None:
        house_filters.append("h.total_price >= :min_price")
        scraped_filters.append("COALESCE(s.price_start, s.price_end) >= :min_price")
        params["min_price"] = min_price
    if max_price is not None:
        house_filters.append("h.total_price <= :max_price")
        scraped_filters.append("COALESCE(s.price_start, s.price_end) <= :max_price")
        params["max_price"] = max_price

    house_where = " AND ".join(house_filters)
    scraped_where = " AND ".join(scraped_filters)

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
                NULL::text AS image_url
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
                s.main_image_url AS image_url
            FROM scraped_listings s
            WHERE {scraped_where}
        )
        SELECT ST_AsMVT(merged.*, 'listings', 4096, 'geom') AS mvt
        FROM merged;
        """
    )

    with db.bind.connect() as conn:
        result = conn.execute(sql, params).scalar()

    return Response(content=result, media_type="application/vnd.mapbox-vector-tile")


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
