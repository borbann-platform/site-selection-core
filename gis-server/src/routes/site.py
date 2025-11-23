import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.config.database import get_db_session
from src.models.site import (
    AnalysisDetails,
    AnalysisSummary,
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    NearbyRequest,
    SiteRequest,
    SiteResponse,
)

router = APIRouter()

# Define the categories for magnets
MAGNET_CATEGORIES = [
    "office",
    "school",
    "train_station",
    "subway_station",
    "university",
    "mall",
    "hospital",
    "hotel",
    "attraction",
    "park",
    "condominiums",
]


@router.get("/site/{site_id}", response_model=SiteResponse)
def get_site_details(site_id: str, db: Session = Depends(get_db_session)):
    """
    Retrieve details for a specific site.
    Fetches from 'saved_sites' table if UUID, otherwise falls back to mock for demo IDs.
    """
    import uuid

    from src.models.db import SavedSite

    # 1. Try to fetch from DB (if UUID)
    try:
        uuid_obj = uuid.UUID(site_id)
        site = db.query(SavedSite).filter(SavedSite.id == uuid_obj).first()
        if site and site.analysis_data:
            # Assuming analysis_data matches the SiteResponse structure
            # We might need to validate or map it if the schema evolves
            return SiteResponse(**site.analysis_data)
    except ValueError:
        pass  # Not a UUID, continue to mock check

    # 2. Mock data based on site_id (Legacy/Demo)
    if site_id == "A":
        return SiteResponse(
            site_score=85.0,
            summary=AnalysisSummary(
                competitors_count=8, magnets_count=12, traffic_potential="High"
            ),
            details=AnalysisDetails(
                nearby_competitors=["Comp A1", "Comp A2"],
                nearby_magnets=["Mall A", "Station A"],
            ),
        )
    if site_id == "B":
        return SiteResponse(
            site_score=92.0,
            summary=AnalysisSummary(
                competitors_count=2, magnets_count=5, traffic_potential="Medium"
            ),
            details=AnalysisDetails(
                nearby_competitors=["Comp B1"], nearby_magnets=["Park B"]
            ),
        )

    # Default mock for any other ID
    return SiteResponse(
        site_score=78.0,
        summary=AnalysisSummary(
            competitors_count=4, magnets_count=8, traffic_potential="Medium"
        ),
        details=AnalysisDetails(
            nearby_competitors=["Generic Comp 1"], nearby_magnets=["Generic Magnet 1"]
        ),
    )


@router.post(
    "/site/analyze",
    response_model=SiteResponse,
    summary="Analyze a geographic site for business potential",
)
def analyze_site(payload: SiteRequest, db: Session = Depends(get_db_session)):
    """
    Analyzes a site's potential by counting competitors and traffic-generating
    "magnets" within a specified radius.
    """
    # This SQL query uses PostGIS's ST_DWithin for a fast, indexed radius search.
    # It counts competitors (matching the target_category) and magnets separately.
    # It also aggregates the names of nearby places for inspection.
    query = text(
        """
        WITH nearby_pois AS (
            SELECT
                name,
                amenity,
                CASE
                    WHEN amenity = :target_category THEN 'competitor'
                    WHEN amenity = ANY(:magnet_categories) THEN 'magnet'
                END as poi_type
            FROM pois
            WHERE ST_DWithin(
                geometry,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                :radius
            )
        )
        SELECT
            poi_type,
            COUNT(*) as count,
            STRING_AGG(name, ', ') as names
        FROM nearby_pois
        WHERE poi_type IS NOT NULL
        GROUP BY poi_type;
    """
    )

    pop_query = text(
        """
        SELECT COALESCE(SUM(population_density), 0) as total_pop
        FROM demographics
        WHERE ST_DWithin(
            geometry,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
            :radius
        )
        """
    )

    try:
        with db.bind.connect() as conn:
            result = conn.execute(
                query,
                {
                    "lat": payload.latitude,
                    "lon": payload.longitude,
                    "radius": payload.radius_meters,
                    "target_category": payload.target_category,
                    "magnet_categories": MAGNET_CATEGORIES,
                },
            ).fetchall()

            pop_result = conn.execute(
                pop_query,
                {
                    "lat": payload.latitude,
                    "lon": payload.longitude,
                    "radius": payload.radius_meters,
                },
            ).scalar()

        # Process the query results
        competitors_count = 0
        magnets_count = 0
        nearby_competitors = []
        nearby_magnets = []
        total_population = int(pop_result) if pop_result else 0

        for row in result:
            if row.poi_type == "competitor":
                competitors_count = row.count
                if row.names:
                    nearby_competitors = [name.strip() for name in row.names.split(",")]
            elif row.poi_type == "magnet":
                magnets_count = row.count
                if row.names:
                    nearby_magnets = [name.strip() for name in row.names.split(",")]

        # Calculate the site score (avoid division by zero)
        # Add 1 to the denominator to prevent zero division and moderate the score
        site_score = (magnets_count * 10 + total_population / 1000) / (
            competitors_count + 1
        )
        site_score = min(max(site_score, 0), 100)  # Normalize to 0-100 roughly

        # Determine traffic potential
        if site_score > 80:
            traffic_potential = "Very High"
        elif site_score > 50:
            traffic_potential = "High"
        elif site_score > 20:
            traffic_potential = "Medium"
        else:
            traffic_potential = "Low"

        # Assemble the response
        return SiteResponse(
            site_score=round(site_score, 2),
            summary=AnalysisSummary(
                competitors_count=competitors_count,
                magnets_count=magnets_count,
                traffic_potential=traffic_potential,
                total_population=total_population,
            ),
            details=AnalysisDetails(
                nearby_competitors=nearby_competitors,
                nearby_magnets=nearby_magnets,
            ),
        )

    except Exception as e:
        # For production, log the error and return a more generic message
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during analysis: {e}. Please check if the 'pois' table exists and is populated.",
        )


@router.post(
    "/site/nearby",
    response_model=GeoJSONFeatureCollection,
    summary="Get nearby POIs as GeoJSON",
)
def get_nearby_pois(payload: NearbyRequest, db: Session = Depends(get_db_session)):
    """
    Returns a GeoJSON FeatureCollection of POIs within the specified radius
    matching the given categories.
    """
    query = text(
        """
        SELECT
            name,
            amenity,
            ST_AsGeoJSON(geometry) as geom_json
        FROM pois
        WHERE ST_DWithin(
            geometry,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
            :radius
        )
        AND amenity = ANY(:categories)
    """
    )

    try:
        with db.bind.connect() as conn:
            result = conn.execute(
                query,
                {
                    "lon": payload.longitude,
                    "lat": payload.latitude,
                    "radius": payload.radius_meters,
                    "categories": payload.categories,
                },
            ).fetchall()

        features = []
        for row in result:
            features.append(
                GeoJSONFeature(
                    geometry=json.loads(row.geom_json),
                    properties={
                        "name": row.name,
                        "amenity": row.amenity,
                    },
                )
            )

        return GeoJSONFeatureCollection(features=features)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while fetching nearby POIs: {e}",
        )
