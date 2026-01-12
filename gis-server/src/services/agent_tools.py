"""
Agent tools for LangGraph ReAct agent.
Wraps existing API services as callable tools for the AI agent.
"""

import json
import logging
import random
from typing import Literal

from langchain_core.tools import tool
from sqlalchemy import text
from src.config.database import SessionLocal
from src.services.catchment import catchment_service
from src.services.location_intelligence import location_intelligence_service

logger = logging.getLogger(__name__)


# =============================================================================
# Site Analysis Tools
# =============================================================================


@tool
def analyze_site(
    latitude: float,
    longitude: float,
    radius_meters: int = 1000,
    target_category: str = "restaurant",
) -> str:
    """
    Analyze a location for business potential by counting competitors and traffic magnets nearby.

    Use this when the user wants to evaluate a location for opening a business,
    or wants to understand the competitive landscape of an area.

    Args:
        latitude: Latitude of the location to analyze (e.g., 13.7563)
        longitude: Longitude of the location to analyze (e.g., 100.5018)
        radius_meters: Search radius in meters (default 1000)
        target_category: Business category to find competitors for (e.g., restaurant, cafe, retail)

    Returns:
        JSON with site_score, competitors_count, magnets_count, and traffic_potential

    """
    magnet_categories = [
        "school",
        "transit_stop",
        "tourist_attraction",
        "museum",
        "water_transport",
        "police_station",
        "hospital",
        "mall",
        "university",
        "park",
    ]

    try:
        with SessionLocal() as db:
            query = text("""
                WITH nearby_pois AS (
                    SELECT
                        name,
                        type,
                        CASE
                            WHEN type = :target_category THEN 'competitor'
                            WHEN type = ANY(:magnet_categories) THEN 'magnet'
                        END as poi_type
                    FROM view_all_pois
                    WHERE ST_DWithin(
                        geometry,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                        :radius
                    )
                    AND (type = :target_category OR type = ANY(:magnet_categories))
                )
                SELECT
                    COALESCE(SUM(CASE WHEN poi_type = 'competitor' THEN 1 ELSE 0 END), 0) as competitors_count,
                    COALESCE(SUM(CASE WHEN poi_type = 'magnet' THEN 1 ELSE 0 END), 0) as magnets_count,
                    array_agg(DISTINCT name) FILTER (WHERE poi_type = 'competitor') as competitor_names,
                    array_agg(DISTINCT name) FILTER (WHERE poi_type = 'magnet') as magnet_names
                FROM nearby_pois
            """)

            result = db.execute(
                query,
                {
                    "lat": latitude,
                    "lon": longitude,
                    "radius": radius_meters,
                    "target_category": target_category,
                    "magnet_categories": magnet_categories,
                },
            ).fetchone()

            if result is None:
                return json.dumps({"error": "No data found for this location"})

            competitors = getattr(result, "competitors_count", 0) or 0
            magnets = getattr(result, "magnets_count", 0) or 0

            # Calculate traffic potential
            if magnets >= 10:
                traffic_potential = "High"
            elif magnets >= 5:
                traffic_potential = "Medium"
            else:
                traffic_potential = "Low"

            # Simple scoring: more magnets = better, fewer competitors = better
            score = min(100, max(0, 50 + (magnets * 3) - (competitors * 2)))

            return json.dumps(
                {
                    "site_score": score,
                    "competitors_count": competitors,
                    "magnets_count": magnets,
                    "traffic_potential": traffic_potential,
                    "nearby_competitors": (
                        getattr(result, "competitor_names", None) or []
                    )[:5],
                    "nearby_magnets": (getattr(result, "magnet_names", None) or [])[:5],
                    "location": {"lat": latitude, "lon": longitude},
                    "radius_meters": radius_meters,
                },
                ensure_ascii=False,
            )

    except Exception as e:
        logger.error(f"Site analysis failed: {e}")
        return json.dumps({"error": str(e)})


# =============================================================================
# Location Intelligence Tools
# =============================================================================


