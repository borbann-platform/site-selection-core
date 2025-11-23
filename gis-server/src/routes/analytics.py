from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.config.database import get_db_session
from src.services.analytics import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


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
def get_pois_tile(z: int, x: int, y: int, db: Session = Depends(get_db_session)):
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


@router.get("/grid", response_model=GridResponse)
def get_analytics_grid(db: Session = Depends(get_db_session)):
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


@router.post("/cannibalization")
def analyze_cannibalization(
    request: CannibalizationRequest, db: Session = Depends(get_db_session)
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
