"""
Agent tools for LangGraph ReAct agent.
Wraps existing API services as callable tools for the AI agent.

IMPORTANT FOR LLM:
- Always use tools BEFORE answering questions about properties, locations, or markets
- Search for data first, then formulate your response based on actual results
- Combine multiple tools for comprehensive analysis (e.g., search_properties + get_location_intelligence)
"""

import json
import logging
import time
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from typing import Any, Literal

from langchain_core.tools import tool
from sqlalchemy import func, text
from src.config.database import SessionLocal
from src.models.realestate import HousePrice
from src.services.catchment import catchment_service
from src.services.location_intelligence import location_intelligence_service
from src.services.price_prediction import get_predictor

logger = logging.getLogger(__name__)
_GEOCODE_CACHE: dict[str, dict[str, float | str]] = {}
_GEOCODE_LAST_CALL_TS = 0.0


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

    WHEN TO USE THIS TOOL:
    - User asks "Is this a good location for a cafe/restaurant/shop?"
    - User wants to evaluate commercial potential of an area
    - User asks about competition or foot traffic at a location
    - User wants a site score or business viability assessment

    EXAMPLE QUERIES:
    - "Should I open a restaurant near Siam Paragon?"
    - "What's the business potential at lat 13.75, lon 100.53?"
    - "How many competitors are near Ekkamai?"

    Args:
        latitude: Latitude of the location (Bangkok is around 13.7-13.9)
        longitude: Longitude of the location (Bangkok is around 100.4-100.7)
        radius_meters: Search radius in meters (500-2000 recommended)
        target_category: Business type to analyze (restaurant, cafe, retail, hotel)

    Returns:
        JSON with site_score (0-100), competitors_count, magnets_count, traffic_potential (Low/Medium/High)
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
    Get comprehensive livability scores for a location: transit, walkability, schools, flood risk, noise.

    WHEN TO USE THIS TOOL:
    - User asks about quality of life or livability of an area
    - User wants transit score or transportation access info
    - User asks about schools nearby
    - User asks about flood risk or safety of an area
    - User wants walkability or amenity access information
    - User is evaluating a location for living/buying property

    EXAMPLE QUERIES:
    - "Is On Nut a good area to live?"
    - "What's the transit score near Asoke?"
    - "Are there schools near this property?"
    - "Is this area prone to flooding?"
    - "How walkable is Thonglor?"

    Args:
        latitude: Latitude of the location (Bangkok is around 13.7-13.9)
        longitude: Longitude of the location (Bangkok is around 100.4-100.7)
        radius_meters: Analysis radius (500-2000 recommended)

    Returns:
        JSON with composite_score (0-100), transit (score + details), walkability (score + amenities),
        schools (score + nearby schools), flood_risk (level), noise (level)
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
    Predict the market price of a property based on its features and location.

    WHEN TO USE THIS TOOL:
    - User asks "How much is this property worth?"
    - User wants a price estimate or valuation
    - User wants to understand what factors affect a property's price
    - User asks about fair market value

    EXAMPLE QUERIES:
    - "How much would a 200sqm house in Sukhumvit cost?"
    - "What's the value of my 3-year-old townhouse?"
    - "Estimate the price for a detached house at this location"

    Args:
        latitude: Property latitude
        longitude: Property longitude
        building_area_sqm: Building area in square meters (typical: 100-400)
        land_area_sqwah: Land area in square wah, 1 wah = 4 sqm (typical: 25-200)
        building_age_years: Age of building (0 = new construction)
        floors: Number of floors (typical: 1-4)
        building_style: Property type in Thai:
            - บ้านเดี่ยว = Detached house
            - ทาวน์เฮ้าส์ = Townhouse
            - บ้านแฝด = Semi-detached house
            - อาคารพาณิชย์ = Commercial building
            - ตึกแถว = Shophouse

    Returns:
        JSON with predicted_price_thb, price factors, and comparable analysis
    """
    try:
        # Get the best available predictor (HGT > Baseline+Hex2Vec > Baseline)
        predictor = get_predictor()

        with SessionLocal() as db:
            # Call real ML prediction service
            prediction = predictor.predict(
                db=db,
                lat=latitude,
                lon=longitude,
                building_area=building_area_sqm,
                land_area=land_area_sqwah,
                building_age=float(building_age_years),
                no_of_floor=float(floors),
                building_style=building_style,
            )

            # Format feature contributions for agent response
            contributions = [
                {
                    "feature": fc.feature_display,
                    "value": fc.value,
                    "impact_thb": round(fc.contribution, 0),
                    "direction": fc.direction,
                }
                for fc in prediction.feature_contributions[:5]  # Top 5 factors
            ]

            # Calculate price comparison with district
            price_vs_district = prediction.price_vs_district or 0.0

            # Map confidence to category
            confidence_level = (
                "high"
                if prediction.confidence > 0.7
                else "medium"
                if prediction.confidence > 0.5
                else "low"
            )

            return json.dumps(
                {
                    "predicted_price_thb": round(prediction.predicted_price, 0),
                    "confidence": confidence_level,
                    "confidence_score": round(prediction.confidence, 2),
                    "model_type": prediction.model_type,
                    "district": prediction.district,
                    "district_avg_price_thb": round(prediction.district_avg_price, 0)
                    if prediction.district_avg_price
                    else None,
                    "price_vs_district_percent": round(price_vs_district, 1),
                    "h3_cell_avg_price_thb": round(prediction.h3_cell_avg_price, 0)
                    if prediction.h3_cell_avg_price
                    else None,
                    "is_cold_start": prediction.is_cold_start,
                    "top_price_factors": contributions,
                    "property_details": {
                        "building_area_sqm": building_area_sqm,
                        "land_area_sqwah": land_area_sqwah,
                        "building_style": building_style,
                        "age_years": building_age_years,
                        "floors": floors,
                        "h3_index": prediction.h3_index,
                    },
                },
                ensure_ascii=False,
            )

    except Exception as e:
        logger.error(f"Price prediction failed: {e}")
        return json.dumps(
            {
                "error": str(e),
                "note": "Price prediction service unavailable. Please ensure the ML model is trained.",
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
    min_lat: float | None = None,
    max_lat: float | None = None,
    min_lon: float | None = None,
    max_lon: float | None = None,
    limit: int = 10,
) -> str:
    """
    Search for properties in the database with filters. Returns real property listings.

    WHEN TO USE THIS TOOL:
    - User asks to find/search/show properties
    - User specifies criteria like budget, area, or property type
    - User asks "What properties are available in X?"
    - User wants a list of options matching their requirements
    - User has drawn a BOUNDING BOX on the map and asks about properties in that area

    EXAMPLE QUERIES:
    - "Find houses under 5 million baht"
    - "Show me townhouses in บางกะปิ"
    - "What detached houses are available between 3-8 million?"
    - "Find properties in Ladprao district"
    - "หาบ้านในพื้นที่นี้" (with bbox from map selection)

    DISTRICT NAMES (use Thai):
    บางกะปิ, สาทร, วัฒนา, พระโขนง, ลาดพร้าว, จตุจักร, บางนา, ห้วยขวาง, คลองเตย, etc.

    BUILDING STYLES (use Thai):
    - บ้านเดี่ยว = Detached house
    - ทาวน์เฮ้าส์ = Townhouse
    - บ้านแฝด = Semi-detached
    - ตึกแถว = Shophouse

    BOUNDING BOX:
    When user selects an area on the map, use min_lat, max_lat, min_lon, max_lon
    to filter properties within that geographic region.

    Args:
        district: District name in Thai (e.g., บางกะปิ, สาทร, วัฒนา)
        building_style: Property type in Thai (e.g., บ้านเดี่ยว, ทาวน์เฮ้าส์)
        min_price: Minimum price in THB (e.g., 2000000 for 2M)
        max_price: Maximum price in THB (e.g., 10000000 for 10M)
        min_lat: Minimum latitude for bounding box (south boundary)
        max_lat: Maximum latitude for bounding box (north boundary)
        min_lon: Minimum longitude for bounding box (west boundary)
        max_lon: Maximum longitude for bounding box (east boundary)
        limit: Number of results (default 10, max 50)

    Returns:
        JSON with count and list of properties (id, district, style, area, price, location)
    """
    limit = min(limit, 50)  # Cap at 50

    try:
        with SessionLocal() as db:
            # Check if bbox filtering is requested
            has_bbox = all(v is not None for v in [min_lat, max_lat, min_lon, max_lon])

            if has_bbox:
                # Use raw SQL with PostGIS for spatial filtering
                sql = """
                    SELECT
                        id, amphur, tumbon, building_style_desc,
                        building_area, land_area, building_age,
                        total_price, no_of_floor,
                        ST_Y(geometry) as lat,
                        ST_X(geometry) as lon
                    FROM house_prices
                    WHERE total_price IS NOT NULL
                    AND ST_Within(
                        geometry,
                        ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
                    )
                """
                params: dict[str, float | str | int | None] = {
                    "min_lon": min_lon,
                    "min_lat": min_lat,
                    "max_lon": max_lon,
                    "max_lat": max_lat,
                }

                # Add optional filters
                if district:
                    sql += " AND amphur = :district"
                    params["district"] = district
                if building_style:
                    sql += " AND building_style_desc = :building_style"
                    params["building_style"] = building_style
                if min_price is not None:
                    sql += " AND total_price >= :min_price"
                    params["min_price"] = min_price
                if max_price is not None:
                    sql += " AND total_price <= :max_price"
                    params["max_price"] = max_price

                sql += " ORDER BY total_price LIMIT :limit"
                params["limit"] = limit

                results = db.execute(text(sql), params).fetchall()

                properties = [
                    {
                        "id": r.id,
                        "source_type": "house_price",
                        "listing_key": f"house:{r.id}",
                        "house_ref": f"house:{r.id}",
                        "locator": f"house:{r.id}",
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

            else:
                # Use SQLAlchemy ORM for non-spatial queries
                query = db.query(HousePrice).filter(HousePrice.total_price.isnot(None))

                if district:
                    query = query.filter(HousePrice.amphur == district)
                if building_style:
                    query = query.filter(
                        HousePrice.building_style_desc == building_style
                    )
                if min_price is not None:
                    query = query.filter(HousePrice.total_price >= min_price)
                if max_price is not None:
                    query = query.filter(HousePrice.total_price <= max_price)

                results = (
                    query.with_entities(
                        HousePrice,
                        func.ST_X(HousePrice.geometry).label("lon"),
                        func.ST_Y(HousePrice.geometry).label("lat"),
                    )
                    .order_by(HousePrice.total_price)
                    .limit(limit)
                    .all()
                )

                properties = [
                    {
                        "id": row.id,
                        "source_type": "house_price",
                        "listing_key": f"house:{row.id}",
                        "house_ref": f"house:{row.id}",
                        "locator": f"house:{row.id}",
                        "district": row.amphur,
                        "subdistrict": row.tumbon,
                        "building_style": row.building_style_desc,
                        "building_area_sqm": row.building_area,
                        "land_area_sqwah": row.land_area,
                        "age_years": row.building_age,
                        "price_thb": row.total_price,
                        "floors": row.no_of_floor,
                        "lat": float(lat) if lat is not None else None,
                        "lon": float(lon) if lon is not None else None,
                    }
                    for row, lon, lat in results
                ]

            return json.dumps(
                {
                    "count": len(properties),
                    "filters_applied": {
                        "district": district,
                        "building_style": building_style,
                        "min_price": min_price,
                        "max_price": max_price,
                        "bbox": {
                            "min_lat": min_lat,
                            "max_lat": max_lat,
                            "min_lon": min_lon,
                            "max_lon": max_lon,
                        }
                        if has_bbox
                        else None,
                    },
                    "properties": properties,
                },
                ensure_ascii=False,
            )

    except Exception as e:
        logger.error(f"Property search failed: {e}")
        return json.dumps({"error": str(e)})


@tool
def validate_house_reference(
    property_id: int | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_meters: int = 80,
) -> str:
    """
    Validate that a UI-grounded house reference still exists before interacting with it.

    WHEN TO USE THIS TOOL:
    - User selected a house on the map and asks to analyze "this house"
    - The request references a property/house locator from UI context
    - You need to confirm the target still exists after async updates/filter changes

    Args:
        property_id: Canonical property ID from UI house reference
        latitude: Optional fallback latitude if ID is unavailable
        longitude: Optional fallback longitude if ID is unavailable
        radius_meters: Nearby match radius for coordinate fallback

    Returns:
        JSON with is_valid flag, matched property (if found), and validation metadata.
    """
    try:
        with SessionLocal() as db:
            if property_id is not None:
                row = db.execute(
                    text(
                        """
                        SELECT
                            id, amphur, building_style_desc, total_price,
                            ST_Y(geometry) AS lat, ST_X(geometry) AS lon
                        FROM house_prices
                        WHERE id = :id
                        LIMIT 1
                        """
                    ),
                    {"id": property_id},
                ).fetchone()

                if row:
                    return json.dumps(
                        {
                            "is_valid": True,
                            "match_type": "id",
                            "property": {
                                "id": row.id,
                                "district": row.amphur,
                                "building_style": row.building_style_desc,
                                "price_thb": row.total_price,
                                "lat": row.lat,
                                "lon": row.lon,
                            },
                        },
                        ensure_ascii=False,
                    )

            if latitude is not None and longitude is not None:
                row = db.execute(
                    text(
                        """
                        SELECT
                            id, amphur, building_style_desc, total_price,
                            ST_Y(geometry) AS lat, ST_X(geometry) AS lon,
                            ST_Distance(
                                geometry::geography,
                                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                            ) AS distance_m
                        FROM house_prices
                        WHERE ST_DWithin(
                            geometry::geography,
                            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                            :radius
                        )
                        ORDER BY distance_m
                        LIMIT 1
                        """
                    ),
                    {"lat": latitude, "lon": longitude, "radius": radius_meters},
                ).fetchone()

                if row:
                    return json.dumps(
                        {
                            "is_valid": True,
                            "match_type": "coordinate",
                            "distance_m": round(row.distance_m, 2),
                            "property": {
                                "id": row.id,
                                "district": row.amphur,
                                "building_style": row.building_style_desc,
                                "price_thb": row.total_price,
                                "lat": row.lat,
                                "lon": row.lon,
                            },
                        },
                        ensure_ascii=False,
                    )

            return json.dumps(
                {
                    "is_valid": False,
                    "reason": "No matching property found for the provided house reference.",
                    "property_id": property_id,
                    "latitude": latitude,
                    "longitude": longitude,
                },
                ensure_ascii=False,
            )

    except Exception as e:
        logger.error(f"House reference validation failed: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def get_nearby_properties(
    latitude: float,
    longitude: float,
    radius_meters: int = 500,
    limit: int = 10,
) -> str:
    """
    Find comparable properties near a specific location. Great for price comparisons.

    WHEN TO USE THIS TOOL:
    - User clicks on map and asks about nearby properties
    - User wants comparable sales/prices for a specific location
    - User asks "What are properties selling for near X?"
    - User wants to compare their property to neighbors

    EXAMPLE QUERIES:
    - "What are houses selling for near this location?"
    - "Show me comparable properties within 500m"
    - "What's the average price near Phrom Phong BTS?"

    Args:
        latitude: Center point latitude
        longitude: Center point longitude
        radius_meters: Search radius (300-1000 recommended)
        limit: Number of results (default 10, max 50)

    Returns:
        JSON with count, avg_price_thb, and list of nearby properties with distance_m
    """
    limit = min(limit, 50)

    try:
        with SessionLocal() as db:
            # Use raw SQL for spatial query but reference correct table name
            query = text("""
                SELECT
                    id, amphur, tumbon, building_style_desc,
                    building_area, land_area, building_age,
                    total_price, no_of_floor,
                    ST_Y(geometry) as lat,
                    ST_X(geometry) as lon,
                    ST_Distance(
                        geometry::geography,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                    ) as distance_m
                FROM house_prices
                WHERE total_price IS NOT NULL
                AND ST_DWithin(
                    geometry::geography,
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
    Get real estate market statistics and price trends by district.

    WHEN TO USE THIS TOOL:
    - User asks about market trends or conditions
    - User wants to compare prices across districts
    - User asks "What's the average price in X?"
    - User wants market overview or summary statistics
    - User asks "Which district is cheapest/most expensive?"

    EXAMPLE QUERIES:
    - "What's the property market like in Bangkok?"
    - "Compare prices between Sukhumvit and Ladprao"
    - "What's the average house price in วัฒนา?"
    - "Which districts have the best value?"

    Args:
        district: Specific district name in Thai (optional). If None, returns top 20 districts.
                  Examples: บางกะปิ, สาทร, วัฒนา, พระโขนง, ลาดพร้าว

    Returns:
        JSON with districts array containing: district name, property_count, avg_price_thb,
        min_price_thb, max_price_thb, avg_price_per_sqm
    """
    try:
        with SessionLocal() as db:
            # Use SQLAlchemy ORM for aggregation
            base_query = db.query(
                HousePrice.amphur,
                func.count(HousePrice.id).label("count"),
                func.avg(HousePrice.total_price).label("avg_price"),
                func.min(HousePrice.total_price).label("min_price"),
                func.max(HousePrice.total_price).label("max_price"),
                func.avg(
                    HousePrice.total_price / func.nullif(HousePrice.building_area, 0)
                ).label("avg_price_per_sqm"),
            ).filter(HousePrice.total_price.isnot(None))

            if district:
                base_query = base_query.filter(HousePrice.amphur == district)

            results = (
                base_query.group_by(HousePrice.amphur)
                .order_by(func.avg(HousePrice.total_price).desc())
                .limit(20)
                .all()
            )

            districts = [
                {
                    "district": r.amphur,
                    "property_count": r.count,
                    "avg_price_thb": round(r.avg_price, 0) if r.avg_price else None,
                    "min_price_thb": round(r.min_price, 0) if r.min_price else None,
                    "max_price_thb": round(r.max_price, 0) if r.max_price else None,
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
    Analyze the catchment area - how far can people travel from this location?

    WHEN TO USE THIS TOOL:
    - User asks about accessibility or reachability
    - User wants to know population within travel time of a location
    - User is evaluating a commercial site for customer reach
    - User asks "How many people can reach this in 15 minutes?"

    EXAMPLE QUERIES:
    - "How accessible is this location by walking?"
    - "What's the population within 10-minute drive?"
    - "Analyze the catchment area for this retail site"
    - "How many people live within walking distance?"

    Args:
        latitude: Center point latitude
        longitude: Center point longitude
        minutes: Travel time in minutes (5, 10, 15, 20, or 30 recommended)
        mode: Travel mode - 'walk' (~5km/h) or 'drive' (~30-40km/h in Bangkok traffic)

    Returns:
        JSON with estimated_population, area_km2, population_density, catchment_score (Excellent/Good/Moderate/Low)
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
# Financial and Legal Tools
# =============================================================================


@tool
def compute_financial_projection(
    asset_price_thb: float,
    loan_ratio: float = 0.5,
    annual_interest_rate: float = 0.06,
    annual_revenue_thb: float = 1_200_000,
    annual_expense_thb: float = 420_000,
    projection_years: int = 10,
) -> str:
    """
    Compute ROI projection and break-even estimate for property investment.
    """
    try:
        years = max(1, min(int(projection_years), 30))
        ratio = max(0.0, min(float(loan_ratio), 0.95))
        rate = max(0.0, min(float(annual_interest_rate), 0.5))
        loan_amount = asset_price_thb * ratio
        equity_amount = asset_price_thb - loan_amount
        annual_interest_cost = loan_amount * rate
        annual_net_cashflow = (
            annual_revenue_thb - annual_expense_thb - annual_interest_cost
        )

        cumulative = -equity_amount
        break_even_year: int | None = None
        timeline: list[dict[str, float | int]] = []
        for y in range(1, years + 1):
            cumulative += annual_net_cashflow
            timeline.append(
                {
                    "year": y,
                    "net_cashflow_thb": round(annual_net_cashflow, 2),
                    "cumulative_cashflow_thb": round(cumulative, 2),
                }
            )
            if break_even_year is None and cumulative >= 0:
                break_even_year = y

        return json.dumps(
            {
                "inputs": {
                    "asset_price_thb": asset_price_thb,
                    "loan_ratio": ratio,
                    "annual_interest_rate": rate,
                    "annual_revenue_thb": annual_revenue_thb,
                    "annual_expense_thb": annual_expense_thb,
                    "projection_years": years,
                },
                "derived": {
                    "loan_amount_thb": round(loan_amount, 2),
                    "equity_amount_thb": round(equity_amount, 2),
                    "annual_interest_cost_thb": round(annual_interest_cost, 2),
                    "annual_net_cashflow_thb": round(annual_net_cashflow, 2),
                    "break_even_year": break_even_year,
                    "roi_on_equity_percent": round(
                        (annual_net_cashflow / equity_amount) * 100
                        if equity_amount > 0
                        else 0,
                        2,
                    ),
                },
                "timeline": timeline,
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        logger.error("Financial projection failed: %s", exc)
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@tool
def compute_dsr_and_affordability(
    monthly_income_thb: float,
    existing_monthly_debt_thb: float,
    annual_interest_rate: float = 0.06,
    tenure_years: int = 30,
    dsr_limit: float = 0.4,
) -> str:
    """
    Estimate DSR-based affordable loan amount and prepayment comparison.
    """
    try:
        tenure_months = max(12, min(int(tenure_years * 12), 480))
        monthly_rate = max(0.0, annual_interest_rate) / 12.0
        max_debt_service = max(0.0, monthly_income_thb * dsr_limit)
        available_payment = max(0.0, max_debt_service - existing_monthly_debt_thb)

        if monthly_rate == 0:
            affordable_loan = available_payment * tenure_months
        else:
            affordable_loan = available_payment * (
                (1 - (1 + monthly_rate) ** (-tenure_months)) / monthly_rate
            )

        standard_total_payment = available_payment * tenure_months
        standard_total_interest = max(0.0, standard_total_payment - affordable_loan)

        annual_prepay = 100_000.0
        prepay_total_interest = max(0.0, standard_total_interest - annual_prepay * 8)

        return json.dumps(
            {
                "inputs": {
                    "monthly_income_thb": monthly_income_thb,
                    "existing_monthly_debt_thb": existing_monthly_debt_thb,
                    "annual_interest_rate": annual_interest_rate,
                    "tenure_years": tenure_years,
                    "dsr_limit": dsr_limit,
                },
                "results": {
                    "max_debt_service_thb": round(max_debt_service, 2),
                    "available_payment_thb": round(available_payment, 2),
                    "estimated_max_loan_thb": round(affordable_loan, 2),
                    "standard_total_interest_thb": round(standard_total_interest, 2),
                    "with_prepay_total_interest_thb": round(prepay_total_interest, 2),
                    "interest_saved_thb": round(
                        max(0.0, standard_total_interest - prepay_total_interest), 2
                    ),
                },
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        logger.error("DSR calculation failed: %s", exc)
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@tool
def legal_estate_sale_checklist_th() -> str:
    """
    Provide Thai estate-sale legal checklist and risk controls for buyer contracts.
    """
    payload = {
        "steps": [
            "ตรวจสอบใบมรณบัตรและทะเบียนบ้านของเจ้ามรดก",
            "ยื่นคำร้องศาลเพื่อแต่งตั้งผู้จัดการมรดก (ศาลแพ่งหรือศาลจังหวัดที่เกี่ยวข้อง)",
            "เมื่อมีคำสั่งศาล ให้ผู้จัดการมรดกดำเนินการรับรองอำนาจและเอกสารสิทธิ",
            "ทำสัญญาจะซื้อจะขายโดยใส่เงื่อนไขบังคับก่อนก่อนโอน",
            "โอนกรรมสิทธิ์ที่สำนักงานที่ดินเมื่อเอกสารครบและผู้มีอำนาจลงนามถูกต้อง",
        ],
        "contract_conditions_precedent": [
            "สัญญามีผลเมื่อศาลมีคำสั่งแต่งตั้งผู้จัดการมรดกถึงที่สุด",
            "ผู้ขายต้องแสดงเอกสารสิทธิปลอดภาระหรือแจ้งภาระทั้งหมดเป็นลายลักษณ์อักษร",
            "หากไม่ผ่านเงื่อนไขภายในกำหนด ผู้ซื้อมีสิทธิรับเงินมัดจำคืนเต็มจำนวน",
        ],
        "deposit_risk_controls": [
            "วางมัดจำเป็นงวดตาม milestone เอกสาร",
            "ใช้บัญชี escrow หรือทนายความดูแลเงิน",
            "กำหนดเบี้ยปรับ/สิทธิเลิกสัญญาให้ชัดเจน",
        ],
        "disclaimer": "ข้อมูลนี้เป็นแนวทางทั่วไป ไม่ใช่คำปรึกษากฎหมายเฉพาะคดี ควรให้ทนายตรวจเอกสารก่อนลงนาม",
    }
    return json.dumps(payload, ensure_ascii=False)


@tool
def geocode_place_nominatim(place: str) -> str:
    """Geocode place name to lat/lon using Nominatim with local cache and gentle rate limit."""
    global _GEOCODE_LAST_CALL_TS
    key = place.strip().lower()
    if not key:
        return json.dumps({"error": "place is required"}, ensure_ascii=False)
    if key in _GEOCODE_CACHE:
        return json.dumps(
            {"source": "cache", **_GEOCODE_CACHE[key]}, ensure_ascii=False
        )

    try:
        now = time.time()
        elapsed = now - _GEOCODE_LAST_CALL_TS
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

        url = (
            "https://nominatim.openstreetmap.org/search?format=json&limit=1&q="
            + quote_plus(place)
        )
        req = Request(url, headers={"User-Agent": "site-select-core-agent/1.0"})
        with urlopen(req, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        _GEOCODE_LAST_CALL_TS = time.time()

        if not payload:
            return json.dumps(
                {"error": "No geocoding result found"}, ensure_ascii=False
            )

        first = payload[0]
        result = {
            "place": place,
            "lat": float(first["lat"]),
            "lon": float(first["lon"]),
            "display_name": first.get("display_name"),
        }
        _GEOCODE_CACHE[key] = result
        return json.dumps({"source": "nominatim", **result}, ensure_ascii=False)
    except Exception as exc:
        logger.error("Nominatim geocoding failed: %s", exc)
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@tool
def compare_candidates_by_criteria(
    candidates_json: str,
    criteria_json: str,
) -> str:
    """
    Score and rank candidate records against weighted criteria.
    """
    try:
        candidates = json.loads(candidates_json)
        criteria = json.loads(criteria_json)
        if not isinstance(candidates, list) or not isinstance(criteria, list):
            return json.dumps({"error": "Invalid JSON inputs"}, ensure_ascii=False)

        ranked: list[dict[str, float | str | int]] = []
        for idx, candidate in enumerate(candidates):
            score = 0.0
            for rule in criteria:
                field = str(rule.get("field", ""))
                op = str(rule.get("op", "eq"))
                weight = float(rule.get("weight", 1.0))
                target = rule.get("value")
                value = candidate.get(field)

                passed = False
                if op == "eq":
                    passed = value == target
                elif op == "lte" and value is not None and target is not None:
                    passed = float(value) <= float(target)
                elif op == "gte" and value is not None and target is not None:
                    passed = float(value) >= float(target)
                elif (
                    op == "contains"
                    and isinstance(value, str)
                    and isinstance(target, str)
                ):
                    passed = target.lower() in value.lower()

                if passed:
                    score += weight

            ranked.append(
                {
                    "rank_key": idx,
                    "score": round(score, 3),
                    "candidate": candidate,
                }
            )

        ranked.sort(key=lambda x: float(x["score"]), reverse=True)
        for i, item in enumerate(ranked, start=1):
            item["rank"] = i

        return json.dumps({"count": len(ranked), "ranked": ranked}, ensure_ascii=False)
    except Exception as exc:
        logger.error("Candidate comparison failed: %s", exc)
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


# =============================================================================
# Tool Registry
# =============================================================================

from src.services.rag_service import retrieve_knowledge
from src.services.internal_knowledge import internal_knowledge_service


@tool
def query_internal_knowledge(
    query: str,
    domain: str | None = None,
    filters_json: str | None = None,
    limit: int = 5,
) -> str:
    """
    Query curated internal project/neighborhood/legal knowledge fixtures.
    Use this when you need benchmark-critical metadata that is not in the property DB.
    """
    try:
        filters: dict[str, Any] | None = None
        if filters_json:
            parsed = json.loads(filters_json)
            if isinstance(parsed, dict):
                filters = parsed
        result = internal_knowledge_service.query(
            query=query,
            domain=domain,
            limit=limit,
            filters=filters,
        )
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        logger.error("Internal knowledge query failed: %s", exc)
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


# List of all available tools for the agent
# Ordered by frequency of use
ALL_TOOLS = [
    # Primary property tools - use these first for property queries
    search_properties,  # Find properties by criteria
    validate_house_reference,  # Validate UI-grounded property references
    get_nearby_properties,  # Find comparable properties near a location
    get_market_statistics,  # Get market overview and district stats
    # Location analysis tools - use for evaluating locations
    get_location_intelligence,  # Livability scores (transit, schools, flood, etc.)
    analyze_site,  # Business site analysis (competitors, magnets)
    analyze_catchment,  # Travel time and population reach
    geocode_place_nominatim,  # Place -> coordinates with caching
    # Price and valuation tools
    predict_property_price,  # Estimate property value (mock for now)
    # Financial/legal analytic tools
    compute_financial_projection,
    compute_dsr_and_affordability,
    legal_estate_sale_checklist_th,
    compare_candidates_by_criteria,
    query_internal_knowledge,
    # Knowledge retrieval - use for general questions
    retrieve_knowledge,  # Search knowledge base for background info
]