@tool
def get_location_intelligence(
    latitude: float,
    longitude: float,
    radius_meters: int = 1000,
) -> str:
    """
    Get comprehensive location intelligence scores including transit, walkability, schools, flood risk, and noise.

    Use this when the user wants to evaluate how livable or accessible a location is,
    or wants to understand the quality of an area for residential or commercial purposes.

    Args:
        latitude: Latitude of the location (e.g., 13.7563)
        longitude: Longitude of the location (e.g., 100.5018)
        radius_meters: Search radius in meters (default 1000)

    Returns:
        JSON with transit_score, walkability_score, schools_score, flood_risk, noise_level, and composite_score

    """
    try:
        with SessionLocal() as db:
            result = location_intelligence_service.analyze(
                db=db,
                lat=latitude,
                lon=longitude,
                radius=radius_meters,
            )

            return json.dumps(
                {
                    "composite_score": result.composite_score,
                    "transit": {
                        "score": result.transit.score,
                        "nearest_rail": result.transit.nearest_rail.model_dump()
                        if result.transit.nearest_rail
                        else None,
                        "bus_stops_500m": result.transit.bus_stops_500m,
                        "description": result.transit.description,
                    },
                    "walkability": {
                        "score": result.walkability.score,
                        "total_amenities": result.walkability.total_amenities,
                        "categories": [
                            {"category": cat.category, "count": cat.count}
                            for cat in result.walkability.categories
                        ],
                        "description": result.walkability.description,
                    },
                    "schools": {
                        "score": result.schools.score,
                        "total_within_2km": result.schools.total_within_2km,
                        "by_level": result.schools.by_level,
                        "nearest": result.schools.nearest.model_dump()
                        if result.schools.nearest
                        else None,
                        "description": result.schools.description,
                    },
                    "flood_risk": {
                        "level": result.flood_risk.level,
                        "risk_group": result.flood_risk.risk_group,
                        "description": result.flood_risk.description,
                    },
                    "noise": {
                        "level": result.noise.level,
                        "nearest_highway_m": result.noise.nearest_highway_m,
                        "description": result.noise.description,
                    },
                },
                ensure_ascii=False,
            )

    except Exception as e:
        logger.error(f"Location intelligence failed: {e}")
        return json.dumps({"error": str(e)})


# =============================================================================
# Price Prediction Tools
# =============================================================================


@tool
def predict_property_price(
    latitude: float,
    longitude: float,
    building_area_sqm: float,
    land_area_sqwah: float = 50.0,
    building_age_years: int = 5,
    floors: int = 2,
    building_style: Literal[
        "บ้านเดี่ยว", "ทาวน์เฮ้าส์", "บ้านแฝด", "อาคารพาณิชย์", "ตึกแถว"
    ] = "บ้านเดี่ยว",
) -> str:
    """
    Predict the price of a property and explain which factors contribute to the price.

    NOTE: Currently returns MOCK data. HGT model migration pending.

    Args:
        latitude: Latitude of the property location
        longitude: Longitude of the property location
        building_area_sqm: Building area in square meters
        land_area_sqwah: Land area in square wah (1 sq wah = 4 sqm)
        building_age_years: Age of the building in years
        floors: Number of floors
        building_style: Type of building (บ้านเดี่ยว=detached, ทาวน์เฮ้าส์=townhouse, etc.)

    Returns:
        JSON with predicted_price, base_price, and feature_contributions (MOCK DATA)

    """
    # Generate mock prediction based on building area
    base_price_per_sqm = random.uniform(25_000, 45_000)
    base_price = building_area_sqm * base_price_per_sqm
    predicted_price = base_price * random.uniform(0.9, 1.1)
    district_avg = base_price * random.uniform(0.85, 1.15)

    # Mock contributions
    contributions = [
        {
            "feature": "Building Area (sqm)",
            "value": building_area_sqm,
            "impact_thb": round(random.uniform(100_000, 500_000), 0),
            "direction": "positive",
        },
        {
            "feature": "Transit Stops (1km)",
            "value": random.randint(1, 5),
            "impact_thb": round(random.uniform(50_000, 200_000), 0),
            "direction": "positive",
        },
        {
            "feature": "Building Age (years)",
            "value": building_age_years,
            "impact_thb": round(random.uniform(-150_000, -50_000), 0),
            "direction": "negative",
        },
        {
            "feature": "District Avg Price/sqm",
            "value": round(district_avg / building_area_sqm, 0),
            "impact_thb": round(random.uniform(-100_000, 100_000), 0),
            "direction": "positive" if random.random() > 0.5 else "negative",
        },
        {
            "feature": "POIs within 500m",
            "value": random.randint(5, 20),
            "impact_thb": round(random.uniform(20_000, 80_000), 0),
            "direction": "positive",
        },
    ]

    price_vs_district = ((predicted_price - district_avg) / district_avg) * 100

    return json.dumps(
        {
            "mock_mode": True,
            "predicted_price_thb": round(predicted_price, 0),
            "base_price_thb": round(base_price * 0.95, 0),
            "district_avg_price_thb": round(district_avg, 0),
            "price_vs_district_percent": round(price_vs_district, 1),
            "top_price_factors": contributions,
            "property_details": {
                "building_area_sqm": building_area_sqm,
                "land_area_sqwah": land_area_sqwah,
                "building_style": building_style,
                "age_years": building_age_years,
                "floors": floors,
            },
            "note": "This is mock data. HGT model migration pending.",
        },
        ensure_ascii=False,
    )


