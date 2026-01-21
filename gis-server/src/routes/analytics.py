from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.database import get_db_session
from src.dependencies.auth import get_current_active_user
from src.models.user import User
from src.services.analytics import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])

# In-memory tile cache with TTL (simple LRU, max 2000 tiles)
# For production, consider Redis or similar distributed cache
_tile_cache: dict[str, tuple[bytes, float]] = {}
_TILE_CACHE_MAX_SIZE = 2000
_TILE_CACHE_TTL_SECONDS = 3600  # 1 hour


def _get_cached_tile(cache_key: str) -> bytes | None:
    """Get tile from cache if exists and not expired."""
    import time

    if cache_key in _tile_cache:
        data, timestamp = _tile_cache[cache_key]
        if time.time() - timestamp < _TILE_CACHE_TTL_SECONDS:
            return data
        del _tile_cache[cache_key]
    return None


def _set_cached_tile(cache_key: str, data: bytes) -> None:
    """Store tile in cache with timestamp."""
    import time

    # Simple LRU eviction: remove oldest entries if over max size
    if len(_tile_cache) >= _TILE_CACHE_MAX_SIZE:
        oldest_key = min(_tile_cache, key=lambda k: _tile_cache[k][1])
        del _tile_cache[oldest_key]
    _tile_cache[cache_key] = (data, time.time())


def clear_tile_cache() -> int:
    """Clear all cached tiles. Returns count of cleared entries."""
    count = len(_tile_cache)
    _tile_cache.clear()
    return count


class SiteLocation(BaseModel):
    id: str | None = None
    lat: float
    lon: float


class CannibalizationRequest(BaseModel):
    new_site: SiteLocation
    existing_sites: list[SiteLocation]
    beta: float = 2.0


class HexagonData(BaseModel):
    position: list[float]
    value: float


class GridResponse(BaseModel):
    hexagons: list[HexagonData]


@router.get("/pois/tile/{z}/{x}/{y}", tags=["Maps"])
def get_pois_tile(
    z: int,
    x: int,
    y: int,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: Session = Depends(get_db_session),
):
    """
    Serves Mapbox Vector Tiles (MVT) for POIs.
    """
    # SQL to generate MVT
    # ST_TileEnvelope(z, x, y) gets the bounds of the tile in Web Mercator (3857)
    # ST_AsMVTGeom transforms geometry to tile coordinates
    sql = text("""
        WITH mvtgeom AS (
            SELECT 
                ST_AsMVTGeom(
                    ST_Transform(geometry, 3857),
                    ST_TileEnvelope(:z, :x, :y)
                ) AS geom,
                name,
                amenity
            FROM pois
            WHERE ST_Intersects(
                ST_Transform(geometry, 3857),
                ST_TileEnvelope(:z, :x, :y)
            )
        )
        SELECT ST_AsMVT(mvtgeom.*, 'default', 4096, 'geom') AS mvt
        FROM mvtgeom;
    """)

    with db.bind.connect() as conn:
        result = conn.execute(sql, {"z": z, "x": x, "y": y}).scalar()

    return Response(content=result, media_type="application/vnd.mapbox-vector-tile")


@router.get("/all-pois/tile/{z}/{x}/{y}", tags=["Maps"])
def get_all_pois_tile(
    z: int,
    x: int,
    y: int,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: Session = Depends(get_db_session),
):
    """
    Serves Mapbox Vector Tiles (MVT) for All POIs (Unified View).
    Uses server-side caching for improved performance.
    """
    cache_key = f"all-pois-{z}-{x}-{y}"

    # Check cache first
    cached = _get_cached_tile(cache_key)
    if cached is not None:
        return Response(
            content=cached,
            media_type="application/vnd.mapbox-vector-tile",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Cache": "HIT",
            },
        )

    sql = text("""
        WITH mvtgeom AS (
            SELECT 
                ST_AsMVTGeom(
                    ST_Transform(geometry, 3857),
                    ST_TileEnvelope(:z, :x, :y)
                ) AS geom,
                id,
                name,
                type,
                source
            FROM view_all_pois
            WHERE ST_Intersects(
                ST_Transform(geometry, 3857),
                ST_TileEnvelope(:z, :x, :y)
            )
        )
        SELECT ST_AsMVT(mvtgeom.*, 'default', 4096, 'geom') AS mvt
        FROM mvtgeom;
    """)

    with db.bind.connect() as conn:
        result = conn.execute(sql, {"z": z, "x": x, "y": y}).scalar()

    # Cache the result
    if result:
        _set_cached_tile(cache_key, bytes(result))

    return Response(
        content=result,
        media_type="application/vnd.mapbox-vector-tile",
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Cache": "MISS",
        },
    )


