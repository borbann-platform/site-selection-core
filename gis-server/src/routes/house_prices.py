"""
House Prices API endpoints.
Provides access to appraised house prices from Treasury Department.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from src.config.database import get_db_session
from src.dependencies.auth import get_current_user_optional
from src.models.realestate import HousePrice
from src.models.user import User

router = APIRouter(prefix="/house-prices", tags=["House Prices"])


class HousePriceItem(BaseModel):
    id: int
    updated_date: str | None = None
    land_type_desc: str | None = None
    building_style_desc: str | None = None
    tumbon: str | None = None
    amphur: str | None = None
    village: str | None = None
    building_age: float | None = None
    land_area: float | None = None
    building_area: float | None = None
    no_of_floor: float | None = None
    total_price: float | None = None
    lat: float
    lon: float


class HousePriceListResponse(BaseModel):
    count: int
    items: list[HousePriceItem]


class DistrictStats(BaseModel):
    amphur: str
    count: int
    avg_price: float
    min_price: float
    max_price: float
    avg_price_per_sqm: float | None = None


class BuildingStyleStats(BaseModel):
    building_style_desc: str
    count: int
    avg_price: float


class HousePriceStatsResponse(BaseModel):
    total_count: int
    by_district: list[DistrictStats]
    by_building_style: list[BuildingStyleStats]


class ResolveLocationResponse(BaseModel):
    amphur: str
    tumbon: str | None = None
    village: str | None = None
    distance_m: float


@router.get("", response_model=HousePriceListResponse)
def list_house_prices(
    amphur: str | None = Query(None, description="Filter by district (เขต)"),
    tumbon: str | None = Query(None, description="Filter by sub-district (แขวง)"),
    building_style: str | None = Query(
        None, description="Filter by building style (บ้านเดี่ยว, ทาวน์เฮ้าส์, etc.)"
    ),
    min_price: float | None = Query(None, ge=0, description="Minimum price in THB"),
    max_price: float | None = Query(None, ge=0, description="Maximum price in THB"),
    min_area: float | None = Query(
        None, ge=0, description="Minimum building area in sqm"
    ),
    max_area: float | None = Query(
        None, ge=0, description="Maximum building area in sqm"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Results offset for pagination"),
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    """
    List house prices with optional filters.
    """
    query = db.query(HousePrice)

    if amphur:
        query = query.filter(HousePrice.amphur == amphur)
    if tumbon:
        query = query.filter(HousePrice.tumbon == tumbon)
    if building_style:
        query = query.filter(HousePrice.building_style_desc == building_style)
    if min_price is not None:
        query = query.filter(HousePrice.total_price >= min_price)
    if max_price is not None:
        query = query.filter(HousePrice.total_price <= max_price)
    if min_area is not None:
        query = query.filter(HousePrice.building_area >= min_area)
    if max_area is not None:
        query = query.filter(HousePrice.building_area <= max_area)

    total = query.count()
    items = (
        query.with_entities(
            HousePrice,
            func.ST_X(HousePrice.geometry).label("lon"),
            func.ST_Y(HousePrice.geometry).label("lat"),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    result_items = []
    for item, lon, lat in items:
        result_items.append(
            HousePriceItem(
                id=item.id,
                updated_date=str(item.updated_date) if item.updated_date else None,
                land_type_desc=item.land_type_desc,
                building_style_desc=item.building_style_desc,
                tumbon=item.tumbon,
                amphur=item.amphur,
                village=item.village,
                building_age=item.building_age,
                land_area=item.land_area,
                building_area=item.building_area,
                no_of_floor=item.no_of_floor,
                total_price=item.total_price,
                lon=float(lon) if lon is not None else 0.0,
                lat=float(lat) if lat is not None else 0.0,
            )
        )

    return HousePriceListResponse(count=total, items=result_items)


@router.get("/stats", response_model=HousePriceStatsResponse)
def get_house_price_stats(
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    """
    Get aggregated statistics for house prices.
    """
    total = db.query(HousePrice).count()

    # Stats by district
    district_stats = (
        db.query(
            HousePrice.amphur,
            func.count(HousePrice.id).label("count"),
            func.avg(HousePrice.total_price).label("avg_price"),
            func.min(HousePrice.total_price).label("min_price"),
            func.max(HousePrice.total_price).label("max_price"),
            func.avg(
                HousePrice.total_price / func.nullif(HousePrice.building_area, 0)
            ).label("avg_price_per_sqm"),
        )
        .group_by(HousePrice.amphur)
        .order_by(func.count(HousePrice.id).desc())
        .all()
    )

    # Stats by building style
    style_stats = (
        db.query(
            HousePrice.building_style_desc,
            func.count(HousePrice.id).label("count"),
            func.avg(HousePrice.total_price).label("avg_price"),
        )
        .group_by(HousePrice.building_style_desc)
        .order_by(func.count(HousePrice.id).desc())
        .all()
    )

    return HousePriceStatsResponse(
        total_count=total,
        by_district=[
            DistrictStats(
                amphur=s.amphur,
                count=s.count,
                avg_price=float(s.avg_price or 0),
                min_price=float(s.min_price or 0),
                max_price=float(s.max_price or 0),
                avg_price_per_sqm=float(s.avg_price_per_sqm)
                if s.avg_price_per_sqm
                else None,
            )
            for s in district_stats
        ],
        by_building_style=[
            BuildingStyleStats(
                building_style_desc=s.building_style_desc or "Unknown",
                count=s.count,
                avg_price=float(s.avg_price or 0),
            )
            for s in style_stats
        ],
    )


@router.get("/nearby")
def get_nearby_house_prices(
    lat: float = Query(..., description="Latitude of center point"),
    lon: float = Query(..., description="Longitude of center point"),
    radius_m: int = Query(1000, ge=100, le=10000, description="Radius in meters"),
    building_style: str | None = Query(None, description="Filter by building style"),
    limit: int = Query(50, ge=1, le=200),
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    """
    Find house prices near a location within a given radius.
    Useful for comparable property analysis.
    """
    sql = text("""
        SELECT 
            id, 
            amphur, 
            tumbon,
            village,
            building_style_desc,
            building_age,
            land_area,
            building_area,
            no_of_floor,
            total_price,
            ST_Y(geometry) as lat,
            ST_X(geometry) as lon,
            ST_Distance(
                geometry::geography, 
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            ) as distance_m
        FROM house_prices
        WHERE ST_DWithin(
            geometry::geography,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
            :radius
        )
        AND (:building_style IS NULL OR building_style_desc = :building_style)
        ORDER BY distance_m
        LIMIT :limit
    """)

    result = db.execute(
        sql,
        {
            "lat": lat,
            "lon": lon,
            "radius": radius_m,
            "building_style": building_style,
            "limit": limit,
        },
    ).fetchall()

    items = []
    for row in result:
        items.append(
            {
                "id": row.id,
                "amphur": row.amphur,
                "tumbon": row.tumbon,
                "village": row.village,
                "building_style_desc": row.building_style_desc,
                "building_age": row.building_age,
                "land_area": row.land_area,
                "building_area": row.building_area,
                "no_of_floor": row.no_of_floor,
                "total_price": row.total_price,
                "lat": row.lat,
                "lon": row.lon,
                "distance_m": round(row.distance_m, 1),
            }
        )

    return {
        "center": {"lat": lat, "lon": lon},
        "radius_m": radius_m,
        "count": len(items),
        "items": items,
    }


@router.get("/resolve-location", response_model=ResolveLocationResponse)
def resolve_location(
    lat: float = Query(..., description="Latitude of location"),
    lon: float = Query(..., description="Longitude of location"),
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    """
    Resolve district/sub-district for a location using nearest property record.
    """
    sql = text(
        """
        SELECT amphur, tumbon, village,
               ST_Distance(
                   geometry::geography,
                   ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
               ) as distance_m
        FROM house_prices
        WHERE geometry IS NOT NULL
          AND amphur IS NOT NULL
        ORDER BY distance_m
        LIMIT 1
    """
    )

    row = db.execute(sql, {"lat": lat, "lon": lon}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No nearby location data")

    return ResolveLocationResponse(
        amphur=row.amphur,
        tumbon=row.tumbon,
        village=row.village,
        distance_m=round(float(row.distance_m), 1),
    )


@router.get("/tile/{z}/{x}/{y}", tags=["Maps"])
def get_house_prices_tile(
    z: int,
    x: int,
    y: int,
    amphur: str | None = Query(None, description="Filter by district"),
    building_style: str | None = Query(None, description="Filter by building style"),
    min_price: float | None = Query(None, ge=0, description="Minimum price"),
    max_price: float | None = Query(None, ge=0, description="Maximum price"),
    min_area: float | None = Query(None, ge=0, description="Minimum building area"),
    max_area: float | None = Query(None, ge=0, description="Maximum building area"),
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    """
    Serves Mapbox Vector Tiles (MVT) for house prices with optional filters.
    """
    # Build dynamic WHERE clause for filters
    filter_conditions = [
        "ST_Intersects(ST_Transform(geometry, 3857), ST_TileEnvelope(:z, :x, :y))"
    ]
    params: dict[str, int | float | str] = {"z": z, "x": x, "y": y}

    if amphur:
        filter_conditions.append("amphur = :amphur")
        params["amphur"] = amphur
    if building_style:
        filter_conditions.append("building_style_desc = :building_style")
        params["building_style"] = building_style
    if min_price is not None:
        filter_conditions.append("total_price >= :min_price")
        params["min_price"] = min_price
    if max_price is not None:
        filter_conditions.append("total_price <= :max_price")
        params["max_price"] = max_price
    if min_area is not None:
        filter_conditions.append("building_area >= :min_area")
        params["min_area"] = min_area
    if max_area is not None:
        filter_conditions.append("building_area <= :max_area")
        params["max_area"] = max_area

    where_clause = " AND ".join(filter_conditions)

    sql = text(f"""
        WITH mvtgeom AS (
            SELECT 
                ST_AsMVTGeom(
                    ST_Transform(geometry, 3857),
                    ST_TileEnvelope(:z, :x, :y)
                ) AS geom,
                id,
                amphur,
                building_style_desc,
                total_price,
                building_area
            FROM house_prices
            WHERE {where_clause}
        )
        SELECT ST_AsMVT(mvtgeom.*, 'house_prices', 4096, 'geom') AS mvt
        FROM mvtgeom;
    """)

    with db.bind.connect() as conn:
        result = conn.execute(sql, params).scalar()

    return Response(content=result, media_type="application/vnd.mapbox-vector-tile")


@router.get("/districts")
def list_districts(
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    """
    List all districts with house price data.
    """
    districts = (
        db.query(HousePrice.amphur, func.count(HousePrice.id).label("count"))
        .group_by(HousePrice.amphur)
        .order_by(HousePrice.amphur)
        .all()
    )
    return [{"amphur": d.amphur, "count": d.count} for d in districts]


@router.get("/building-styles")
def list_building_styles(
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    """
    List all building styles.
    """
    styles = (
        db.query(
            HousePrice.building_style_desc, func.count(HousePrice.id).label("count")
        )
        .group_by(HousePrice.building_style_desc)
        .order_by(func.count(HousePrice.id).desc())
        .all()
    )
    return [
        {"building_style_desc": s.building_style_desc or "Unknown", "count": s.count}
        for s in styles
    ]


@router.get("/{property_id}")
def get_property_by_id(
    property_id: int,
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Session = Depends(get_db_session),
):
    """
    Get a single property by ID with full details.
    """
    row = (
        db.query(
            HousePrice,
            func.ST_X(HousePrice.geometry).label("lon"),
            func.ST_Y(HousePrice.geometry).label("lat"),
        )
        .filter(HousePrice.id == property_id)
        .first()
    )
    if not row:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Property not found")

    item, lon, lat = row

    return {
        "id": item.id,
        "updated_date": str(item.updated_date) if item.updated_date else None,
        "land_type_desc": item.land_type_desc,
        "building_style_desc": item.building_style_desc,
        "tumbon": item.tumbon,
        "amphur": item.amphur,
        "village": item.village,
        "building_age": item.building_age,
        "land_area": item.land_area,
        "building_area": item.building_area,
        "no_of_floor": item.no_of_floor,
        "total_price": item.total_price,
        "lon": float(lon) if lon is not None else 0.0,
        "lat": float(lat) if lat is not None else 0.0,
    }