# =============================================================================
# Property Search Tools
# =============================================================================


@tool
def search_properties(
    district: str | None = None,
    building_style: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    limit: int = 10,
) -> str:
    """
    Search for properties in the database with optional filters.

    Use this when the user wants to find properties matching certain criteria,
    or wants to explore available properties in a specific area.

    Args:
        district: Filter by district name in Thai (e.g., บางกะปิ, สาทร)
        building_style: Filter by building type (บ้านเดี่ยว, ทาวน์เฮ้าส์, บ้านแฝด, etc.)
        min_price: Minimum price in THB
        max_price: Maximum price in THB
        limit: Maximum number of results (default 10, max 50)

    Returns:
        JSON with count and list of matching properties

    """
    limit = min(limit, 50)  # Cap at 50

    try:
        with SessionLocal() as db:
            query = text("""
                SELECT
                    id, amphur, tumbon, building_style_desc,
                    building_area, land_area, building_age,
                    total_price, no_of_floor,
                    ST_Y(geom::geometry) as lat,
                    ST_X(geom::geometry) as lon
                FROM appraised_house_price
                WHERE total_price IS NOT NULL
                AND (:district IS NULL OR amphur = :district)
                AND (:style IS NULL OR building_style_desc = :style)
                AND (:min_price IS NULL OR total_price >= :min_price)
                AND (:max_price IS NULL OR total_price <= :max_price)
                ORDER BY total_price
                LIMIT :limit
            """)

            results = db.execute(
                query,
                {
                    "district": district,
                    "style": building_style,
                    "min_price": min_price,
                    "max_price": max_price,
                    "limit": limit,
                },
            ).fetchall()

            properties = [
                {
                    "id": r.id,
                    "district": r.amphur,
                    "subdistrict": r.tumbon,
                    "building_style": r.building_style_desc,
                    "building_area_sqm": r.building_area,
                    "land_area_sqwah": r.land_area,
                    "age_years": r.building_age,
                    "price_thb": r.total_price,
                    "floors": r.no_of_floor,
                    "lat": r.lat,
                    "lon": r.lon,
                }
                for r in results
            ]

            return json.dumps(
                {
                    "count": len(properties),
                    "filters_applied": {
                        "district": district,
                        "building_style": building_style,
                        "min_price": min_price,
                        "max_price": max_price,
                    },
                    "properties": properties,
                },
                ensure_ascii=False,
            )

    except Exception as e:
        logger.error(f"Property search failed: {e}")
        return json.dumps({"error": str(e)})


@tool
def get_nearby_properties(
    latitude: float,
    longitude: float,
    radius_meters: int = 500,
    limit: int = 10,
) -> str:
    """
    Find comparable properties near a specific location.

    Use this when the user wants to find properties close to a specific location,
    or wants to compare prices in a neighborhood.

    Args:
        latitude: Center latitude
        longitude: Center longitude
        radius_meters: Search radius in meters (default 500)
        limit: Maximum number of results (default 10, max 50)

    Returns:
        JSON with nearby properties and their details

    """
    limit = min(limit, 50)

    try:
        with SessionLocal() as db:
            query = text("""
                SELECT
                    id, amphur, tumbon, building_style_desc,
                    building_area, land_area, building_age,
                    total_price, no_of_floor,
                    ST_Y(geom::geometry) as lat,
                    ST_X(geom::geometry) as lon,
                    ST_Distance(
                        geom::geography,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                    ) as distance_m
                FROM appraised_house_price
                WHERE total_price IS NOT NULL
                AND ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radius
                )
                ORDER BY distance_m
                LIMIT :limit
            """)

            results = db.execute(
                query,
                {
                    "lat": latitude,
                    "lon": longitude,
                    "radius": radius_meters,
                    "limit": limit,
                },
            ).fetchall()

            properties = [
                {
                    "id": r.id,
                    "district": r.amphur,
                    "building_style": r.building_style_desc,
                    "building_area_sqm": r.building_area,
                    "price_thb": r.total_price,
                    "distance_m": round(r.distance_m, 0),
                    "lat": r.lat,
                    "lon": r.lon,
                }
                for r in results
            ]

            # Calculate avg price if we have results
            avg_price = (
                sum(p["price_thb"] for p in properties) / len(properties)
                if properties
                else 0
            )

            return json.dumps(
                {
                    "center": {"lat": latitude, "lon": longitude},
                    "radius_meters": radius_meters,
                    "count": len(properties),
                    "avg_price_thb": round(avg_price, 0),
                    "properties": properties,
                },
                ensure_ascii=False,
            )

    except Exception as e:
        logger.error(f"Nearby properties search failed: {e}")
        return json.dumps({"error": str(e)})