@router.get("/residential/tile/{z}/{x}/{y}", tags=["Maps"])
def get_residential_tile(
    z: int,
    x: int,
    y: int,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: Session = Depends(get_db_session),
):
    """
    Serves Mapbox Vector Tiles (MVT) for Residential Supply (Unified View).
    """
    sql = text("""
        WITH mvtgeom AS (
            SELECT 
                ST_AsMVTGeom(
                    ST_Transform(geometry, 3857),
                    ST_TileEnvelope(:z, :x, :y)
                ) AS geom,
                id,
                name,
                type,
                price,
                source
            FROM view_residential_supply
            WHERE ST_Intersects(
                ST_Transform(geometry, 3857),
                ST_TileEnvelope(:z, :x, :y)
            )
        )
        SELECT ST_AsMVT(mvtgeom.*, 'default', 4096, 'geom') AS mvt
        FROM mvtgeom;
    """)

    with db.bind.connect() as conn:
        result = conn.execute(sql, {"z": z, "x": x, "y": y}).scalar()

    return Response(content=result, media_type="application/vnd.mapbox-vector-tile")


@router.get("/grid", response_model=GridResponse)
def get_analytics_grid(
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: Session = Depends(get_db_session),
):
    """
    Returns a grid of hexagon data points for the heatmap.
    Fetches pre-calculated H3 suitability grid from the database.
    """
    import h3
    from src.models.grid import SuitabilityGrid

    # Fetch all grid cells
    # In a real app, you might want to filter by viewport (bbox)
    grid_cells = db.query(SuitabilityGrid).all()

    hexagons = []
    for cell in grid_cells:
        # Convert H3 index to lat/lon center
        lat, lon = h3.cell_to_latlng(cell.h3_index)

        hexagons.append(
            HexagonData(
                position=[lon, lat],  # Deck.gl expects [lon, lat]
                value=cell.score,
            )
        )

    return GridResponse(hexagons=hexagons)


# ============ H3 Hexagon Overlay Endpoints ============


class H3HexagonItem(BaseModel):
    h3_index: str
    value: float
    label: str | None = None


class H3HexagonResponse(BaseModel):
    metric: str
    resolution: int
    count: int
    min_value: float
    max_value: float
    hexagons: list[H3HexagonItem]


