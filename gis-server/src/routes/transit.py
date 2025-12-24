"""Transit routes API - serves transit line data for map visualization."""

from enum import IntEnum
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.config.database import get_db_session

router = APIRouter(prefix="/transit", tags=["Transit"])


class RouteType(IntEnum):
    """GTFS route types."""

    TRAM = 0  # BTS Skytrain
    METRO = 1  # MRT Subway
    RAIL = 2  # Airport Rail Link, SRT
    BUS = 3  # BMTA buses


class TransitLineFeature(BaseModel):
    """GeoJSON Feature for a transit line."""

    type: str = "Feature"
    properties: dict[str, Any]
    geometry: dict[str, Any]


class TransitLinesResponse(BaseModel):
    """GeoJSON FeatureCollection of transit lines."""

    type: str = "FeatureCollection"
    features: list[TransitLineFeature]


@router.get("/lines", response_model=TransitLinesResponse)
def get_transit_lines(
    route_type: int | None = Query(
        None, description="Filter by route type: 0=Tram/BTS, 1=Metro/MRT, 2=Rail, 3=Bus"
    ),
    db: Session = Depends(get_db_session),
):
    """
    Get all transit lines as GeoJSON FeatureCollection.
    Optionally filter by route_type (0=BTS, 1=MRT, 2=Rail, 3=Bus).
    """
    where_clause = ""
    params: dict[str, Any] = {}

    if route_type is not None:
        where_clause = "WHERE route_type = :route_type"
        params["route_type"] = route_type

    sql = text(f"""
        SELECT
            shape_id,
            route_id,
            route_short_name,
            route_long_name,
            route_type,
            route_color,
            agency_id,
            ST_AsGeoJSON(geometry)::json as geometry
        FROM view_transit_lines
        {where_clause}
    """)

    with db.bind.connect() as conn:
        result = conn.execute(sql, params).fetchall()

    features = []
    for row in result:
        feature = TransitLineFeature(
            properties={
                "shape_id": row.shape_id,
                "route_id": row.route_id,
                "route_short_name": row.route_short_name,
                "route_long_name": row.route_long_name,
                "route_type": row.route_type,
                "route_color": row.route_color,
                "agency_id": row.agency_id,
            },
            geometry=row.geometry,
        )
        features.append(feature)

    return TransitLinesResponse(features=features)


@router.get("/lines/tile/{z}/{x}/{y}", tags=["Maps"])
def get_transit_lines_tile(
    z: int,
    x: int,
    y: int,
    route_type: int | None = Query(
        None, description="Filter by route type: 0=Tram/BTS, 1=Metro/MRT, 2=Rail, 3=Bus"
    ),
    db: Session = Depends(get_db_session),
):
    """
    Serves Mapbox Vector Tiles (MVT) for transit lines.
    Filter by route_type to show only specific transit modes.
    """
    # route_type is validated as int by FastAPI, safe for interpolation
    where_filter = ""
    if route_type is not None:
        where_filter = f"AND route_type = {int(route_type)}"

    sql = text(f"""
        WITH mvtgeom AS (
            SELECT
                ST_AsMVTGeom(
                    ST_Transform(geometry, 3857),
                    ST_TileEnvelope(:z, :x, :y)
                ) AS geom,
                shape_id,
                route_id,
                route_short_name,
                route_long_name,
                route_type,
                route_color,
                agency_id
            FROM view_transit_lines
            WHERE ST_Intersects(
                ST_Transform(geometry, 3857),
                ST_TileEnvelope(:z, :x, :y)
            )
            {where_filter}
        )
        SELECT ST_AsMVT(mvtgeom.*, 'transit_lines', 4096, 'geom') AS mvt
        FROM mvtgeom;
    """)

    with db.bind.connect() as conn:
        result = conn.execute(sql, {"z": z, "x": x, "y": y}).scalar()

    if result is None:
        result = b""

    return Response(content=result, media_type="application/vnd.mapbox-vector-tile")


@router.get("/stops", response_model=TransitLinesResponse)
def get_transit_stops(
    db: Session = Depends(get_db_session),
):
    """Get all transit stops as GeoJSON FeatureCollection."""
    sql = text("""
        SELECT
            stop_id,
            stop_name,
            zone_id,
            source,
            ST_AsGeoJSON(geometry)::json as geometry
        FROM transit_stops
    """)

    with db.bind.connect() as conn:
        result = conn.execute(sql).fetchall()

    features = []
    for row in result:
        feature = TransitLineFeature(
            properties={
                "stop_id": row.stop_id,
                "stop_name": row.stop_name,
                "zone_id": row.zone_id,
                "source": row.source,
            },
            geometry=row.geometry,
        )
        features.append(feature)

    return TransitLinesResponse(features=features)