# =============================================================================
# Market Statistics Tools
# =============================================================================


@tool
def get_market_statistics(district: str | None = None) -> str:
    """
    Get real estate market statistics by district.

    Use this when the user wants to understand market trends,
    average prices, or compare different districts.

    Args:
        district: Optional district name to filter (e.g., บางกะปิ). If None, returns all districts.

    Returns:
        JSON with market statistics including average prices, counts by district and building style

    """
    try:
        with SessionLocal() as db:
            if district:
                query = text("""
                    SELECT
                        amphur,
                        COUNT(*) as count,
                        AVG(total_price) as avg_price,
                        MIN(total_price) as min_price,
                        MAX(total_price) as max_price,
                        AVG(total_price / NULLIF(building_area, 0)) as avg_price_per_sqm
                    FROM appraised_house_price
                    WHERE total_price IS NOT NULL
                    AND amphur = :district
                    GROUP BY amphur
                """)
                results = db.execute(query, {"district": district}).fetchall()
            else:
                query = text("""
                    SELECT
                        amphur,
                        COUNT(*) as count,
                        AVG(total_price) as avg_price,
                        MIN(total_price) as min_price,
                        MAX(total_price) as max_price,
                        AVG(total_price / NULLIF(building_area, 0)) as avg_price_per_sqm
                    FROM appraised_house_price
                    WHERE total_price IS NOT NULL
                    GROUP BY amphur
                    ORDER BY avg_price DESC
                    LIMIT 20
                """)
                results = db.execute(query).fetchall()

            districts = [
                {
                    "district": r.amphur,
                    "property_count": r.count,
                    "avg_price_thb": round(r.avg_price, 0),
                    "min_price_thb": round(r.min_price, 0),
                    "max_price_thb": round(r.max_price, 0),
                    "avg_price_per_sqm": round(r.avg_price_per_sqm, 0)
                    if r.avg_price_per_sqm
                    else None,
                }
                for r in results
            ]

            return json.dumps(
                {
                    "filter": {"district": district} if district else "all",
                    "districts": districts,
                },
                ensure_ascii=False,
            )

    except Exception as e:
        logger.error(f"Market statistics failed: {e}")
        return json.dumps({"error": str(e)})


# =============================================================================
# Catchment Analysis Tools
# =============================================================================


@tool
def analyze_catchment(
    latitude: float,
    longitude: float,
    minutes: int = 15,
    mode: Literal["walk", "drive"] = "walk",
) -> str:
    """
    Analyze the catchment area (reachable zone) from a location within a given travel time.

    Use this when the user wants to understand how far people can travel from a location,
    or wants to estimate the population within reach of a business location.

    Args:
        latitude: Center latitude
        longitude: Center longitude
        minutes: Travel time in minutes (default 15)
        mode: Travel mode - 'walk' or 'drive'

    Returns:
        JSON with isochrone geometry, population estimate, and catchment score

    """
    try:
        isochrone = catchment_service.get_isochrone(
            lat=latitude,
            lon=longitude,
            minutes=minutes,
            mode=mode,
        )

        if not isochrone:
            return json.dumps(
                {
                    "error": "Could not generate isochrone. The graph may not cover this area.",
                    "location": {"lat": latitude, "lon": longitude},
                }
            )

        # Get population within catchment
        population = isochrone.get("population", 0)
        area_km2 = isochrone.get("area_km2", 0)

        # Simple catchment score based on population density
        density = population / area_km2 if area_km2 > 0 else 0
        if density > 10000:
            score = "Excellent"
        elif density > 5000:
            score = "Good"
        elif density > 2000:
            score = "Moderate"
        else:
            score = "Low"

        return json.dumps(
            {
                "center": {"lat": latitude, "lon": longitude},
                "travel_time_minutes": minutes,
                "mode": mode,
                "estimated_population": population,
                "area_km2": round(area_km2, 2),
                "population_density": round(density, 0),
                "catchment_score": score,
                # Exclude full geometry to keep response size manageable
                "has_geometry": bool(isochrone.get("geometry")),
            },
            ensure_ascii=False,
        )

    except Exception as e:
        logger.error(f"Catchment analysis failed: {e}")
        return json.dumps({"error": str(e)})


# =============================================================================
# Tool Registry
# =============================================================================

# List of all available tools for the agent
ALL_TOOLS = [
    analyze_site,
    get_location_intelligence,
    predict_property_price,
    search_properties,
    get_nearby_properties,
    get_market_statistics,
    analyze_catchment,
]