@router.get("/h3-hexagons", response_model=H3HexagonResponse)
def get_h3_hexagons(
    metric: str = "poi_total",
    resolution: int = 9,
    min_lat: float | None = None,
    max_lat: float | None = None,
    min_lon: float | None = None,
    max_lon: float | None = None,
    limit: int = 5000,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
):
    """
    Returns H3 hexagon data for overlay visualization.

    Metrics available:
    - poi_total: Total POI count
    - poi_school: School count
    - poi_transit_stop: Transit stop count
    - avg_price: Average property price
    - property_count: Property transaction count
    - transit_total: Total transit accessibility
    """
    from pathlib import Path

    import pandas as pd

    # Load H3 features based on resolution
    h3_path = Path("data/h3_features") / f"h3_features_res{resolution}.parquet"
    if not h3_path.exists():
        # Fall back to combined file
        h3_path = Path("data/h3_features/h3_features_all.parquet")
        if not h3_path.exists():
            raise HTTPException(status_code=404, detail="H3 features data not found")

    df = pd.read_parquet(h3_path)

    # Filter by resolution if using combined file
    if "resolution" in df.columns:
        df = df[df["resolution"] == resolution]

    # Filter by bounding box if provided
    if all(v is not None for v in [min_lat, max_lat, min_lon, max_lon]):
        df = df[
            (df["centroid_lat"] >= min_lat)
            & (df["centroid_lat"] <= max_lat)
            & (df["centroid_lon"] >= min_lon)
            & (df["centroid_lon"] <= max_lon)
        ]

    # Validate metric exists
    if metric not in df.columns:
        available = [
            c
            for c in df.columns
            if not c.startswith(("h3_", "centroid", "is_", "resolution"))
        ]
        raise HTTPException(
            status_code=400,
            detail=f"Metric '{metric}' not found. Available: {available[:20]}",
        )

    # Filter out NaN values and limit
    df = df[df[metric].notna()].head(limit)

    if df.empty:
        return H3HexagonResponse(
            metric=metric,
            resolution=resolution,
            count=0,
            min_value=0,
            max_value=0,
            hexagons=[],
        )

    min_val = float(df[metric].min())
    max_val = float(df[metric].max())

    hexagons = [
        H3HexagonItem(h3_index=row["h3_index"], value=float(row[metric]), label=None)
        for _, row in df.iterrows()
    ]

    return H3HexagonResponse(
        metric=metric,
        resolution=resolution,
        count=len(hexagons),
        min_value=min_val,
        max_value=max_val,
        hexagons=hexagons,
    )


@router.get("/h3-hexagons/metrics")
def get_available_metrics(
    resolution: int = 9,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
):
    """
    Returns list of available metrics for H3 hexagon overlay.
    """
    from pathlib import Path

    import pandas as pd

    h3_path = Path("data/h3_features") / f"h3_features_res{resolution}.parquet"
    if not h3_path.exists():
        h3_path = Path("data/h3_features/h3_features_all.parquet")
        if not h3_path.exists():
            raise HTTPException(status_code=404, detail="H3 features data not found")

    df = pd.read_parquet(h3_path)

    # Filter out internal columns
    exclude_prefixes = ("h3_", "centroid", "is_", "resolution", "Unnamed")
    metrics = [
        c for c in df.columns if not any(c.startswith(p) for p in exclude_prefixes)
    ]

    # Categorize metrics
    categories = {
        "poi": [m for m in metrics if m.startswith("poi_")],
        "transit": [m for m in metrics if m.startswith("transit_")],
        "property": [
            m
            for m in metrics
            if m
            in [
                "avg_price",
                "median_price",
                "std_price",
                "property_count",
                "avg_building_area",
                "avg_land_area",
                "avg_building_age",
            ]
        ],
        "other": [
            m
            for m in metrics
            if not m.startswith(("poi_", "transit_"))
            and m
            not in [
                "avg_price",
                "median_price",
                "std_price",
                "property_count",
                "avg_building_area",
                "avg_land_area",
                "avg_building_age",
            ]
        ],
    }

    return {
        "resolution": resolution,
        "total_metrics": len(metrics),
        "categories": categories,
    }


@router.get("/flood-risk")
def get_flood_risk_by_district(
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
):
    """
    Returns flood risk data aggregated by district.
    """
    from pathlib import Path

    import pandas as pd

    flood_path = Path("data/flood-warning.csv")
    if not flood_path.exists():
        raise HTTPException(status_code=404, detail="Flood risk data not found")

    df = pd.read_csv(flood_path)

    # Aggregate by district
    district_risk = (
        df.groupby("District")
        .agg({"risk_id": "count", "risk_group": "min"})
        .reset_index()
    )

    district_risk.columns = ["district", "risk_count", "highest_risk_group"]

    return {
        "count": len(district_risk),
        "items": district_risk.to_dict(orient="records"),
    }


@router.post("/cannibalization")
def analyze_cannibalization(
    request: CannibalizationRequest,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: Session = Depends(get_db_session),
):
    """
    Analyze the cannibalization impact of a new site on existing sites using the Huff Model.
    """
    result = analytics_service.calculate_cannibalization(
        db,
        request.new_site.model_dump(),
        [s.model_dump() for s in request.existing_sites],
        request.beta,
    )

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result
